import requests
import logging
from django.conf import settings

logger = logging.getLogger('netbox.plugins.netbox_zabbix')

class ZabbixAPI:
    def __init__(self):
        config = getattr(settings, 'PLUGINS_CONFIG', {}).get('netbox_zabbix', {})
        self.url = config.get('zabbix_url', 'http://10.26.192.125/zabbix/api_jsonrpc.php')
        self.token = config.get('zabbix_token', '7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61')
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
        if self.token and method != 'apiinfo.version':
            payload["auth"] = self.token
            
        headers = {"Content-Type": "application/json-rpc"}
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            res_json = response.json()
            if "error" in res_json:
                error_msg = res_json['error'].get('message', 'Unknown Error')
                error_data = res_json['error'].get('data', '')
                logger.error(f"Zabbix API Error [{method}]: {error_msg} - {error_data}")
                return {"error": f"{error_msg} ({error_data})"}
            self.id += 1
            return res_json.get("result", [])
        except Exception as e:
            logger.error(f"Zabbix Connection Error [{method}]: {e}")
            return {"error": str(e)}

    def get_api_version(self):
        res = self.call("apiinfo.version", {})
        if isinstance(res, dict) and "error" in res:
            return None, res["error"]
        return res, None

    def get_proxies(self):
        return self.call("proxy.get", {
            "output": ["proxyid", "name", "host", "operating_mode", "status", "state", "version", "lastaccess", "description"]
        })

    def get_proxy_groups(self):
        return self.call("proxygroup.get", {
            "output": ["proxy_groupid", "name", "state", "description"]
        })

    def get_templates(self):
        return self.call("template.get", {
            "output": ["templateid", "name", "host", "description"]
        })

    def get_template_groups(self):
        return self.call("templategroup.get", {
            "output": ["groupid", "name"]
        })

    def get_macros(self):
        return self.call("usermacro.get", {
            "globalmacro": True,
            "output": ["globalmacroid", "macro", "value", "description"]
        })

    def get_host_groups(self):
        return self.call("hostgroup.get", {
            "output": ["groupid", "name"]
        })

    def get_hosts(self):
        return self.call("host.get", {
            "output": ["hostid", "host", "name", "status", "proxyid", "proxy_hostid"],
            "selectInterfaces": ["ip", "port", "type", "main"]
        })

    def get_tags(self):
        hosts = self.call("host.get", {"output": ["hostid"], "selectTags": ["tag", "value"]})
        templates = self.call("template.get", {"output": ["templateid"], "selectTags": ["tag", "value"]})
        
        tags_set = set()
        if isinstance(hosts, list):
            for h in hosts:
                for t in h.get("tags", []):
                    if isinstance(t, dict):
                        tags_set.add((t.get("tag", ""), t.get("value", "")))
        if isinstance(templates, list):
            for tm in templates:
                for t in tm.get("tags", []):
                    if isinstance(t, dict):
                        tags_set.add((t.get("tag", ""), t.get("value", "")))
                    
        return [{"tag": t[0], "value": t[1]} for t in sorted(tags_set)]
