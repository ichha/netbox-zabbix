from django.views.generic import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
import logging
from .zabbix_api import ZabbixAPI

logger = logging.getLogger('netbox.plugins.netbox_zabbix')


def process_table_data(request, items, headers, title, default_per_page=50, has_status=True):
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

    return {
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
                proxy_id = p.get("proxyid", "-")
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
        
        if isinstance(zabbix_groups, dict) and "error" in zabbix_groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Host Groups', 'error': zabbix_groups["error"]
            })

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

        headers = ["Group ID", "Zabbix Host Group Name", "NetBox Device Role", "Sync Status"]
        items = []
        processed_zabbix_lower = set()

        for role in netbox_roles:
            r_name = role.name
            r_lower = r_name.strip().lower()

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
                status_cell
            ])

        if isinstance(zabbix_groups, list):
            for g in zabbix_groups:
                g_name = g.get("name", "")
                if g_name.strip().lower() not in processed_zabbix_lower:
                    items.append([
                        g.get("groupid", "-"),
                        g_name,
                        "—",
                        {"type": "none", "text": "Zabbix Only"}
                    ])

        context = process_table_data(request, items, headers, 'Host Groups', has_status=False)
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixCreateHostGroupView(View):
    def post(self, request):
        role_name = request.POST.get('role_name')
        
        if not role_name:
            messages.error(request, "Missing NetBox Device Role name.")
            return redirect('plugins:netbox_zabbix:hostgroups')
            
        api = ZabbixAPI()
        
        groups = api.call("hostgroup.get", {"filter": {"name": role_name}})
        if isinstance(groups, list) and len(groups) > 0:
            messages.info(request, f"Host Group '{role_name}' already exists in Zabbix.")
            return redirect('plugins:netbox_zabbix:hostgroups')
            
        create_res = api.call("hostgroup.create", {"name": role_name})
        if isinstance(create_res, dict) and "groupids" in create_res and len(create_res["groupids"]) > 0:
            messages.success(request, f"Successfully created Host Group '{role_name}' in Zabbix (ID {create_res['groupids'][0]})!")
        elif isinstance(create_res, dict) and "error" in create_res:
            messages.error(request, f"Failed to create Host Group in Zabbix: {create_res['error']}")
        else:
            messages.error(request, f"Unable to create Host Group '{role_name}' in Zabbix.")
            
        return redirect('plugins:netbox_zabbix:hostgroups')


class ZabbixHostsView(View):
    def get(self, request):
        api = ZabbixAPI()
        
        # 1. Base QuerySet: ONLY NetBox devices with Primary IP assigned!
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

        total_devices = qs.count()

        per_page_param = request.GET.get('per_page', '50')
        page_param = request.GET.get('page', '1')

        try:
            per_page = int(per_page_param) if per_page_param.lower() != 'all' else total_devices
            if per_page <= 0:
                per_page = 50
        except ValueError:
            per_page = 50

        paginator = Paginator(qs, per_page if per_page > 0 else 50)
        try:
            page_obj = paginator.page(page_param)
        except Exception:
            page_obj = paginator.page(1)

        # 2. Fetch Zabbix Hosts for lightweight matching
        zabbix_hosts = api.get_hosts()
        
        zabbix_name_map = {}
        zabbix_ip_map = {}
        if isinstance(zabbix_hosts, list):
            for zh in zabbix_hosts:
                zh_name = zh.get("host", "").strip()
                zh_vis_name = zh.get("name", "").strip()
                if zh_name:
                    zabbix_name_map[zh_name.lower()] = zh
                if zh_vis_name:
                    zabbix_name_map[zh_vis_name.lower()] = zh
                    
                interfaces = zh.get("interfaces", [])
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break
                    zip_addr = main_iface.get("ip", "").strip()
                    if zip_addr and zip_addr not in ["0.0.0.0", "127.0.0.1"]:
                        zabbix_ip_map[zip_addr] = zh

        # 3. Calculate exact Matched count for NetBox devices against Zabbix
        matched_count = 0
        for dev in qs:
            nb_name = (dev.name or "").strip().lower()
            nb_ip = ""
            if dev.primary_ip4:
                nb_ip = str(dev.primary_ip4.address).split('/')[0]
            elif dev.primary_ip6:
                nb_ip = str(dev.primary_ip6.address).split('/')[0]

            if (nb_name and nb_name in zabbix_name_map) or (nb_ip and nb_ip in zabbix_ip_map):
                matched_count += 1

        unmatched_count = max(0, total_devices - matched_count)

        headers = [
            "NetBox Device Name",
            "NetBox Primary IP",
            "NetBox Status",
            "NetBox Device Role",
            "Zabbix Host Name",
            "Zabbix Primary IP",
            "Match Status",
            "Role Sync"
        ]

        # 4. Build table rows ONLY for current page
        page_devices = list(page_obj.object_list)
        page_rows = []

        for dev in page_devices:
            nb_name = dev.name or f"Device-{dev.pk}"
            nb_ip = "—"
            if dev.primary_ip4:
                nb_ip = str(dev.primary_ip4.address).split('/')[0]
            elif dev.primary_ip6:
                nb_ip = str(dev.primary_ip6.address).split('/')[0]

            nb_status = str(dev.status).capitalize() if dev.status else "Active"
            nb_role = dev.role.name if dev.role else "—"

            zh_by_name = zabbix_name_map.get(nb_name.lower())
            zh_by_ip = zabbix_ip_map.get(nb_ip) if nb_ip != "—" else None

            zabbix_host_disp = "—"
            zabbix_ip_disp = "—"
            match_status_cell = {"type": "not_in_zabbix", "text": "Not in Zabbix"}
            sync_cell = {"type": "none", "text": "—"}

            if zh_by_name and zh_by_ip and (zh_by_name.get("hostid") == zh_by_ip.get("hostid")):
                zabbix_host_disp = zh_by_name.get("host", "-")
                zabbix_ip_disp = nb_ip
                match_status_cell = {"type": "matched", "text": "Matched"}
                
                zabbix_groups = zh_by_name.get("hostgroups", []) or zh_by_name.get("groups", [])
                zabbix_group_names = [g.get("name") for g in zabbix_groups if isinstance(g, dict) and g.get("name")]
                role_synced = any(nb_role.lower() == zg.lower() for zg in zabbix_group_names) if nb_role != "—" else False
                
                if role_synced:
                    sync_cell = {"type": "synced", "text": "Synced"}
                elif nb_role != "—":
                    sync_cell = {"type": "sync_button", "host_id": zh_by_name.get("hostid"), "role_name": nb_role}

            elif zh_by_name:
                zabbix_host_disp = zh_by_name.get("host", "-")
                zip_found = "No IP"
                interfaces = zh_by_name.get("interfaces", [])
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    zip_found = interfaces[0].get("ip", "No IP")
                zabbix_ip_disp = zip_found
                match_status_cell = {"type": "ip_mismatch", "text": f"IP Mismatch ({zip_found})"}

            elif zh_by_ip:
                z_name_found = zh_by_ip.get("host", "Unknown")
                zabbix_host_disp = z_name_found
                zabbix_ip_disp = nb_ip
                match_status_cell = {"type": "name_mismatch", "text": f"Name Mismatch ({z_name_found})"}

            else:
                match_status_cell = {"type": "not_in_zabbix", "text": "Not in Zabbix"}

            page_rows.append([
                nb_name,
                nb_ip,
                nb_status,
                nb_role,
                zabbix_host_disp,
                zabbix_ip_disp,
                match_status_cell,
                sync_cell
            ])

        page_obj.object_list = page_rows

        context = {
            'title': 'Hosts',
            'headers': headers,
            'page_obj': page_obj,
            'per_page': per_page_param if per_page_param.lower() == 'all' else per_page,
            'total_devices': total_devices,
            'synced_devices': matched_count,
            'devices_to_sync': unmatched_count,
            'has_status': True,
            'q': q,
        }
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixSyncRoleView(View):
    def post(self, request):
        host_id = request.POST.get('host_id')
        role_name = request.POST.get('role_name')
        
        if not host_id or not role_name:
            messages.error(request, "Missing host ID or NetBox Device Role name.")
            return redirect('plugins:netbox_zabbix:hosts')
            
        api = ZabbixAPI()
        
        groups = api.call("hostgroup.get", {"filter": {"name": role_name}})
        group_id = None
        
        if isinstance(groups, list) and len(groups) > 0:
            group_id = groups[0].get("groupid")
        else:
            create_res = api.call("hostgroup.create", {"name": role_name})
            if isinstance(create_res, dict) and "groupids" in create_res and len(create_res["groupids"]) > 0:
                group_id = create_res["groupids"][0]
            elif isinstance(create_res, dict) and "error" in create_res:
                messages.error(request, f"Failed to create Zabbix Host Group '{role_name}': {create_res['error']}")
                return redirect('plugins:netbox_zabbix:hosts')
                
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
