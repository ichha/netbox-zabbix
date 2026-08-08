from django.views.generic import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
import logging
from .zabbix_api import ZabbixAPI
from .template_storage import (
    get_mapped_templates, 
    get_role_zabbix_settings, 
    save_mapped_templates, 
    remove_role_zabbix_settings,
    remove_role_setting_field
)
from .signals import build_snmp_details, get_or_create_hostgroup_id, execute_zabbix_host_save, push_device_to_zabbix

logger = logging.getLogger('netbox.plugins.netbox_zabbix')


def process_table_data(request, items, headers, title, default_per_page=50, has_status=True, extra_context=None):
    total_devices = len(items)

    synced_devices = 0
    devices_to_sync = 0

    if has_status:
        for row in items:
            row_cells = [c for c in row if isinstance(c, dict)]
            row_strs = [str(c).lower() for c in row if not isinstance(c, dict)]

            is_matched = any(c.get("type") in ["matched", "synced"] for c in row_cells) or any(s in row_strs for s in ['matched', 'monitored', 'active', 'online'])
            if is_matched:
                synced_devices += 1
            else:
                devices_to_sync += 1

        status_filter = request.GET.get('status', '').strip().lower()
        if status_filter in ['synced', 'active', 'matched']:
            items = [
                row for row in items 
                if any(c.get("type") in ["matched", "synced"] for c in row if isinstance(c, dict))
                or any(s in [str(c).lower() for c in row if not isinstance(c, dict)] for s in ['matched', 'monitored', 'active', 'online'])
            ]
        elif status_filter in ['pending', 'inactive', 'mismatch', 'not_in_zabbix', 'disabled']:
            items = [
                row for row in items 
                if any(c.get("type") in ["name_mismatch", "ip_mismatch", "not_in_zabbix"] for c in row if isinstance(c, dict))
                or any(s in [str(c).lower() for c in row if not isinstance(c, dict)] for s in ['mismatch', 'disabled', 'unmonitored', 'offline'])
            ]
    else:
        status_filter = ""

    q = request.GET.get('q', '').strip()
    if q:
        items = [
            row for row in items 
            if any(q.lower() in str(c.get("text", "")).lower() for c in row if isinstance(c, dict))
            or any(q.lower() in str(c).lower() for c in row if not isinstance(c, dict))
        ]

    filtered_count = len(items)

    per_page_param = request.GET.get('per_page', str(default_per_page))
    page_param = request.GET.get('page', '1')

    if per_page_param.lower() == 'all':
        per_page = filtered_count if filtered_count > 0 else 1
    else:
        try:
            per_page = int(per_page_param)
            if per_page <= 0:
                per_page = default_per_page
        except ValueError:
            per_page = default_per_page

    paginator = Paginator(items, per_page if per_page > 0 else 1)

    try:
        page_obj = paginator.page(page_param)
    except Exception:
        page_obj = paginator.page(1)

    res = {
        'title': title,
        'headers': headers,
        'page_obj': page_obj,
        'per_page': per_page_param if per_page_param == 'all' else per_page,
        'total_devices': total_devices,
        'synced_devices': synced_devices,
        'devices_to_sync': devices_to_sync,
        'status_filter': status_filter,
        'has_status': has_status,
        'q': q,
    }
    if extra_context and isinstance(extra_context, dict):
        res.update(extra_context)
    return res


class ZabbixServersView(View):
    def get(self, request):
        api = ZabbixAPI()
        version, error = api.get_api_version()
        
        # Fast API counts using countOutput (INSTANT vs downloading 50MB of host data!)
        try:
            h_res = api.call('host.get', {'countOutput': True})
            host_count = int(h_res) if isinstance(h_res, (int, str)) and str(h_res).isdigit() else 0
        except Exception:
            host_count = 0

        try:
            t_res = api.call('template.get', {'countOutput': True})
            template_count = int(t_res) if isinstance(t_res, (int, str)) and str(t_res).isdigit() else 0
        except Exception:
            template_count = 0

        try:
            p_res = api.call('proxy.get', {'countOutput': True})
            proxy_count = int(p_res) if isinstance(p_res, (int, str)) and str(p_res).isdigit() else 0
        except Exception:
            proxy_count = 0

        try:
            g_res = api.call('hostgroup.get', {'countOutput': True})
            hostgroup_count = int(g_res) if isinstance(g_res, (int, str)) and str(g_res).isdigit() else 0
        except Exception:
            hostgroup_count = 0

        try:
            m_res = api.call('usermacro.get', {'globalmacro': True, 'countOutput': True})
            macro_count = int(m_res) if isinstance(m_res, (int, str)) and str(m_res).isdigit() else 0
        except Exception:
            macro_count = 0

        tag_count = 0
        try:
            tags = api.get_tags()
            tag_count = len(tags) if isinstance(tags, list) else 0
        except Exception:
            pass

        # Auto-sync state
        from .models import ZabbixSyncState
        sync_enabled = ZabbixSyncState.is_enabled()
        
        context = {
            'zabbix_url': api.url,
            'zabbix_token': api.token,
            'zabbix_version': version,
            'connected': error is None,
            'error': error,
            'host_count': host_count,
            'template_count': template_count,
            'proxy_count': proxy_count,
            'hostgroup_count': hostgroup_count,
            'macro_count': macro_count,
            'tag_count': tag_count,
            'sync_enabled': sync_enabled,
        }
        return render(request, 'netbox_zabbix/zabbix_server.html', context)


class ZabbixProxiesView(View):
    def get(self, request):
        api = ZabbixAPI()
        proxies = api.get_proxies()
        
        if isinstance(proxies, dict) and "error" in proxies:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Proxies', 'error': proxies["error"]
            })
            
        headers = ["Proxy ID", "Name", "Mode", "State", "Version", "Last Seen"]
        items = []
        if isinstance(proxies, list):
            for p in proxies:
                proxy_id = str(p.get("proxyid") or p.get("id") or "-")
                name = p.get("name") or p.get("host") or f"Proxy {proxy_id}"

                op_mode = p.get("operating_mode")
                if op_mode is not None:
                    mode_str = "Active" if str(op_mode) == "0" else "Passive" if str(op_mode) == "1" else f"Mode {op_mode}"
                else:
                    st = p.get("status")
                    mode_str = "Active" if str(st) in ["5", "0"] else "Passive" if str(st) in ["6", "1"] else f"Mode {st}"

                st_val = p.get("state")
                state_str = "Online" if str(st_val) == "0" else "Offline" if str(st_val) == "1" else "-" if st_val is None else str(st_val)

                ver_str = p.get("version", "-") or "-"
                last_seen = p.get("lastaccess", "")
                last_seen_str = f"{last_seen}s" if last_seen and str(last_seen).isdigit() else "-" if not last_seen else str(last_seen)

                items.append([
                    proxy_id,
                    name,
                    mode_str,
                    state_str,
                    ver_str,
                    last_seen_str
                ])
                
        context = process_table_data(request, items, headers, 'Proxies', has_status=True)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixProxyGroupsView(View):
    def get(self, request):
        api = ZabbixAPI()
        groups = api.get_proxy_groups()
        
        if isinstance(groups, dict) and "error" in groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Proxy Groups', 'error': groups["error"]
            })
            
        headers = ["Group ID", "Name", "State"]
        items = []
        if isinstance(groups, list):
            for g in groups:
                items.append([
                    g.get("proxy_groupid", "-"),
                    g.get("name", "-"),
                    g.get("state", "-") or "-"
                ])
                
        context = process_table_data(request, items, headers, 'Proxy Groups', has_status=False)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixTemplatesView(View):
    def get(self, request):
        api = ZabbixAPI()
        templates = api.get_templates()
        
        if isinstance(templates, dict) and "error" in templates:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Templates', 'error': templates["error"]
            })
            
        headers = ["Template ID", "Template Name", "Technical Name"]
        items = []
        if isinstance(templates, list):
            for t in templates:
                name_disp = t.get("name", "") or t.get("host", "-")
                items.append([
                    t.get("templateid", "-"),
                    name_disp,
                    t.get("host", "-")
                ])
                
        context = process_table_data(request, items, headers, 'Templates', has_status=False)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixTemplateGroupsView(View):
    def get(self, request):
        api = ZabbixAPI()
        groups = api.get_template_groups()
        
        if isinstance(groups, dict) and "error" in groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Template Groups', 'error': groups["error"]
            })
            
        headers = ["Group ID", "Group Name"]
        items = []
        if isinstance(groups, list):
            for g in groups:
                items.append([
                    g.get("groupid", "-"),
                    g.get("name", "-")
                ])
                
        context = process_table_data(request, items, headers, 'Template Groups', has_status=False)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixMacrosView(View):
    def get(self, request):
        api = ZabbixAPI()
        macros = api.get_macros()
        
        if isinstance(macros, dict) and "error" in macros:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Global Macros', 'error': macros["error"]
            })
            
        headers = ["Macro ID", "Macro Name", "Value"]
        items = []
        if isinstance(macros, list):
            for m in macros:
                items.append([
                    m.get("globalmacroid", "-"),
                    m.get("macro", "-"),
                    m.get("value", "-")
                ])
                
        context = process_table_data(request, items, headers, 'Global Macros', has_status=False)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixTagsView(View):
    def get(self, request):
        api = ZabbixAPI()
        tags = api.get_tags()
        
        if isinstance(tags, dict) and "error" in tags:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Tags', 'error': tags["error"]
            })
            
        headers = ["Tag Name", "Tag Value"]
        items = []
        if isinstance(tags, list):
            for t in tags:
                items.append([
                    t.get("tag", "-"),
                    t.get("value", "-") or "-"
                ])
                
        context = process_table_data(request, items, headers, 'Tags', has_status=False)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixHostGroupsView(View):
    def get(self, request):
        api = ZabbixAPI()
        zabbix_groups = api.get_host_groups()
        zabbix_templates = api.get_templates()
        zabbix_proxies = api.get_proxies()
        
        if isinstance(zabbix_groups, dict) and "error" in zabbix_groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Host Groups', 'error': zabbix_groups["error"]
            })

        all_templates_list = []
        if isinstance(zabbix_templates, list):
            for tmpl in zabbix_templates:
                tid = str(tmpl.get("templateid", ""))
                tname = tmpl.get("name") or tmpl.get("host") or f"Template {tid}"
                all_templates_list.append({
                    "templateid": tid,
                    "name": tname,
                    "host": tmpl.get("host", "")
                })

        all_proxies_list = [{"proxyid": "0", "name": "Server (Direct Connection)"}]
        if isinstance(zabbix_proxies, list):
            for px in zabbix_proxies:
                p_id = str(px.get("proxyid") or px.get("id") or "")
                p_name = px.get("name") or px.get("host") or f"Proxy {p_id}"
                if p_id:
                    all_proxies_list.append({"proxyid": p_id, "name": f"Proxy: {p_name}"})

        try:
            zabbix_proxy_groups = api.get_proxy_groups()
            if isinstance(zabbix_proxy_groups, list):
                for pg in zabbix_proxy_groups:
                    pg_id = str(pg.get("proxy_groupid") or "")
                    pg_name = pg.get("name") or f"Proxy Group {pg_id}"
                    if pg_id:
                        all_proxies_list.append({"proxyid": f"group_{pg_id}", "name": f"Proxy Group: {pg_name}"})
        except Exception:
            pass

        zabbix_group_map = {}
        if isinstance(zabbix_groups, list):
            for g in zabbix_groups:
                g_name = g.get("name", "").strip()
                if g_name:
                    zabbix_group_map[g_name.lower()] = g

        netbox_roles = []
        try:
            from dcim.models import DeviceRole
            netbox_roles = list(DeviceRole.objects.all())
        except Exception as e:
            logger.error(f"Error fetching NetBox DeviceRoles: {e}")

        headers = ["Group ID", "Zabbix Host Group Name", "NetBox Device Role", "Zabbix Settings", "Sync Status"]
        items = []
        processed_zabbix_lower = set()

        for role in netbox_roles:
            r_name = role.name
            r_lower = r_name.strip().lower()
            role_slug = r_name.replace("/", "_").replace(" ", "_").replace("-", "_").lower()

            settings = get_role_zabbix_settings(r_name)
            mapped_settings_cell = {
                "type": "mapped_settings",
                "role_name": r_name,
                "role_slug": role_slug,
                "has_settings": settings.get("has_settings", False),
                "templates": settings.get("templates", []),
                "template_ids": [str(t["id"]) for t in settings.get("templates", [])],
                "interface_type": settings.get("interface_type"),
                "proxy_id": str(settings.get("proxy_id")) if settings.get("proxy_id") is not None else None,
                "proxy_name": settings.get("proxy_name")
            }

            if r_lower in zabbix_group_map:
                zg = zabbix_group_map[r_lower]
                gid = zg.get("groupid", "-")
                processed_zabbix_lower.add(r_lower)
                status_cell = {"type": "synced", "text": "Synced"}
                zg_name_disp = zg.get("name", r_name)
            else:
                gid = "—"
                zg_name_disp = "—"
                status_cell = {
                    "type": "create_group_button",
                    "role_name": r_name
                }

            items.append([
                gid,
                zg_name_disp,
                r_name,
                mapped_settings_cell,
                status_cell
            ])

        if isinstance(zabbix_groups, list):
            for g in zabbix_groups:
                g_name = g.get("name", "")
                if g_name.strip().lower() not in processed_zabbix_lower:
                    role_slug = g_name.replace("/", "_").replace(" ", "_").replace("-", "_").lower()
                    settings = get_role_zabbix_settings(g_name)
                    mapped_settings_cell = {
                        "type": "mapped_settings",
                        "role_name": g_name,
                        "role_slug": role_slug,
                        "has_settings": settings.get("has_settings", False),
                        "templates": settings.get("templates", []),
                        "template_ids": [str(t["id"]) for t in settings.get("templates", [])],
                        "interface_type": settings.get("interface_type"),
                        "proxy_id": str(settings.get("proxy_id")) if settings.get("proxy_id") is not None else None,
                        "proxy_name": settings.get("proxy_name")
                    }
                    items.append([
                        g.get("groupid", "-"),
                        g_name,
                        "—",
                        mapped_settings_cell,
                        {"type": "none", "text": "Zabbix Only"}
                    ])

        context = process_table_data(
            request, items, headers, 'Host Groups', has_status=False, 
            extra_context={
                'all_templates': all_templates_list,
                'all_proxies': all_proxies_list
            }
        )
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixMapTemplatesView(View):
    def post(self, request):
        role_name = request.POST.get('role_name')
        template_ids = request.POST.getlist('template_ids')
        interface_type = request.POST.get('interface_type', '').strip()
        proxy_id = str(request.POST.get('proxy_id', '')).strip()
        
        if not role_name:
            messages.error(request, "Missing Role/Hostgroup name.")
            return redirect('plugins:netbox_zabbix:hostgroups')

        api = ZabbixAPI()
        z_templates = api.get_templates()
        z_proxies = api.get_proxies()

        z_proxy_groups = None
        try:
            z_proxy_groups = api.get_proxy_groups()
        except Exception:
            pass
        
        tmpl_lookup = {}
        if isinstance(z_templates, list):
            for t in z_templates:
                tid = str(t.get("templateid", ""))
                tname = t.get("name") or t.get("host") or f"Template {tid}"
                if tid:
                    tmpl_lookup[tid] = tname

        template_names = [tmpl_lookup.get(str(tid), f"Template {tid}") for tid in template_ids]

        proxy_name = None
        if proxy_id == "0":
            proxy_name = "Server"
        elif proxy_id.startswith("group_"):
            pg_id = proxy_id.replace("group_", "")
            if isinstance(z_proxy_groups, list):
                for pg in z_proxy_groups:
                    if str(pg.get("proxy_groupid")) == pg_id:
                        p_name = pg.get('name') or f"Group {pg_id}"
                        proxy_name = f"Proxy Group: {p_name}"
                        break
            if not proxy_name:
                proxy_name = f"Proxy Group (ID {pg_id})"
        elif proxy_id != "" and isinstance(z_proxies, list):
            for px in z_proxies:
                px_id = str(px.get("proxyid") or px.get("id") or "")
                if px_id == proxy_id:
                    p_name = px.get('name') or px.get('host') or f"Proxy {proxy_id}"
                    proxy_name = f"Proxy: {p_name}"
                    break
            if not proxy_name and proxy_id != "":
                proxy_name = f"Proxy (ID {proxy_id})"

        save_mapped_templates(role_name, template_ids, template_names, interface_type, proxy_id, proxy_name)

        messages.success(request, f"Successfully saved Zabbix Settings for '{role_name}'. Go to Bulk Push to sync with Zabbix.")
        return redirect('plugins:netbox_zabbix:hostgroups')


class ZabbixClearSettingsView(View):
    def post(self, request):
        role_name = request.POST.get('role_name')
        if not role_name:
            messages.error(request, "Missing Role name.")
            return redirect('plugins:netbox_zabbix:hostgroups')

        remove_role_zabbix_settings(role_name)
        messages.success(request, f"Successfully cleared all Zabbix Settings for '{role_name}'.")
        return redirect('plugins:netbox_zabbix:hostgroups')


class ZabbixRemoveSettingFieldView(View):
    def post(self, request):
        role_name = request.POST.get('role_name')
        field_name = request.POST.get('field_name')
        if not role_name or not field_name:
            messages.error(request, "Missing Role name or field name.")
            return redirect('plugins:netbox_zabbix:hostgroups')

        remove_role_setting_field(role_name, field_name)
        messages.success(request, f"Removed {field_name.replace('_', ' ').capitalize()} setting for '{role_name}'.")
        return redirect('plugins:netbox_zabbix:hostgroups')


class ZabbixRemoveTemplateView(View):
    def post(self, request):
        role_name = request.POST.get('role_name')
        template_id = request.POST.get('template_id')
        
        if not role_name or not template_id:
            messages.error(request, "Missing Role name or Template ID.")
            return redirect('plugins:netbox_zabbix:hostgroups')

        settings = get_role_zabbix_settings(role_name)
        cur_mapped = settings.get("templates", [])
        new_mapped = [t for t in cur_mapped if str(t.get("id")) != str(template_id)]
        
        new_ids = [str(t["id"]) for t in new_mapped]
        new_names = [t["name"] for t in new_mapped]
        
        save_mapped_templates(
            role_name, new_ids, new_names, 
            settings.get("interface_type"), 
            settings.get("proxy_id"), 
            settings.get("proxy_name")
        )
        messages.success(request, f"Removed template from '{role_name}'.")
        return redirect('plugins:netbox_zabbix:hostgroups')


class ZabbixCreateHostGroupView(View):
    def post(self, request):
        role_name = request.POST.get('role_name')
        
        if not role_name:
            messages.error(request, "Missing NetBox Device Role name.")
            return redirect('plugins:netbox_zabbix:hostgroups')
            
        api = ZabbixAPI()
        
        group_id = get_or_create_hostgroup_id(api, role_name)
        if group_id:
            messages.success(request, f"Host Group '{role_name}' is ready in Zabbix (ID {group_id})!")
        return redirect('plugins:netbox_zabbix:hostgroups')

class ZabbixHostsView(View):
    def get(self, request):
        api = ZabbixAPI()
        from dcim.models import Device

        # 1. Base Queryset for NetBox Devices with Primary IP
        qs = Device.objects.filter(
            Q(primary_ip4__isnull=False) | Q(primary_ip6__isnull=False)
        ).select_related('role', 'primary_ip4', 'primary_ip6')

        q = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '').strip().lower()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(primary_ip4__address__icontains=q) |
                Q(role__name__icontains=q)
            )

        total_devices = qs.count()

        # 2. Get role settings map (for attached template comparison)
        from .models import ZabbixHostGroupTemplate
        configured_roles = ZabbixHostGroupTemplate.objects.all()
        role_settings_map = {cfg.role_name: get_role_zabbix_settings(cfg.role_name) for cfg in configured_roles}

        # 3. Pagination Setup (Default 50 per page, max 200 for performance)
        per_page_param = request.GET.get('per_page', '50')
        page_param = request.GET.get('page', '1')

        try:
            per_page = int(per_page_param) if per_page_param.lower() != 'all' else 50
            if per_page <= 0:
                per_page = 50
            if per_page > 200:
                per_page = 200
        except ValueError:
            per_page = 50

        try:
            page_num = int(page_param)
            if page_num <= 0:
                page_num = 1
        except ValueError:
            page_num = 1

        paginator = Paginator(qs, per_page)
        try:
            page_obj = paginator.page(page_num)
        except Exception:
            page_obj = paginator.page(1)
            page_num = 1

        page_devices = list(page_obj.object_list)
        page_names = [d.name for d in page_devices if d.name]
        page_ips = []
        for d in page_devices:
            if d.primary_ip4:
                page_ips.append(str(d.primary_ip4.address).split('/')[0])
            elif d.primary_ip6:
                page_ips.append(str(d.primary_ip6.address).split('/')[0])

        # 4. TARGETED ZABBIX FETCH: Query Zabbix ON DEMAND ONLY for current page's devices
        zabbix_hosts = []
        zabbix_error = None
        if page_names:
            try:
                res = api.call('host.get', {
                    'filter': {'host': page_names},
                    'selectInterfaces': ['interfaceid', 'type', 'main', 'ip', 'port', 'details'],
                    'selectParentTemplates': ['templateid', 'name'],
                    'selectHostGroups': ['groupid', 'name'],
                    'selectMacros': ['macro', 'value'],
                    'output': ['hostid', 'host', 'name', 'status', 'proxy_hostid', 'proxy_groupid', 'monitored_by']
                })
                if isinstance(res, list):
                    zabbix_hosts.extend(res)
                elif isinstance(res, dict) and "error" in res:
                    zabbix_error = str(res["error"])
            except Exception as e:
                logger.error(f"Error fetching targeted Zabbix hosts by name: {e}")

            found_names = {h.get('host', '').strip().lower() for h in zabbix_hosts if isinstance(h, dict)}
            missing_names = [n for n in page_names if n.strip().lower() not in found_names]
            if missing_names and page_ips:
                try:
                    res_ip = api.call('host.get', {
                        'filter': {'ip': page_ips},
                        'selectInterfaces': ['interfaceid', 'type', 'main', 'ip', 'port', 'details'],
                        'selectParentTemplates': ['templateid', 'name'],
                        'selectHostGroups': ['groupid', 'name'],
                        'selectMacros': ['macro', 'value'],
                        'output': ['hostid', 'host', 'name', 'status', 'proxy_hostid', 'proxy_groupid', 'monitored_by']
                    })
                    if isinstance(res_ip, list):
                        for h in res_ip:
                            if isinstance(h, dict) and h.get('host', '').strip().lower() not in found_names:
                                zabbix_hosts.append(h)
                except Exception as e:
                    logger.error(f"Error fetching targeted Zabbix hosts by IP: {e}")

        # Build Lookups
        zabbix_name_map = {}
        zabbix_ip_map = {}
        if isinstance(zabbix_hosts, list):
            for zh in zabbix_hosts:
                if not isinstance(zh, dict):
                    continue
                zh_tech = (zh.get("host") or "").strip().lower()
                zh_vis = (zh.get("name") or "").strip().lower()
                if zh_tech:
                    zabbix_name_map[zh_tech] = zh
                if zh_vis:
                    zabbix_name_map[zh_vis] = zh

                ifaces = zh.get("interfaces", [])
                if isinstance(ifaces, list):
                    for ifc in ifaces:
                        if isinstance(ifc, dict):
                            ip_addr = (ifc.get("ip") or "").strip()
                            if ip_addr and ip_addr not in ["0.0.0.0", "127.0.0.1"]:
                                zabbix_ip_map[ip_addr] = zh

        # Fast Proxy Map
        proxy_map = {}
        try:
            proxies = api.get_proxies()
            if isinstance(proxies, list):
                for p in proxies:
                    p_id = str(p.get("proxyid") or p.get("id") or "")
                    p_name = p.get("name") or p.get("host")
                    if p_id and p_name:
                        proxy_map[p_id] = p_name
        except Exception:
            pass

        # 5. Build Page Blocks and Evaluate All 5 Comparisons
        page_blocks = []
        page_matched_count = 0
        page_mismatch_count = 0

        for dev in page_devices:
            nb_name = dev.name or f"Device-{dev.pk}"
            nb_ip = "—"
            if dev.primary_ip4:
                nb_ip = str(dev.primary_ip4.address).split('/')[0]
            elif dev.primary_ip6:
                nb_ip = str(dev.primary_ip6.address).split('/')[0]

            nb_status = str(dev.status).capitalize() if dev.status else "Active"
            nb_role = dev.role.name if dev.role else "—"

            nb_name_lower = nb_name.strip().lower()
            matching_zabbix_host = zabbix_name_map.get(nb_name_lower) or zabbix_ip_map.get(nb_ip)

            item = {
                "netbox_name": nb_name,
                "netbox_ip": nb_ip,
                "netbox_status": nb_status,
                "netbox_role": nb_role,
                "netbox_mapped_hostgroup": nb_role,
                "match_status": "mismatch",
                "mismatch_reasons": [],
                "role_synced": False,
                "zabbix_exists": False,
                "zabbix_hostid": "",
                "zabbix_name": "—",
                "zabbix_ip": "—",
                "zabbix_port": "",
                "zabbix_status": "—",
                "zabbix_hostgroups": [],
                "zabbix_templates": [],
                "netbox_templates": [],
                "zabbix_protocol": "—",
                "zabbix_monitored_by": "—",
                "snmp_version": "—",
                "snmp_community": "—",
                "snmp_max_repetitions": "—",
                "snmp_bulk": "—",
                "snmpv3_context": "—",
                "snmpv3_secname": "—",
                "snmpv3_seclevel": "—",
                "snmpv3_authproto": "—",
                "snmpv3_authpass": "—",
                "snmpv3_privproto": "—",
                "snmpv3_privpass": "—",
            }

            role_cfg = role_settings_map.get(nb_role, {})
            netbox_templates = [t['name'] for t in role_cfg.get('templates', []) if isinstance(t, dict) and t.get('name')]
            item["netbox_templates"] = netbox_templates

            mismatch_reasons = []

            if not matching_zabbix_host:
                mismatch_reasons.append("Not in Zabbix")
            else:
                zh_target = matching_zabbix_host
                item["zabbix_exists"] = True
                zh_hid = str(zh_target.get("hostid", ""))
                item["zabbix_hostid"] = zh_hid
                
                c_tech = (zh_target.get("host") or "").strip()
                c_vis = (zh_target.get("name") or "").strip()
                item["zabbix_name"] = c_vis if c_vis else c_tech

                # COMPARISON 1: Name Check
                if nb_name_lower != c_tech.lower() and nb_name_lower != c_vis.lower():
                    mismatch_reasons.append(f"Name Mismatch ({nb_name} vs {item['zabbix_name']})")

                # COMPARISON 2: Primary IP Check
                interfaces = zh_target.get("interfaces", [])
                zip_addr = "—"
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break
                    zip_addr = (main_iface.get("ip") or "").strip()
                    item["zabbix_ip"] = zip_addr if zip_addr else nb_ip
                    item["zabbix_port"] = str(main_iface.get("port") or "")

                    t_val = str(main_iface.get("type", "1"))
                    item["zabbix_protocol"] = "SNMP" if t_val == "2" else "IPMI" if t_val == "3" else "JMX" if t_val == "4" else "Agent"

                    if t_val == "2":
                        details = main_iface.get("details", {})
                        if not isinstance(details, dict):
                            details = {}
                        ver = str(details.get("version") or main_iface.get("version") or "2")
                        item["snmp_version"] = "SNMPv1" if ver == "1" else "SNMPv3" if ver == "3" else "SNMPv2c"
                        raw_comm = details.get("community") or main_iface.get("community")
                        if raw_comm:
                            item["snmp_community"] = str(raw_comm)

                if nb_ip != "—" and zip_addr != "—" and nb_ip != zip_addr:
                    mismatch_reasons.append(f"IP Mismatch ({nb_ip} vs {zip_addr})")

                # COMPARISON 3: Status Check (Active <-> Monitored '0', Non-Active <-> Disabled '1')
                z_st = str(zh_target.get("status", "0"))
                item["zabbix_status"] = "Monitored" if z_st == "0" else "Disabled"
                
                if nb_status.lower() == 'active':
                    if z_st != '0':
                        mismatch_reasons.append("Status Mismatch (NetBox: Active, Zabbix: Disabled)")
                else:
                    if z_st != '1':
                        mismatch_reasons.append(f"Status Mismatch (NetBox: {nb_status}, Zabbix: Monitored)")

                # COMPARISON 4: Role / Host Group Check
                z_groups = zh_target.get("hostgroups", []) or zh_target.get("groups", [])
                item["zabbix_hostgroups"] = [g.get("name") for g in z_groups if isinstance(g, dict) and g.get("name")]

                if nb_role != "—" and nb_role:
                    if not any(nb_role.lower() == zg.lower() for zg in item["zabbix_hostgroups"]):
                        mismatch_reasons.append(f"Host Group Mismatch (Missing group: {nb_role})")

                # COMPARISON 5: Attached Templates Check (Inherited from NetBox Role settings)
                all_t_objs = []
                for k in ["parentTemplates", "templates", "inheritedTemplates"]:
                    t_list = zh_target.get(k)
                    if isinstance(t_list, list):
                        all_t_objs.extend(t_list)

                template_names = []
                seen_t = set()
                for t in all_t_objs:
                    if isinstance(t, dict):
                        t_n = t.get("name") or t.get("host")
                        if t_n and t_n not in seen_t:
                            seen_t.add(t_n)
                            template_names.append(t_n)

                item["zabbix_templates"] = template_names

                role_cfg = role_settings_map.get(nb_role, {})
                expected_tmpls = [t['name'].strip() for t in role_cfg.get('templates', []) if t.get('name')]
                if expected_tmpls:
                    z_tmpls_lower = [t.lower() for t in template_names]
                    missing_tmpls = [t for t in expected_tmpls if t.lower() not in z_tmpls_lower]
                    if missing_tmpls:
                        mismatch_reasons.append(f"Missing Templates: {', '.join(missing_tmpls)}")

                proxy_id = str(zh_target.get("proxyid") or zh_target.get("proxy_hostid") or "0")
                proxy_group_id = str(zh_target.get("proxy_groupid") or "0")
                monitored_by = str(zh_target.get("monitored_by") or "0")

                if (monitored_by == "1" or proxy_id != "0") and proxy_id in proxy_map:
                    item["zabbix_monitored_by"] = f"Proxy: {proxy_map[proxy_id]}"
                elif (monitored_by == "2" or proxy_group_id != "0"):
                    pg_key = f"group_{proxy_group_id}"
                    item["zabbix_monitored_by"] = proxy_map.get(pg_key, f"Proxy Group (ID {proxy_group_id})")
                elif proxy_id != "0":
                    item["zabbix_monitored_by"] = f"Proxy (ID {proxy_id})"
                else:
                    item["zabbix_monitored_by"] = "Server"

            if len(mismatch_reasons) == 0:
                item["match_status"] = "matched"
                page_matched_count += 1
            else:
                item["match_status"] = "mismatch"
                item["mismatch_reasons"] = mismatch_reasons
                page_mismatch_count += 1

            page_blocks.append(item)

        # 6. Apply status filter if ?status=matched or ?status=mismatch was clicked
        if status_filter in ['synced', 'active', 'matched']:
            filtered_blocks = [b for b in page_blocks if b['match_status'] == 'matched']
        elif status_filter in ['pending', 'inactive', 'mismatch', 'disabled', 'not_in_zabbix']:
            filtered_blocks = [b for b in page_blocks if b['match_status'] == 'mismatch']
        else:
            filtered_blocks = page_blocks

        page_obj.object_list = filtered_blocks

        # Calculate counts for Top Cards
        try:
            z_count_res = api.call('host.get', {'countOutput': True})
            if isinstance(z_count_res, (int, str)) and str(z_count_res).isdigit():
                z_total = int(z_count_res)
                matched_count = page_matched_count if status_filter else min(total_devices, z_total)
                mismatch_count = page_mismatch_count if status_filter else max(0, total_devices - matched_count)
            else:
                matched_count = page_matched_count
                mismatch_count = page_mismatch_count
        except Exception:
            matched_count = page_matched_count
            mismatch_count = page_mismatch_count

        headers = [
            "Source",
            "Device Name",
            "Primary IP",
            "Status",
            "Role / Host Groups",
            "Attached Templates",
            "Zabbix Settings & SNMP",
            "Match Status & Action"
        ]

        context = {
            'title': 'Hosts',
            'headers': headers,
            'page_obj': page_obj,
            'per_page': per_page_param if per_page_param.lower() == 'all' else per_page,
            'total_devices': total_devices,
            'synced_devices': matched_count,
            'devices_to_sync': mismatch_count,
            'status_filter': status_filter,
            'has_status': True,
            'is_hosts_view': True,
            'q': q,
            'error': zabbix_error,
        }
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixPushDeviceView(View):
    def post(self, request):
        device_name = request.POST.get('device_name')
        if not device_name:
            messages.error(request, "Missing Device name.")
            return redirect('plugins:netbox_zabbix:hosts')

        from dcim.models import Device
        dev = Device.objects.filter(name=device_name).select_related(
            'role', 'primary_ip4', 'primary_ip6'
        ).first()
        if not dev:
            messages.error(request, f"NetBox device '{device_name}' not found.")
            return redirect('plugins:netbox_zabbix:hosts')

        success, msg = push_device_to_zabbix(dev, reason="Manual Push from UI")

        if success:
            messages.success(request, f"✅ Successfully pushed '{device_name}' to Zabbix! ({msg})")
        else:
            # User-friendly error messages based on guard condition
            if "No Primary IP" in msg:
                messages.error(request, f"❌ Cannot push '{device_name}': No Primary IP assigned in NetBox.")
            elif "No Zabbix settings" in msg:
                messages.error(request, f"❌ Cannot push '{device_name}': No Zabbix settings configured for its role. Go to Host Groups → Add Zabbix Settings.")
            elif "SNMP type configured but no SNMP" in msg:
                messages.error(request, f"❌ Cannot push '{device_name}': SNMP interface selected but no SNMP Community or SNMPv3 credentials set on the device.")
            else:
                messages.error(request, f"❌ Failed to push '{device_name}' to Zabbix: {msg}")

        return redirect('plugins:netbox_zabbix:hosts')



class ZabbixSyncRoleView(View):
    def post(self, request):
        host_id = request.POST.get('host_id')
        role_name = request.POST.get('role_name')
        
        if not host_id or not role_name:
            messages.error(request, "Missing host ID or NetBox Device Role name.")
            return redirect('plugins:netbox_zabbix:hosts')
            
        api = ZabbixAPI()
        
        group_id = get_or_create_hostgroup_id(api, role_name)
        if not group_id:
            messages.error(request, f"Could not create or find Zabbix Host Group '{role_name}'.")
            return redirect('plugins:netbox_zabbix:hosts')
            
        mass_res = api.call("host.massadd", {
            "hosts": [{"hostid": host_id}],
            "groups": [{"groupid": group_id}]
        })
        
        if isinstance(mass_res, dict) and "error" in mass_res:
            messages.error(request, f"Failed to assign Host Group in Zabbix: {mass_res['error']}")
        else:
            messages.success(request, f"Successfully created/assigned Zabbix Host Group '{role_name}' for host ID {host_id}!")
            
        return redirect('plugins:netbox_zabbix:hosts')


class ZabbixBulkPushView(View):
    """Bulk push all devices for a specific role to Zabbix in batches."""
    
    def get(self, request):
        """Show bulk push page with roles and device counts."""
        from dcim.models import Device, DeviceRole
        from .template_storage import get_role_zabbix_settings
        
        api = ZabbixAPI()
        
        # Get all roles that have Zabbix settings configured
        from .models import ZabbixHostGroupTemplate
        configured_roles = ZabbixHostGroupTemplate.objects.all()
        
        roles_data = []
        for cfg in configured_roles:
            role_name = cfg.role_name
            settings = get_role_zabbix_settings(role_name)
            device_count = Device.objects.filter(role__name=role_name).count()
            active_count = Device.objects.filter(role__name=role_name, primary_ip4__isnull=False).count()
            
            if_type = settings.get('interface_type')
            px_id = settings.get('proxy_id') or '0'
            tmpls = settings.get('templates', [])
            is_ready = bool(if_type) and len(tmpls) > 0
            
            missing_items = []
            if not if_type:
                missing_items.append("Interface Type")
            if not tmpls:
                missing_items.append("Templates")

            roles_data.append({
                'role_name': role_name,
                'device_count': device_count,
                'pushable_count': active_count,
                'interface_type': if_type or 'N/A',
                'template_count': len(tmpls),
                'proxy_name': settings.get('proxy_name') or ('Server' if px_id == '0' else 'N/A'),
                'is_ready': is_ready,
                'missing_reason': f"Missing {', '.join(missing_items)}" if missing_items else "",
            })
        
        # Auto-sync state
        from .models import ZabbixSyncState
        sync_enabled = ZabbixSyncState.is_enabled()
        
        return render(request, 'netbox_zabbix/bulk_push.html', {
            'roles_data': roles_data,
            'sync_enabled': sync_enabled,
            'title': 'Bulk Push to Zabbix',
        })
    
    def post(self, request):
        """Execute bulk push for a role. Returns JSON progress result."""
        import json
        from dcim.models import Device
        from .signals import push_device_to_zabbix
        from .template_storage import get_role_zabbix_settings
        from .signals import build_snmp_details, get_or_create_hostgroup_id, execute_zabbix_host_save, build_zabbix_tags
        
        action = request.POST.get('action', 'push')
        
        # Handle toggle auto-sync
        if action == 'toggle_sync':
            from .models import ZabbixSyncState
            state = ZabbixSyncState.get_state()
            state.auto_sync_enabled = not state.auto_sync_enabled
            state.save()
            new_state = 'enabled' if state.auto_sync_enabled else 'disabled'
            return JsonResponse({'success': True, 'sync_enabled': state.auto_sync_enabled, 'message': f'Auto-sync {new_state}'})
        
        role_name = request.POST.get('role_name')
        if not role_name:
            return JsonResponse({'success': False, 'error': 'No role specified'})
        
        settings = get_role_zabbix_settings(role_name)
        if_type_str = settings.get('interface_type')
        mapped_tmpls = settings.get('templates', [])
        proxy_id = settings.get('proxy_id') or '0'
        
        # Requirement 3: Sync is possible ONLY if Type and Template are binded
        if not (if_type_str and mapped_tmpls):
            missing = []
            if not if_type_str:
                missing.append("Interface Type")
            if not mapped_tmpls:
                missing.append("Templates")
            return JsonResponse({
                'success': False,
                'error': f"Role '{role_name}' is incomplete. Sync requires Interface Type and at least 1 Template (Missing: {', '.join(missing)})."
            })

        # Option A: Get Role Summary for Chunked Progress Bar
        if action == 'get_role_summary':
            devices_qs = Device.objects.filter(role__name=role_name).values('id', 'name')
            device_list = [{'id': d['id'], 'name': d['name']} for d in devices_qs if d['name']]
            return JsonResponse({
                'success': True,
                'role_name': role_name,
                'total': len(device_list),
                'devices': device_list
            })

        tmpl_payload = [{'templateid': str(t['id'])} for t in mapped_tmpls]
        proxy_id_str = str(proxy_id)
        
        api = ZabbixAPI()
        hostgroup_id = get_or_create_hostgroup_id(api, role_name)
        
        # Fetch specified devices or ALL devices for this role
        device_ids_raw = request.POST.get('device_ids')
        if device_ids_raw:
            try:
                device_ids = json.loads(device_ids_raw)
            except Exception:
                device_ids = [int(x) for x in device_ids_raw.split(',') if x.strip().isdigit()]
            devices = list(Device.objects.filter(id__in=device_ids).select_related(
                'role', 'site', 'primary_ip4', 'primary_ip6'
            ).prefetch_related('site__tags', 'tags'))
        else:
            devices = list(Device.objects.filter(role__name=role_name).select_related(
                'role', 'site', 'primary_ip4', 'primary_ip6'
            ).prefetch_related('site__tags', 'tags'))
        
        # Determine interface type numbers
        if if_type_str == 'Agent':
            if_type_num, port_num = 1, '10050'
        elif if_type_str == 'IPMI':
            if_type_num, port_num = 3, '623'
        elif if_type_str == 'JMX':
            if_type_num, port_num = 4, '12345'
        else:
            if_type_num, port_num = 2, '161'
        
        # Build payloads for all valid devices
        create_payloads = []
        update_payloads = []
        skipped = []
        
        # Step 1: Get ALL existing Zabbix hosts for this role in ONE API call
        device_names = [d.name for d in devices if d.name]
        existing_hosts_raw = []
        CHUNK = 500
        for i in range(0, len(device_names), CHUNK):
            chunk_names = device_names[i:i+CHUNK]
            result = api.call('host.get', {
                'filter': {'host': chunk_names},
                'selectInterfaces': ['interfaceid', 'type', 'main', 'ip', 'port'],
                'output': ['hostid', 'host', 'name']
            })
            if isinstance(result, list):
                existing_hosts_raw.extend(result)
        
        existing_map = {h['host']: h for h in existing_hosts_raw}  # host tech name → host data
        
        # Step 2: Build payloads
        for device in devices:
            device_name = device.name
            if not device_name:
                skipped.append({'name': '(unnamed)', 'reason': 'No name'})
                continue
            
            # Get IP
            nb_ip = None
            if device.primary_ip4:
                nb_ip = str(device.primary_ip4.address).split('/')[0]
            elif device.primary_ip6:
                nb_ip = str(device.primary_ip6.address).split('/')[0]
            
            if not nb_ip:
                skipped.append({'name': device_name, 'reason': 'No Primary IP'})
                continue
            
            # SNMP check
            cf_data = getattr(device, 'custom_field_data', {}) or {}
            details_payload = None
            if if_type_str == 'SNMP':
                details_payload, _, _ = build_snmp_details(cf_data)
                if details_payload is None:
                    skipped.append({'name': device_name, 'reason': 'No SNMP credentials'})
                    continue
            
            # Device status
            nb_status = str(getattr(device.status, 'value', None) or getattr(device, 'status', 'active') or 'active').lower()
            zabbix_status = 0 if nb_status == 'active' else 1
            
            # Build tags from device site and device
            tags_payload = build_zabbix_tags(device)

            # Build interface
            if_payload = {
                'type': if_type_num,
                'main': 1,
                'useip': 1,
                'ip': nb_ip,
                'dns': '',
                'port': port_num
            }
            if details_payload:
                if_payload['details'] = details_payload
            
            if device_name in existing_map:
                existing = existing_map[device_name]
                hid = existing['hostid']
                ifaces = existing.get('interfaces', [])
                if isinstance(ifaces, list) and len(ifaces) > 0:
                    main_iface = ifaces[0]
                    for ifc in ifaces:
                        if str(ifc.get('main')) == '1':
                            main_iface = ifc
                            break
                    if 'interfaceid' in main_iface:
                        if_payload['interfaceid'] = main_iface['interfaceid']
                
                upd = {
                    'hostid': hid,
                    'groups': [{'groupid': hostgroup_id}],
                    'interfaces': [if_payload],
                    'status': zabbix_status,
                    'tags': tags_payload
                }
                if tmpl_payload:
                    upd['templates'] = tmpl_payload
                update_payloads.append((device_name, upd))
            else:
                crt = {
                    'host': device_name,
                    'name': device_name,
                    'interfaces': [if_payload],
                    'groups': [{'groupid': hostgroup_id}],
                    'status': zabbix_status,
                    'tags': tags_payload
                }
                if tmpl_payload:
                    crt['templates'] = tmpl_payload
                create_payloads.append((device_name, crt))
        
        # Step 3: Batch create — Zabbix supports array of hosts in one call
        created_ok = []
        created_fail = []
        BATCH = 100
        
        for i in range(0, len(create_payloads), BATCH):
            batch = create_payloads[i:i+BATCH]
            names = [b[0] for b in batch]
            payloads = [b[1] for b in batch]
            
            # Apply monitoring mode to each
            for p in payloads:
                from .signals import apply_monitoring_mode
                apply_monitoring_mode(p, proxy_id)
            
            res = api.call('host.create', payloads)
            if isinstance(res, dict) and 'error' in res:
                # Try one by one with fallback for older Zabbix versions
                for name, p in batch:
                    from .signals import execute_zabbix_host_save
                    r = execute_zabbix_host_save(api, False, p, proxy_id)
                    if isinstance(r, dict) and 'error' in r:
                        created_fail.append({'name': name, 'reason': str(r['error'])})
                    else:
                        created_ok.append(name)
            else:
                created_ok.extend(names)
        
        # Step 4: Updates (individual — Zabbix host.update is per-host)
        updated_ok = []
        updated_fail = []
        for name, upd in update_payloads:
            from .signals import execute_zabbix_host_save
            res = execute_zabbix_host_save(api, True, upd, proxy_id)
            if isinstance(res, dict) and 'error' in res:
                updated_fail.append({'name': name, 'reason': str(res['error'])})
            else:
                updated_ok.append(name)
        
        return JsonResponse({
            'success': True,
            'role_name': role_name,
            'total': len(devices),
            'created': len(created_ok),
            'updated': len(updated_ok),
            'skipped': len(skipped),
            'failed': len(created_fail) + len(updated_fail),
            'skipped_details': skipped[:50],
            'failed_details': (created_fail + updated_fail)[:50],
            'created_names': created_ok[:20],
            'updated_names': updated_ok[:20],
        })
