from django.views.generic import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
import logging
from .zabbix_api import ZabbixAPI

logger = logging.getLogger('netbox.plugins.netbox_zabbix')


def process_table_data(request, items, headers, title, default_per_page=50, has_status=True):
    total_devices = len(items)

    synced_devices = 0
    devices_to_sync = 0

    if has_status:
        for row in items:
            if any(str(cell).lower() in ['monitored', 'online', 'active'] for cell in row):
                synced_devices += 1
        devices_to_sync = total_devices - synced_devices

        status_filter = request.GET.get('status', '').strip().lower()
        if status_filter == 'synced' or status_filter == 'active':
            items = [row for row in items if any(str(cell).lower() in ['monitored', 'online', 'active'] for cell in row)]
        elif status_filter == 'pending' or status_filter == 'inactive':
            items = [row for row in items if not any(str(cell).lower() in ['monitored', 'online', 'active'] for cell in row)]
    else:
        status_filter = ""

    q = request.GET.get('q', '').strip()
    if q:
        items = [row for row in items if any(q.lower() in str(cell).lower() for cell in row)]

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

        # Fetch Zabbix groups dictionary
        zabbix_group_map = {}
        if isinstance(zabbix_groups, list):
            for g in zabbix_groups:
                g_name = g.get("name", "").strip()
                if g_name:
                    zabbix_group_map[g_name.lower()] = g

        # Fetch NetBox Device Roles
        netbox_roles = []
        try:
            from dcim.models import DeviceRole
            netbox_roles = list(DeviceRole.objects.all())
        except Exception as e:
            logger.error(f"Error fetching NetBox DeviceRoles: {e}")

        headers = ["Group ID", "Zabbix Host Group Name", "NetBox Device Role", "Sync Status"]
        items = []
        processed_zabbix_lower = set()

        # 1. Process NetBox Device Roles first (Plain text, no color!)
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
                r_name,  # Plain text, no color badge!
                status_cell
            ])

        # 2. Add remaining Zabbix Host Groups that are not NetBox Device Roles
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
        hosts = api.get_hosts()
        
        if isinstance(hosts, dict) and "error" in hosts:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Hosts', 'error': hosts["error"]
            })

        # Pre-build Proxy ID -> Name map for fast, error-free lookup
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

        # Query NetBox Device objects for Role comparison
        netbox_devices = {}
        netbox_ip_map = {}
        try:
            from dcim.models import Device
            for d in Device.objects.select_related('role', 'primary_ip4', 'primary_ip6').all():
                if d.name:
                    netbox_devices[d.name.lower()] = d
                if d.primary_ip4:
                    ip_clean = str(d.primary_ip4.address).split('/')[0]
                    netbox_ip_map[ip_clean] = d
        except Exception as e:
            logger.error(f"Error querying NetBox devices: {e}")

        headers = ["Host Name", "Primary IP", "NetBox Device Role", "Zabbix Hostgroups", "Protocol", "Monitored By", "Role Sync"]
        items = []
        if isinstance(hosts, list):
            for h in hosts:
                h_name = h.get("host", "-")
                v_name = h.get("name", "") or h_name
                host_id = h.get("hostid")
                status_str = "Monitored" if str(h.get("status")) == "0" else "Unmonitored"

                # 1. Interface & Protocol
                interfaces = h.get("interfaces", [])
                ip_str = "-"
                port_str = "-"
                protocol_str = "Agent"
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    main_iface = interfaces[0]
                    for iface in interfaces:
                        if str(iface.get("main")) == "1":
                            main_iface = iface
                            break
                    ip_str = main_iface.get("ip", "-") or "-"
                    port_str = main_iface.get("port", "-") or "-"
                    if_type = str(main_iface.get("type", "1"))
                    protocol_str = "SNMP" if if_type == "2" else "IPMI" if if_type == "3" else "JMX" if if_type == "4" else "Agent"

                # 2. Monitored By / Proxy designation
                proxy_id = str(h.get("proxyid") or "0")
                proxy_group_id = str(h.get("proxy_groupid") or "0")
                monitored_by = str(h.get("monitored_by") or "0")

                if (monitored_by == "1" or proxy_id != "0") and proxy_id in proxy_map:
                    monitored_by_str = f"Proxy: {proxy_map[proxy_id]}"
                elif proxy_id != "0":
                    monitored_by_str = f"Proxy (ID {proxy_id})"
                elif monitored_by == "2" or proxy_group_id != "0":
                    monitored_by_str = f"Proxy Group (ID {proxy_group_id})"
                else:
                    monitored_by_str = "Server"

                # 3. Zabbix Hostgroups assigned
                zabbix_groups = h.get("hostgroups", []) or h.get("groups", [])
                zabbix_group_names = [g.get("name") for g in zabbix_groups if isinstance(g, dict) and g.get("name")]
                zabbix_group_disp = ", ".join(zabbix_group_names) if zabbix_group_names else "-"

                # 4. NetBox Device Role matching
                nb_device = netbox_devices.get(h_name.lower()) or netbox_devices.get(v_name.lower()) or netbox_ip_map.get(ip_str)
                nb_role_name = "-"
                role_synced = False

                if nb_device and nb_device.role:
                    nb_role_name = nb_device.role.name
                    role_synced = any(nb_role_name.lower() == zg.lower() for zg in zabbix_group_names)

                # Format Role Sync action / badge cell (Plain text, no color!)
                if not nb_device or nb_role_name == "-":
                    sync_cell = {"type": "none", "text": "No Role"}
                elif role_synced:
                    sync_cell = {"type": "synced", "text": "Synced"}
                else:
                    sync_cell = {
                        "type": "sync_button",
                        "host_id": host_id,
                        "role_name": nb_role_name,
                        "host_name": h_name
                    }

                items.append([
                    h_name,
                    ip_str,
                    nb_role_name,  # Plain text, no color!
                    zabbix_group_disp,
                    protocol_str,
                    monitored_by_str,
                    sync_cell
                ])
                
        context = process_table_data(request, items, headers, 'Hosts', has_status=True)
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
