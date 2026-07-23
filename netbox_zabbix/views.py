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
        
        # 1. NetBox Devices with Primary IP assigned (Source of Truth)
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

        # 2. Fetch Zabbix Hosts & Proxies
        zabbix_hosts = api.get_hosts()
        
        proxy_map = {}
        try:
            proxies = api.get_proxies()
            if isinstance(proxies, list):
                for p in proxies:
                    p_id = str(p.get("proxyid", ""))
                    p_name = p.get("name") or p.get("host")
                    if p_id and p_name:
                        proxy_map[p_id] = p_name
        except Exception:
            pass

        zabbix_name_map = {} # Lowercase Name/Host -> List of Zabbix host objects
        zabbix_ip_map = {}   # IP Address -> List of Zabbix host objects
        
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

        # 3. Dual-Validation Verification Engine
        all_rows = []
        matched_count = 0
        mismatch_count = 0

        total_devices = qs.count()

        for dev in qs.iterator():
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

            zabbix_host_disp = "—"
            zabbix_ip_disp = "—"
            zabbix_status_disp = "—"
            protocol_str = "—"
            monitored_by_str = "—"

            match_status_type = "mismatch"
            match_status_cell = {"type": "not_in_zabbix", "text": "Not in Zabbix"}
            sync_cell = {"type": "none", "text": "—"}

            # Search for a host matching BOTH Name and Primary IP
            perfect_match_host = None

            for zh in zh_name_candidates:
                zh_interfaces = zh.get("interfaces", [])
                if isinstance(zh_interfaces, list):
                    for iface in zh_interfaces:
                        if isinstance(iface, dict) and (iface.get("ip") or "").strip() == nb_ip:
                            perfect_match_host = zh
                            break
                if perfect_match_host:
                    break

            if not perfect_match_host:
                for zh in zh_ip_candidates:
                    c_tech = (zh.get("host") or "").strip().lower()
                    c_vis = (zh.get("name") or "").strip().lower()
                    if nb_name_lower in [c_tech, c_vis]:
                        perfect_match_host = zh
                        break

            if perfect_match_host:
                # BOTH Device Name and Primary IP exist & match in Zabbix!
                c_tech = perfect_match_host.get("host", "")
                c_vis = perfect_match_host.get("name", "")
                zabbix_host_disp = c_vis if c_vis else c_tech
                zabbix_ip_disp = nb_ip

                z_st = str(perfect_match_host.get("status", "0"))
                zabbix_status_disp = "Monitored" if z_st == "0" else "Disabled"

                interfaces = perfect_match_host.get("interfaces", [])
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break
                    if_type = str(main_iface.get("type", "1"))
                    protocol_str = "SNMP" if if_type == "2" else "IPMI" if if_type == "3" else "JMX" if if_type == "4" else "Agent"

                proxy_id = str(perfect_match_host.get("proxyid") or "0")
                proxy_group_id = str(perfect_match_host.get("proxy_groupid") or "0")
                monitored_by = str(perfect_match_host.get("monitored_by") or "0")

                if (monitored_by == "1" or proxy_id != "0") and proxy_id in proxy_map:
                    monitored_by_str = f"Proxy: {proxy_map[proxy_id]}"
                elif proxy_id != "0":
                    monitored_by_str = f"Proxy (ID {proxy_id})"
                elif monitored_by == "2" or proxy_group_id != "0":
                    monitored_by_str = f"Proxy Group (ID {proxy_group_id})"
                else:
                    monitored_by_str = "Server"

                match_status_type = "matched"
                match_status_cell = {"type": "matched", "text": "Matched"}
                matched_count += 1

                zabbix_groups = perfect_match_host.get("hostgroups", []) or perfect_match_host.get("groups", [])
                zabbix_group_names = [g.get("name") for g in zabbix_groups if isinstance(g, dict) and g.get("name")]
                role_synced = any(nb_role.lower() == zg.lower() for zg in zabbix_group_names) if nb_role != "—" else False

                if role_synced:
                    sync_cell = {"type": "synced", "text": "Synced"}
                elif nb_role != "—":
                    sync_cell = {"type": "sync_button", "host_id": perfect_match_host.get("hostid"), "role_name": nb_role}

            elif len(zh_name_candidates) > 0:
                # Name exists in Zabbix, but IP differs
                zh_target = zh_name_candidates[0]
                c_tech = zh_target.get("host", "")
                c_vis = zh_target.get("name", "")
                zabbix_host_disp = c_vis if c_vis else c_tech

                main_z_ip = "No IP"
                interfaces = zh_target.get("interfaces", [])
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_z_ip = interfaces[0].get("ip", "No IP")
                    for iface in interfaces:
                        if isinstance(iface, dict) and str(iface.get("main")) == "1":
                            main_z_ip = iface.get("ip", "No IP")
                            break
                zabbix_ip_disp = main_z_ip

                z_st = str(zh_target.get("status", "0"))
                zabbix_status_disp = "Monitored" if z_st == "0" else "Disabled"

                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break
                    if_type = str(main_iface.get("type", "1"))
                    protocol_str = "SNMP" if if_type == "2" else "IPMI" if if_type == "3" else "JMX" if if_type == "4" else "Agent"

                proxy_id = str(zh_target.get("proxyid") or "0")
                proxy_group_id = str(zh_target.get("proxy_groupid") or "0")
                monitored_by = str(zh_target.get("monitored_by") or "0")

                if (monitored_by == "1" or proxy_id != "0") and proxy_id in proxy_map:
                    monitored_by_str = f"Proxy: {proxy_map[proxy_id]}"
                elif proxy_id != "0":
                    monitored_by_str = f"Proxy (ID {proxy_id})"
                elif monitored_by == "2" or proxy_group_id != "0":
                    monitored_by_str = f"Proxy Group (ID {proxy_group_id})"
                else:
                    monitored_by_str = "Server"

                match_status_type = "mismatch"
                match_status_cell = {"type": "ip_mismatch", "text": f"IP Mismatch ({main_z_ip})"}
                mismatch_count += 1

            elif len(zh_ip_candidates) > 0:
                # Primary IP exists in Zabbix, but under a different Device Name
                zh_target = zh_ip_candidates[0]
                c_tech = zh_target.get("host", "")
                c_vis = zh_target.get("name", "")
                z_host_name = c_vis if c_vis else c_tech
                
                zabbix_host_disp = z_host_name
                zabbix_ip_disp = nb_ip

                z_st = str(zh_target.get("status", "0"))
                zabbix_status_disp = "Monitored" if z_st == "0" else "Disabled"

                interfaces = zh_target.get("interfaces", [])
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break
                    if_type = str(main_iface.get("type", "1"))
                    protocol_str = "SNMP" if if_type == "2" else "IPMI" if if_type == "3" else "JMX" if if_type == "4" else "Agent"

                proxy_id = str(zh_target.get("proxyid") or "0")
                proxy_group_id = str(zh_target.get("proxy_groupid") or "0")
                monitored_by = str(zh_target.get("monitored_by") or "0")

                if (monitored_by == "1" or proxy_id != "0") and proxy_id in proxy_map:
                    monitored_by_str = f"Proxy: {proxy_map[proxy_id]}"
                elif proxy_id != "0":
                    monitored_by_str = f"Proxy (ID {proxy_id})"
                elif monitored_by == "2" or proxy_group_id != "0":
                    monitored_by_str = f"Proxy Group (ID {proxy_group_id})"
                else:
                    monitored_by_str = "Server"

                match_status_type = "mismatch"
                match_status_cell = {"type": "name_mismatch", "text": f"Name Mismatch ({z_host_name})"}
                mismatch_count += 1

            else:
                # Neither Device Name nor Primary IP exists in Zabbix
                match_status_type = "mismatch"
                match_status_cell = {"type": "not_in_zabbix", "text": "Not in Zabbix"}
                mismatch_count += 1

            row = [
                nb_name,
                nb_ip,
                nb_status,
                nb_role,
                zabbix_host_disp,
                zabbix_ip_disp,
                zabbix_status_disp,
                protocol_str,
                monitored_by_str,
                match_status_cell,
                sync_cell
            ]
            row_match_type = match_status_type
            all_rows.append((row, row_match_type))

        # 4. Filter rows if card clicked
        status_filter = request.GET.get('status', '').strip().lower()
        if status_filter in ['synced', 'active', 'matched']:
            filtered_rows = [r[0] for r in all_rows if r[1] == 'matched']
        elif status_filter in ['pending', 'inactive', 'mismatch', 'disabled']:
            filtered_rows = [r[0] for r in all_rows if r[1] == 'mismatch']
        else:
            filtered_rows = [r[0] for r in all_rows]

        # 5. Pagination
        per_page_param = request.GET.get('per_page', '50')
        page_param = request.GET.get('page', '1')

        try:
            per_page = int(per_page_param) if per_page_param.lower() != 'all' else len(filtered_rows)
            if per_page <= 0:
                per_page = 50
        except ValueError:
            per_page = 50

        paginator = Paginator(filtered_rows, per_page if per_page > 0 else 50)
        try:
            page_obj = paginator.page(page_param)
        except Exception:
            page_obj = paginator.page(1)

        headers = [
            "NetBox Device Name",
            "NetBox Primary IP",
            "NetBox Status",
            "NetBox Device Role",
            "Zabbix Host Name",
            "Zabbix Primary IP",
            "Zabbix Status",
            "Protocol",
            "Monitored By",
            "Match Status",
            "Role Sync"
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
