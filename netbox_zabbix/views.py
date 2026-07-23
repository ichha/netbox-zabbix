from django.views.generic import View
from django.shortcuts import render
from django.core.paginator import Paginator
from .zabbix_api import ZabbixAPI


def process_table_data(request, items, headers, title, default_per_page=50):
    total_devices = len(items)

    # Calculate active/monitored and inactive/unmonitored counts
    synced_devices = 0
    for row in items:
        if any(str(cell).lower() in ['monitored', 'online', 'active'] for cell in row):
            synced_devices += 1
    devices_to_sync = total_devices - synced_devices

    # Filter by status if requested
    status_filter = request.GET.get('status', '').strip().lower()
    if status_filter == 'synced' or status_filter == 'active':
        items = [row for row in items if any(str(cell).lower() in ['monitored', 'online', 'active'] for cell in row)]
    elif status_filter == 'pending' or status_filter == 'inactive':
        items = [row for row in items if not any(str(cell).lower() in ['monitored', 'online', 'active'] for cell in row)]

    # Quick search filtering across all columns
    q = request.GET.get('q', '').strip()
    if q:
        items = [row for row in items if any(q.lower() in str(cell).lower() for cell in row)]

    filtered_count = len(items)

    # Per page pagination configuration
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
        'q': q,
    }


class ZabbixServersView(View):
    def get(self, request):
        api = ZabbixAPI()
        version, error = api.get_api_version()
        
        hosts = api.get_hosts()
        templates = api.get_templates()
        
        host_count = len(hosts) if isinstance(hosts, list) else 0
        template_count = len(templates) if isinstance(templates, list) else 0
        
        context = {
            'zabbix_url': api.url,
            'zabbix_token': api.token,
            'zabbix_version': version,
            'connected': error is None,
            'error': error,
            'host_count': host_count,
            'template_count': template_count,
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
            
        headers = ["Proxy ID", "Name", "Mode", "State", "Version", "Last Seen", "Description"]
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
                    last_seen_str,
                    p.get("description", "-") or "-"
                ])
                
        context = process_table_data(request, items, headers, 'Proxies')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixProxyGroupsView(View):
    def get(self, request):
        api = ZabbixAPI()
        groups = api.get_proxy_groups()
        
        if isinstance(groups, dict) and "error" in groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Proxy Groups', 'error': groups["error"]
            })
            
        headers = ["Group ID", "Name", "State", "Description"]
        items = []
        if isinstance(groups, list):
            for g in groups:
                items.append([
                    g.get("proxy_groupid", "-"),
                    g.get("name", "-"),
                    g.get("state", "-") or "-",
                    g.get("description", "-") or "-"
                ])
                
        context = process_table_data(request, items, headers, 'Proxy Groups')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixTemplatesView(View):
    def get(self, request):
        api = ZabbixAPI()
        templates = api.get_templates()
        
        if isinstance(templates, dict) and "error" in templates:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Templates', 'error': templates["error"]
            })
            
        headers = ["Template ID", "Name / Technical Host", "Description"]
        items = []
        if isinstance(templates, list):
            for t in templates:
                name_disp = t.get("name", "") or t.get("host", "-")
                items.append([
                    t.get("templateid", "-"),
                    name_disp,
                    t.get("description", "-") or "-"
                ])
                
        context = process_table_data(request, items, headers, 'Templates')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixTemplateGroupsView(View):
    def get(self, request):
        api = ZabbixAPI()
        groups = api.get_template_groups()
        
        if isinstance(groups, dict) and "error" in groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Template Groups', 'error': groups["error"]
            })
            
        headers = ["Group ID", "Name"]
        items = []
        if isinstance(groups, list):
            for g in groups:
                items.append([
                    g.get("groupid", "-"),
                    g.get("name", "-")
                ])
                
        context = process_table_data(request, items, headers, 'Template Groups')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixMacrosView(View):
    def get(self, request):
        api = ZabbixAPI()
        macros = api.get_macros()
        
        if isinstance(macros, dict) and "error" in macros:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Global Macros', 'error': macros["error"]
            })
            
        headers = ["Macro ID", "Macro", "Value", "Description"]
        items = []
        if isinstance(macros, list):
            for m in macros:
                items.append([
                    m.get("globalmacroid", "-"),
                    m.get("macro", "-"),
                    m.get("value", "-"),
                    m.get("description", "-") or "-"
                ])
                
        context = process_table_data(request, items, headers, 'Global Macros')
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
                
        context = process_table_data(request, items, headers, 'Tags')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixHostGroupsView(View):
    def get(self, request):
        api = ZabbixAPI()
        groups = api.get_host_groups()
        
        if isinstance(groups, dict) and "error" in groups:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Host Groups', 'error': groups["error"]
            })
            
        headers = ["Group ID", "Group Name"]
        items = []
        if isinstance(groups, list):
            for g in groups:
                items.append([
                    g.get("groupid", "-"),
                    g.get("name", "-")
                ])
                
        context = process_table_data(request, items, headers, 'Host Groups')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)


class ZabbixHostsView(View):
    def get(self, request):
        api = ZabbixAPI()
        hosts = api.get_hosts()
        
        if isinstance(hosts, dict) and "error" in hosts:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Hosts', 'error': hosts["error"]
            })
            
        headers = ["Host Name", "Primary IP", "Protocol", "Port", "Monitored By", "Visible Name", "Status"]
        items = []
        if isinstance(hosts, list):
            for h in hosts:
                status_str = "Monitored" if str(h.get("status")) == "0" else "Unmonitored"
                
                # 1. Interface & Protocol parsing
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
                    if if_type == "2":
                        protocol_str = "SNMP"
                    elif if_type == "3":
                        protocol_str = "IPMI"
                    elif if_type == "4":
                        protocol_str = "JMX"
                    else:
                        protocol_str = "Agent"

                # 2. Monitored By / Proxy designation parsing
                proxy_obj = h.get("proxy")
                proxy_name = None
                if isinstance(proxy_obj, dict):
                    proxy_name = proxy_obj.get("name") or proxy_obj.get("host")
                elif isinstance(proxy_obj, list) and len(proxy_obj) > 0 and isinstance(proxy_obj[0], dict):
                    proxy_name = proxy_obj[0].get("name") or proxy_obj[0].get("host")
                    
                proxy_id = h.get("proxyid") or h.get("proxy_hostid")
                
                if proxy_name:
                    monitored_by_str = f"Proxy: {proxy_name}"
                elif proxy_id and str(proxy_id) != "0":
                    monitored_by_str = f"Proxy (ID {proxy_id})"
                else:
                    monitored_by_str = "Server"

                items.append([
                    h.get("host", "-"),
                    ip_str,
                    protocol_str,
                    port_str,
                    monitored_by_str,
                    h.get("name") or h.get("host") or "-",
                    status_str
                ])
                
        context = process_table_data(request, items, headers, 'Hosts')
        return render(request, 'netbox_zabbix/zabbix_table.html', context)
