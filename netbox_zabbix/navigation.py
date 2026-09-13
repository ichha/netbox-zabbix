from netbox.plugins import PluginMenu, PluginMenuItem

menu = PluginMenu(
    label='ZABBIX',
    icon_class='mdi mdi-server-network',
    groups=(
        ('', (
            PluginMenuItem(link='plugins:netbox_zabbix:servers', link_text='Servers', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:proxies', link_text='Proxies', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:proxy_groups', link_text='Proxy Groups', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:templates', link_text='Templates', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:template_groups', link_text='Template Groups', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:macros', link_text='Macros', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:tags', link_text='Tags', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:hostgroups', link_text='Hostgroups', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:hosts', link_text='Hosts', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
            PluginMenuItem(link='plugins:netbox_zabbix:bulk_push', link_text='Bulk Push', permissions=['netbox_zabbix.view_zabbixhostgrouptemplate']),
        )),
    )
)

