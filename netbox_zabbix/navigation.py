from netbox.plugins import PluginMenu, PluginMenuItem, PluginMenuButton

server_buttons = (
    PluginMenuButton(
        link='plugins:netbox_zabbix:zabbixserver_add',
        title='Add Zabbix Server',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_zabbix.add_zabbixserver']
    ),
)

proxy_buttons = (
    PluginMenuButton(
        link='plugins:netbox_zabbix:zabbixproxy_add',
        title='Add Proxy',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_zabbix.add_zabbixproxy']
    ),
)

hostgroup_buttons = (
    PluginMenuButton(
        link='plugins:netbox_zabbix:zabbixhostgroup_add',
        title='Add Hostgroup',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_zabbix.add_zabbixhostgroup']
    ),
)

servers = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixserver_list',
    link_text='Servers',
    buttons=server_buttons,
    permissions=['netbox_zabbix.view_zabbixserver']
)

proxies = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixproxy_list',
    link_text='Proxies',
    buttons=proxy_buttons,
    permissions=['netbox_zabbix.view_zabbixproxy']
)

proxy_groups = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixproxygroup_list',
    link_text='Proxy Groups',
    permissions=['netbox_zabbix.view_zabbixproxygroup']
)

templates = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixtemplate_list',
    link_text='Templates',
    permissions=['netbox_zabbix.view_zabbixtemplate']
)

template_groups = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixtemplategroup_list',
    link_text='Template Groups',
    permissions=['netbox_zabbix.view_zabbixtemplategroup']
)

macros = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixmacro_list',
    link_text='Macros',
    permissions=['netbox_zabbix.view_zabbixmacro']
)

tags = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixtag_list',
    link_text='Tags',
    permissions=['netbox_zabbix.view_zabbixtag']
)

hostgroups = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixhostgroup_list',
    link_text='Hostgroups',
    buttons=hostgroup_buttons,
    permissions=['netbox_zabbix.view_zabbixhostgroup']
)

hosts = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixhost_list',
    link_text='Hosts',
    permissions=['netbox_zabbix.view_zabbixhost']
)

menu = PluginMenu(
    label='ZABBIX',
    icon_class='mdi mdi-monitor-network',
    groups=(
        ('', (
            servers,
            proxies,
            proxy_groups,
            templates,
            template_groups,
            macros,
            tags,
            hostgroups,
            hosts,
        )),
    )
)
