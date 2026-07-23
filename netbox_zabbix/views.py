from django.views.generic import View
from django.shortcuts import render
from .zabbix_api import ZabbixAPI

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
            
        headers = ["Proxy ID", "Name", "Status / Mode", "Description"]
        items = []
        if isinstance(proxies, list):
            for p in proxies:
                status_str = "Active" if str(p.get("status")) == "5" else "Passive" if str(p.get("status")) == "6" else f"Mode {p.get('status')}"
                items.append([
                    p.get("proxyid", "-"),
                    p.get("host", "-"),
                    status_str,
                    p.get("description", "-") or "-"
                ])
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Proxies', 'headers': headers, 'items': items
        })


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
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Proxy Groups', 'headers': headers, 'items': items
        })


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
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Templates', 'headers': headers, 'items': items
        })


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
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Template Groups', 'headers': headers, 'items': items
        })


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
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Global Macros', 'headers': headers, 'items': items
        })


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
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Tags', 'headers': headers, 'items': items
        })


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
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Host Groups', 'headers': headers, 'items': items
        })


class ZabbixHostsView(View):
    def get(self, request):
        api = ZabbixAPI()
        hosts = api.get_hosts()
        
        if isinstance(hosts, dict) and "error" in hosts:
            return render(request, 'netbox_zabbix/zabbix_table.html', {
                'title': 'Hosts', 'error': hosts["error"]
            })
            
        headers = ["Host ID", "Host Name", "Visible Name", "Status", "IP Address", "Port"]
        items = []
        if isinstance(hosts, list):
            for h in hosts:
                status_str = "Monitored" if str(h.get("status")) == "0" else "Unmonitored"
                
                # Extract primary interface IP & Port
                interfaces = h.get("interfaces", [])
                ip_str = "-"
                port_str = "-"
                if isinstance(interfaces, list) and len(interfaces) > 0:
                    ip_str = interfaces[0].get("ip", "-")
                    port_str = interfaces[0].get("port", "-")
                    
                items.append([
                    h.get("hostid", "-"),
                    h.get("host", "-"),
                    h.get("name", "") or h.get("host", "-"),
                    status_str,
                    ip_str,
                    port_str
                ])
                
        return render(request, 'netbox_zabbix/zabbix_table.html', {
            'title': 'Hosts', 'headers': headers, 'items': items
        })
