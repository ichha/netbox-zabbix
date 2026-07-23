import requests
import logging
from .models import (
    ZabbixServer, ZabbixProxy, ZabbixProxyGroup, ZabbixTemplate,
    ZabbixTemplateGroup, ZabbixMacro, ZabbixTag, ZabbixHostGroup, ZabbixHost
)

logger = logging.getLogger('netbox.plugins.netbox_zabbix')

class ZabbixClient:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.id = 1

    def call(self, method, params=None):
        if params is None:
            params = {}
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.id
        }
        if self.token:
            payload["auth"] = self.token
            
        headers = {
            "Content-Type": "application/json-rpc"
        }
        
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            res_json = response.json()
        except requests.RequestException as e:
            raise Exception(f"HTTP request to Zabbix failed: {e}")
        
        if "error" in res_json:
            error_data = res_json['error'].get('data', '')
            error_msg = res_json['error'].get('message', '')
            raise Exception(f"Zabbix API Error: {error_msg} ({error_data})")
            
        self.id += 1
        return res_json.get("result", [])

def sync_zabbix_data(server):
    """
    Connects to Zabbix server, pulls all configuration items,
    and updates the NetBox plugin models.
    """
    client = ZabbixClient(server.url, server.token)
    
    # 1. Sync Proxies
    proxies_data = client.call("proxy.get", {
        "output": ["proxyid", "host", "status", "description"]
    })
    active_proxy_ids = []
    for item in proxies_data:
        p_id = item['proxyid']
        name = item.get('host', '') or item.get('name', f"Proxy {p_id}")
        # status mapping (active: 5, passive: 6 or 0/1 depending on Zabbix version)
        # Zabbix 7.0+ uses different proxy types, we will save status as string/raw
        status_raw = str(item.get('status', ''))
        
        proxy, _ = ZabbixProxy.objects.update_or_create(
            zabbix_server=server,
            proxyid=p_id,
            defaults={
                'name': name,
                'status': status_raw,
                'description': item.get('description', '')
            }
        )
        active_proxy_ids.append(p_id)
    ZabbixProxy.objects.filter(zabbix_server=server).exclude(proxyid__in=active_proxy_ids).delete()

    # 2. Sync Proxy Groups (Zabbix 7.0+)
    active_proxy_group_ids = []
    try:
        proxy_groups_data = client.call("proxygroup.get", {
            "output": ["proxy_groupid", "name", "description"]
        })
        for item in proxy_groups_data:
            pg_id = item['proxy_groupid']
            pg, _ = ZabbixProxyGroup.objects.update_or_create(
                zabbix_server=server,
                proxy_groupid=pg_id,
                defaults={
                    'name': item.get('name', ''),
                    'description': item.get('description', '')
                }
            )
            active_proxy_group_ids.append(pg_id)
    except Exception as e:
        logger.warning(f"Failed to fetch proxy groups: {e}. Zabbix server might not support proxy groups (introduced in Zabbix 7.0).")
    ZabbixProxyGroup.objects.filter(zabbix_server=server).exclude(proxy_groupid__in=active_proxy_group_ids).delete()

    # 3. Sync Templates & gather template tags
    templates_data = client.call("template.get", {
        "output": ["templateid", "host", "name", "description"],
        "selectTags": "extend"
    })
    active_template_ids = []
    tags_to_save = set()
    
    for item in templates_data:
        t_id = item['templateid']
        name = item.get('name', '') or item.get('host', f"Template {t_id}")
        t, _ = ZabbixTemplate.objects.update_or_create(
            zabbix_server=server,
            templateid=t_id,
            defaults={
                'name': name,
                'description': item.get('description', '')
            }
        )
        active_template_ids.append(t_id)
        
        # Collect tags
        for tag_item in item.get('tags', []):
            tags_to_save.add((tag_item['tag'], tag_item.get('value', '')))
            
    ZabbixTemplate.objects.filter(zabbix_server=server).exclude(templateid__in=active_template_ids).delete()

    # 4. Sync Template Groups (Zabbix 6.2+)
    active_template_group_ids = []
    try:
        template_groups_data = client.call("templategroup.get", {
            "output": ["groupid", "name"]
        })
        for item in template_groups_data:
            tg_id = item['groupid']
            tg, _ = ZabbixTemplateGroup.objects.update_or_create(
                zabbix_server=server,
                template_groupid=tg_id,
                defaults={
                    'name': item.get('name', ''),
                    'description': 'Synchronized Template Group'
                }
            )
            active_template_group_ids.append(tg_id)
    except Exception as e:
        logger.warning(f"Failed to fetch template groups: {e}.")
    ZabbixTemplateGroup.objects.filter(zabbix_server=server).exclude(template_groupid__in=active_template_group_ids).delete()

    # 5. Sync User Macros (Global)
    active_macro_ids = []
    try:
        macros_data = client.call("usermacro.get", {
            "globalmacro": True,
            "output": ["globalmacroid", "macro", "value", "description"]
        })
        for item in macros_data:
            # We don't have a direct database unique field for macro string across servers,
            # but we can filter by macro name and server.
            macro_str = item.get('macro', '')
            if macro_str:
                mac, _ = ZabbixMacro.objects.update_or_create(
                    zabbix_server=server,
                    macro=macro_str,
                    defaults={
                        'value': item.get('value', ''),
                        'description': item.get('description', '')
                    }
                )
                active_macro_ids.append(mac.id)
    except Exception as e:
        logger.warning(f"Failed to fetch global macros: {e}")
    ZabbixMacro.objects.filter(zabbix_server=server).exclude(id__in=active_macro_ids).delete()

    # 6. Sync Host Groups
    hostgroups_data = client.call("hostgroup.get", {
        "output": ["groupid", "name"]
    })
    active_hostgroup_ids = []
    for item in hostgroups_data:
        g_id = item['groupid']
        hg, _ = ZabbixHostGroup.objects.update_or_create(
            zabbix_server=server,
            groupid=g_id,
            defaults={
                'name': item.get('name', ''),
                'description': 'Synchronized Host Group'
            }
        )
        active_hostgroup_ids.append(g_id)
    ZabbixHostGroup.objects.filter(zabbix_server=server).exclude(groupid__in=active_hostgroup_ids).delete()

    # 7. Sync Hosts & gather host tags
    hosts_data = client.call("host.get", {
        "output": ["hostid", "host", "name", "status", "description"],
        "selectTags": "extend"
    })
    active_host_ids = []
    for item in hosts_data:
        h_id = item['hostid']
        name = item.get('name', '') or item.get('host', f"Host {h_id}")
        
        # Status: 0 = Monitored, 1 = Unmonitored
        try:
            status_val = int(item.get('status', 0))
        except ValueError:
            status_val = 0
            
        h, _ = ZabbixHost.objects.update_or_create(
            zabbix_server=server,
            hostid=h_id,
            defaults={
                'name': name,
                'status': status_val,
                'description': item.get('description', '')
            }
        )
        active_host_ids.append(h_id)
        
        # Collect tags
        for tag_item in item.get('tags', []):
            tags_to_save.add((tag_item['tag'], tag_item.get('value', '')))
            
    ZabbixHost.objects.filter(zabbix_server=server).exclude(hostid__in=active_host_ids).delete()

    # 8. Sync Tags
    active_tag_ids = []
    for tag_name, tag_val in tags_to_save:
        tag_obj, _ = ZabbixTag.objects.update_or_create(
            zabbix_server=server,
            name=tag_name,
            value=tag_val,
            defaults={
                'description': 'Synchronized from Zabbix'
            }
        )
        active_tag_ids.append(tag_obj.id)
    ZabbixTag.objects.filter(zabbix_server=server).exclude(id__in=active_tag_ids).delete()

    logger.info(f"Successfully finished synchronization for server {server.name}")
