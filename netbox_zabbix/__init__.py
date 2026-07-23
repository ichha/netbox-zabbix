from netbox.plugins import PluginConfig

class NetBoxZabbixConfig(PluginConfig):
    name = 'netbox_zabbix'
    verbose_name = 'Zabbix Integration'
    description = 'Manages and synchronizes NetBox devices and metrics to Zabbix'
    version = '0.1.0'
    author = 'Antigravity'
    author_email = 'antigravity@example.com'
    base_url = 'zabbix'
    default_settings = {
        'zabbix_url': 'http://10.26.192.125/zabbix/api_jsonrpc.php',
        'zabbix_token': '7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61',
        'default_group_id': '2',
    }
    required_settings = []

config = NetBoxZabbixConfig
