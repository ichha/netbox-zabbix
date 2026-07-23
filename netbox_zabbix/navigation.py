from netbox.plugins import PluginMenu, PluginMenuItem, PluginMenuButton
from utilities.choices import ButtonColorChoices

server_buttons = (
    PluginMenuButton(
        link='plugins:netbox_zabbix:zabbixserver_add',
        title='Add Zabbix Server',
        icon_class='mdi mdi-plus-thick',
        color=ButtonColorChoices.GREEN
    ),
)

proxy_buttons = (
    PluginMenuButton(
        link='plugins:netbox_zabbix:zabbixproxy_add',
        title='Add Proxy',
        icon_class='mdi mdi-plus-thick',
        color=ButtonColorChoices.GREEN
    ),
)

hostgroup_buttons = (
    PluginMenuButton(
        link='plugins:netbox_zabbix:zabbixhostgroup_add',
        title='Add Hostgroup',
        icon_class='mdi mdi-plus-thick',
        color=ButtonColorChoices.GREEN
    ),
)

servers = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixserver_list',
    link_text='Servers',
    buttons=server_buttons
)

proxies = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixproxy_list',
    link_text='Proxies',
    buttons=proxy_buttons
)

proxy_groups = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixproxygroup_list',
    link_text='Proxy Groups'
)

templates = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixtemplate_list',
    link_text='Templates'
)

template_groups = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixtemplategroup_list',
    link_text='Template Groups'
)

macros = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixmacro_list',
    link_text='Macros'
)

tags = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixtag_list',
    link_text='Tags'
)

hostgroups = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixhostgroup_list',
    link_text='Hostgroups',
    buttons=hostgroup_buttons
)

hosts = PluginMenuItem(
    link='plugins:netbox_zabbix:zabbixhost_list',
    link_text='Hosts'
)

# Render a single flat group to match the requested UI layout
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
