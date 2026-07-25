from netbox.plugins import PluginConfig

class NetBoxZabbixConfig(PluginConfig):
    name = 'netbox_zabbix'
    label = 'netbox_zabbix'
    verbose_name = 'Zabbix Integration'
    description = 'A NetBox plugin to synchronize data with Zabbix.'
    version = '0.1.0'
    base_url = 'zabbix'

    def ready(self):
        super().ready()
        try:
            import netbox_zabbix.signals  # noqa: F401
            from netbox_zabbix.signals import connect_zabbix_settings_signal
            connect_zabbix_settings_signal()
        except Exception:
            pass

config = NetBoxZabbixConfig
