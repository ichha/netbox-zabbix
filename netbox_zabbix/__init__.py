from netbox.plugins import PluginConfig

class NetBoxZabbixConfig(PluginConfig):
    name = 'netbox_zabbix'
    verbose_name = 'Zabbix'
    description = 'Zabbix Integration Plugin'
    version = '0.1.0'
    author = 'Antigravity'
    author_email = 'antigravity@example.com'
    base_url = 'zabbix'
    default_settings = {}
    required_settings = []

config = NetBoxZabbixConfig
