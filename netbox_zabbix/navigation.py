from netbox.plugins import PluginMenu, PluginMenuItem

menu = PluginMenu(
    label='ZABBIX',
    icon_class='mdi mdi-monitor-network',
    groups=(
        ('', (
            PluginMenuItem(link='plugins:netbox_zabbix:servers', link_text='Servers'),
            PluginMenuItem(link='plugins:netbox_zabbix:proxies', link_text='Proxies'),
            PluginMenuItem(link='plugins:netbox_zabbix:proxy_groups', link_text='Proxy Groups'),
            PluginMenuItem(link='plugins:netbox_zabbix:templates', link_text='Templates'),
            PluginMenuItem(link='plugins:netbox_zabbix:template_groups', link_text='Template Groups'),
            PluginMenuItem(link='plugins:netbox_zabbix:macros', link_text='Macros'),
            PluginMenuItem(link='plugins:netbox_zabbix:tags', link_text='Tags'),
            PluginMenuItem(link='plugins:netbox_zabbix:hostgroups', link_text='Hostgroups'),
            PluginMenuItem(link='plugins:netbox_zabbix:hosts', link_text='Hosts'),
        )),
    )
)
