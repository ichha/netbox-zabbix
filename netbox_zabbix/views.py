from django.views.generic import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
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
from .signals import build_snmp_details, get_or_create_hostgroup_id, execute_zabbix_host_save

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
        
        hosts = api.get_hosts()
        templates = api.get_templates()
        proxies = api.get_proxies()
        hostgroups = api.get_host_groups()
        macros = api.get_macros()
        tags = api.get_tags()
        
        host_count = len(hosts) if isinstance(hosts, list) else 0
        template_count = len(templates) if isinstance(templates, list) else 0
        proxy_count = len(proxies) if isinstance(proxies, list) else 0
        hostgroup_count = len(hostgroups) if isinstance(hostgroups, list) else 0
        macro_count = len(macros) if isinstance(macros, list) else 0
        tag_count = len(tags) if isinstance(tags, list) else 0
        
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

        messages.success(request, f"Successfully saved Zabbix Settings for '{role_name}'!")
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
        else:
            messages.error(request, f"Unable to create Host Group '{role_name}' in Zabbix.")
            
        return redirect('plugins:netbox_zabbix:hostgroups')


class ZabbixHostsView(View):
    def get(self, request):
        api = ZabbixAPI()
        
        # 1. NetBox Devices with Primary IP assigned
        from dcim.models import Device

        qs = Device.objects.filter(
            Q(primary_ip4__isnull=False) | Q(primary_ip6__isnull=False)
        ).select_related('role', 'primary_ip4', 'primary_ip6')

        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(primary_ip4__address__icontains=q) |
                Q(role__name__icontains=q)
            )

        # 2. Fetch Zabbix Hosts, Proxies, Global Macros, and Template-Host links
        zabbix_hosts = api.get_hosts()
        zabbix_error = None
        if isinstance(zabbix_hosts, dict) and "error" in zabbix_hosts:
            zabbix_error = zabbix_hosts["error"]
            zabbix_hosts = []
        
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

        try:
            p_groups = api.get_proxy_groups()
            if isinstance(p_groups, list):
                for pg in p_groups:
                    pg_id = str(pg.get("proxy_groupid") or "")
                    pg_name = pg.get("name")
                    if pg_id and pg_name:
                        proxy_map[f"group_{pg_id}"] = f"Proxy Group: {pg_name}"
        except Exception:
            pass

        global_macros = {}
        try:
            g_macs = api.get_macros()
            if isinstance(g_macs, list):
                for gm in g_macs:
                    m_key = gm.get("macro", "").strip()
                    m_val = gm.get("value", "").strip()
                    if m_key:
                        global_macros[m_key] = m_val
        except Exception:
            pass

        host_template_map = {}
        try:
            raw_tmpl_hosts = api.get_templates_with_hosts()
            if isinstance(raw_tmpl_hosts, list):
                for tmpl in raw_tmpl_hosts:
                    if isinstance(tmpl, dict):
                        t_name = tmpl.get("name") or tmpl.get("host")
                        h_list = tmpl.get("hosts", [])
                        if t_name and isinstance(h_list, list):
                            for h_elem in h_list:
                                if isinstance(h_elem, dict):
                                    hid = str(h_elem.get("hostid", ""))
                                    if hid:
                                        if hid not in host_template_map:
                                            host_template_map[hid] = []
                                        if t_name not in host_template_map[hid]:
                                            host_template_map[hid].append(t_name)
        except Exception as e:
            logger.error(f"Error fetching templates with hosts: {e}")

        zabbix_name_map = {}
        zabbix_ip_map = {}
        
        if isinstance(zabbix_hosts, list):
            for zh in zabbix_hosts:
                zh_tech = (zh.get("host") or "").strip().lower()
                zh_vis = (zh.get("name") or "").strip().lower()
                
                if zh_tech:
                    if zh_tech not in zabbix_name_map:
                        zabbix_name_map[zh_tech] = []
                    zabbix_name_map[zh_tech].append(zh)
                    
                if zh_vis and zh_vis != zh_tech:
                    if zh_vis not in zabbix_name_map:
                        zabbix_name_map[zh_vis] = []
                    zabbix_name_map[zh_vis].append(zh)

                interfaces = zh.get("interfaces", [])
                if isinstance(interfaces, list):
                    for iface in interfaces:
                        if isinstance(iface, dict):
                            zip_addr = (iface.get("ip") or "").strip()
                            if zip_addr and zip_addr not in ["0.0.0.0", "127.0.0.1"]:
                                if zip_addr not in zabbix_ip_map:
                                    zabbix_ip_map[zip_addr] = []
                                if zh not in zabbix_ip_map[zip_addr]:
                                    zabbix_ip_map[zip_addr].append(zh)

        zabbix_names_set = set(zabbix_name_map.keys())
        zabbix_ips_set = set(zabbix_ip_map.keys())

        total_devices = qs.count()

        def is_dev_matched(dev):
            dev_n = (dev.name or "").strip().lower()
            dev_ip = ""
            if dev.primary_ip4:
                dev_ip = str(dev.primary_ip4.address).split('/')[0]
            elif dev.primary_ip6:
                dev_ip = str(dev.primary_ip6.address).split('/')[0]
            return (dev_n in zabbix_names_set) or (dev_ip and dev_ip in zabbix_ips_set)

        status_filter = request.GET.get('status', '').strip().lower()

        all_devices_list = list(qs.iterator())

        if status_filter in ['synced', 'active', 'matched']:
            filtered_devs = [dev for dev in all_devices_list if is_dev_matched(dev)]
            matched_count = len(filtered_devs)
            mismatch_count = total_devices - matched_count
        elif status_filter in ['pending', 'inactive', 'mismatch', 'disabled']:
            filtered_devs = [dev for dev in all_devices_list if not is_dev_matched(dev)]
            mismatch_count = len(filtered_devs)
            matched_count = total_devices - mismatch_count
        else:
            filtered_devs = all_devices_list
            matched_count = sum(1 for dev in all_devices_list if is_dev_matched(dev))
            mismatch_count = total_devices - mismatch_count

        filtered_count = len(filtered_devs)

        per_page_param = request.GET.get('per_page', '50')
        page_param = request.GET.get('page', '1')

        try:
            per_page = int(per_page_param) if per_page_param.lower() != 'all' else filtered_count
            if per_page <= 0:
                per_page = 50
        except ValueError:
            per_page = 50

        try:
            page_num = int(page_param)
            if page_num <= 0:
                page_num = 1
        except ValueError:
            page_num = 1

        start_idx = (page_num - 1) * per_page
        end_idx = start_idx + per_page
        page_slice = filtered_devs[start_idx:end_idx]

        page_blocks = []

        for dev in page_slice:
            nb_name = dev.name or f"Device-{dev.pk}"
            nb_ip = "—"
            if dev.primary_ip4:
                nb_ip = str(dev.primary_ip4.address).split('/')[0]
            elif dev.primary_ip6:
                nb_ip = str(dev.primary_ip6.address).split('/')[0]

            nb_status = str(dev.status).capitalize() if dev.status else "Active"
            nb_role = dev.role.name if dev.role else "—"

            nb_name_lower = nb_name.strip().lower()
            zh_name_candidates = zabbix_name_map.get(nb_name_lower, [])
            zh_ip_candidates = zabbix_ip_map.get(nb_ip, []) if nb_ip != "—" else []

            matching_zabbix_host = None

            for zh in zh_name_candidates:
                zh_interfaces = zh.get("interfaces", [])
                if isinstance(zh_interfaces, list):
                    for iface in zh_interfaces:
                        if isinstance(iface, dict) and (iface.get("ip") or "").strip() == nb_ip:
                            matching_zabbix_host = zh
                            break
                if matching_zabbix_host:
                    break

            if not matching_zabbix_host:
                for zh in zh_ip_candidates:
                    c_tech = (zh.get("host") or "").strip().lower()
                    c_vis = (zh.get("name") or "").strip().lower()
                    if nb_name_lower in [c_tech, c_vis]:
                        matching_zabbix_host = zh
                        break

            if not matching_zabbix_host and len(zh_name_candidates) > 0:
                matching_zabbix_host = zh_name_candidates[0]

            if not matching_zabbix_host and len(zh_ip_candidates) > 0:
                matching_zabbix_host = zh_ip_candidates[0]

            item = {
                "netbox_name": nb_name,
                "netbox_ip": nb_ip,
                "netbox_status": nb_status,
                "netbox_role": nb_role,
                "netbox_mapped_hostgroup": nb_role,
                "match_status": "matched" if matching_zabbix_host else "mismatch",
                "role_synced": False,
                "zabbix_exists": False,
                "zabbix_hostid": "",
                "zabbix_name": "—",
                "zabbix_ip": "—",
                "zabbix_port": "",
                "zabbix_status": "—",
                "zabbix_hostgroups": [],
                "zabbix_templates": [],
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

            if matching_zabbix_host:
                zh_target = matching_zabbix_host
                item["zabbix_exists"] = True
                zh_hid = str(zh_target.get("hostid", ""))
                item["zabbix_hostid"] = zh_hid
                
                c_tech = zh_target.get("host", "")
                c_vis = zh_target.get("name", "")
                item["zabbix_name"] = c_vis if c_vis else c_tech

                z_st = str(zh_target.get("status", "0"))
                item["zabbix_status"] = "Monitored" if z_st == "0" else "Disabled"

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

                if zh_hid and zh_hid in host_template_map:
                    for t_n in host_template_map[zh_hid]:
                        if t_n not in seen_t:
                            seen_t.add(t_n)
                            template_names.append(t_n)

                item["zabbix_templates"] = template_names

                z_groups = zh_target.get("hostgroups", []) or zh_target.get("groups", [])
                item["zabbix_hostgroups"] = [g.get("name") for g in z_groups if isinstance(g, dict) and g.get("name")]

                host_macro_map = dict(global_macros)
                host_macros_list = zh_target.get("macros", [])
                if isinstance(host_macros_list, list):
                    for hm in host_macros_list:
                        if isinstance(hm, dict):
                            m_k = hm.get("macro", "").strip()
                            m_v = hm.get("value", "").strip()
                            if m_k:
                                host_macro_map[m_k] = m_v

                interfaces = zh_target.get("interfaces", [])
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break

                    zip_addr = main_iface.get("ip")
                    item["zabbix_ip"] = zip_addr if zip_addr else nb_ip
                    item["zabbix_port"] = str(main_iface.get("port") or "")

                    t_val = str(main_iface.get("type", "1"))
                    item["zabbix_protocol"] = "SNMP" if t_val == "2" else "IPMI" if t_val == "3" else "JMX" if t_val == "4" else "Agent"

                    if t_val == "2":
                        details = main_iface.get("details", {})
                        if not isinstance(details, dict):
                            details = {}

                        ver = str(details.get("version") or main_iface.get("version") or "2")

                        if ver == "1":
                            item["snmp_version"] = "SNMPv1"
                        elif ver in ["2", "2c"]:
                            item["snmp_version"] = "SNMPv2c"
                        elif ver == "3":
                            item["snmp_version"] = "SNMPv3"
                        else:
                            item["snmp_version"] = "SNMPv2c"

                        raw_comm = None
                        if isinstance(details, dict):
                            raw_comm = details.get("community")
                        if not raw_comm:
                            raw_comm = main_iface.get("community")

                        if raw_comm:
                            if str(raw_comm).startswith("{$"):
                                resolved_comm = host_macro_map.get(raw_comm, raw_comm)
                            else:
                                resolved_comm = str(raw_comm)
                            item["snmp_community"] = resolved_comm
                        elif "{$SNMP_COMMUNITY}" in host_macro_map:
                            item["snmp_community"] = host_macro_map["{$SNMP_COMMUNITY}"]

                        if ver == "3":
                            item["snmpv3_context"] = details.get("contextname") or main_iface.get("contextname") or "—"
                            item["snmpv3_secname"] = details.get("securityname") or main_iface.get("securityname") or "—"
                            
                            s_lvl = str(details.get("securitylevel") or main_iface.get("securitylevel") or "0")
                            item["snmpv3_seclevel"] = "authPriv" if s_lvl == "2" else "authNoPriv" if s_lvl == "1" else "noAuthNoPriv"

                            a_pr = str(details.get("authprotocol") or main_iface.get("authprotocol") or "")
                            auth_map = {"0": "MD5", "1": "SHA1", "2": "SHA224", "3": "SHA256", "4": "SHA384", "5": "SHA512"}
                            item["snmpv3_authproto"] = auth_map.get(a_pr, a_pr) if a_pr else "—"

                            apass = details.get("authpassphrase") or main_iface.get("authpassphrase")
                            item["snmpv3_authpass"] = "••••••••" if apass else "—"

                            p_pr = str(details.get("privprotocol") or main_iface.get("privprotocol") or "")
                            priv_map = {"0": "DES", "1": "AES128", "2": "AES192", "3": "AES256", "4": "AES192C3GPP", "5": "AES256C3GPP"}
                            item["snmpv3_privproto"] = priv_map.get(p_pr, p_pr) if p_pr else "—"

                            ppass = details.get("privpassphrase") or main_iface.get("privpassphrase")
                            item["snmpv3_privpass"] = "••••••••" if ppass else "—"

                        max_rep = details.get("max_repetitions") or main_iface.get("max_repetitions")
                        if max_rep is not None and str(max_rep) != "":
                            item["snmp_max_repetitions"] = str(max_rep)

                        bulk_val = details.get("bulk") or main_iface.get("bulk")
                        if bulk_val is not None:
                            item["snmp_bulk"] = "Yes" if str(bulk_val) == "1" else "No"

                proxy_id = str(zh_target.get("proxyid") or "0")
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

                item["role_synced"] = any(nb_role.lower() == zg.lower() for zg in item["zabbix_hostgroups"]) if nb_role != "—" else False

            page_blocks.append(item)

        paginator = Paginator(filtered_devs, per_page if per_page > 0 else 50)
        try:
            page_obj = paginator.page(page_num)
        except Exception:
            page_obj = paginator.page(1)

        page_obj.object_list = page_blocks

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
        dev = Device.objects.filter(name=device_name).first()
        if not dev:
            messages.error(request, f"NetBox device '{device_name}' not found.")
            return redirect('plugins:netbox_zabbix:hosts')

        nb_ip = None
        if dev.primary_ip4:
            nb_ip = str(dev.primary_ip4.address).split('/')[0]
        elif dev.primary_ip6:
            nb_ip = str(dev.primary_ip6.address).split('/')[0]

        if not nb_ip:
            messages.error(request, f"Device '{device_name}' has no Primary IP assigned.")
            return redirect('plugins:netbox_zabbix:hosts')

        role_name = dev.role.name if dev.role else None

        api = ZabbixAPI()

        hostgroup_id = get_or_create_hostgroup_id(api, role_name)

        settings = get_role_zabbix_settings(role_name) if role_name else {}
        mapped_tmpls = settings.get("templates", [])
        tmpl_payload = [{"templateid": str(t["id"])} for t in mapped_tmpls]

        cf_data = getattr(dev, 'custom_field_data', {}) or {}

        if_type_str = settings.get("interface_type") or "SNMP"
        if if_type_str == "Agent":
            if_type_num = 1
            port_num = "10050"
            details_payload = None
            snmp_ver_name = "Agent"
        elif if_type_str == "IPMI":
            if_type_num = 3
            port_num = "623"
            details_payload = None
            snmp_ver_name = "IPMI"
        elif if_type_str == "JMX":
            if_type_num = 4
            port_num = "12345"
            details_payload = None
            snmp_ver_name = "JMX"
        else:
            if_type_num = 2
            port_num = "161"
            details_payload, _, snmp_ver_name = build_snmp_details(cf_data)

        if_payload = {
            "type": if_type_num,
            "main": 1,
            "useip": 1,
            "ip": nb_ip,
            "dns": "",
            "port": port_num
        }
        if details_payload:
            if_payload["details"] = details_payload

        interfaces_list = [if_payload]

        if if_type_str == "Agent":
            has_snmp_cf = bool(cf_data.get('snmp_community') or cf_data.get('security_name') or cf_data.get('security_level'))
            has_templates = bool(tmpl_payload)
            if has_snmp_cf or has_templates:
                snmp_details, _, _ = build_snmp_details(cf_data)
                snmp_if_payload = {
                    "type": 2,
                    "main": 1,
                    "useip": 1,
                    "ip": nb_ip,
                    "dns": "",
                    "port": "161",
                    "details": snmp_details
                }
                interfaces_list.append(snmp_if_payload)

        proxy_id = str(settings.get("proxy_id") or "0")

        existing = api.call("host.get", {
            "filter": {"host": device_name},
            "selectInterfaces": ["interfaceid", "type", "main", "ip", "port"]
        })
        if not (isinstance(existing, list) and len(existing) > 0):
            existing = api.call("host.get", {
                "filter": {"name": device_name},
                "selectInterfaces": ["interfaceid", "type", "main", "ip", "port"]
            })

        if isinstance(existing, list) and len(existing) > 0:
            hid = existing[0].get("hostid")
            existing_ifaces = existing[0].get("interfaces", [])
            if isinstance(existing_ifaces, list) and len(existing_ifaces) > 0:
                main_iface = existing_ifaces[0]
                for ifc in existing_ifaces:
                    if str(ifc.get("main")) == "1":
                        main_iface = ifc
                        break
                if "interfaceid" in main_iface:
                    if_payload["interfaceid"] = main_iface["interfaceid"]

            upd_params = {
                "hostid": hid,
                "groups": [{"groupid": hostgroup_id}],
                "interfaces": interfaces_list
            }
            if tmpl_payload:
                upd_params["templates"] = tmpl_payload

            res = execute_zabbix_host_save(api, True, upd_params, proxy_id)
            if isinstance(res, dict) and "error" in res:
                messages.error(request, f"Failed to update device '{device_name}' in Zabbix: {res['error']}")
            else:
                messages.success(request, f"Successfully updated device '{device_name}' in Zabbix ({if_type_str}) with {len(mapped_tmpls)} template(s)!")
        else:
            create_params = {
                "host": device_name,
                "name": device_name,
                "interfaces": interfaces_list,
                "groups": [{"groupid": hostgroup_id}]
            }
            if tmpl_payload:
                create_params["templates"] = tmpl_payload

            res = execute_zabbix_host_save(api, False, create_params, proxy_id)
            if isinstance(res, dict) and "error" in res:
                messages.error(request, f"Failed to push device '{device_name}' to Zabbix: {res['error']}")
            else:
                messages.success(request, f"Successfully pushed device '{device_name}' (IP: {nb_ip}) to Zabbix as {if_type_str} with {len(mapped_tmpls)} template(s)!")

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
