import django_tables2 as tables
from netbox.tables import NetBoxTable
from .models import (
    ZabbixServer, ZabbixProxy, ZabbixProxyGroup, ZabbixTemplate,
    ZabbixTemplateGroup, ZabbixMacro, ZabbixTag, ZabbixHostGroup, ZabbixHost
)

class ZabbixServerTable(NetBoxTable):
    name = tables.Column(linkify=True)
    url = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixServer
        fields = ('pk', 'id', 'name', 'url', 'description')
        default_columns = ('pk', 'name', 'url', 'description')


class ZabbixProxyTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    proxyid = tables.Column()
    status = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixProxy
        fields = ('pk', 'id', 'name', 'zabbix_server', 'proxyid', 'status', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'proxyid', 'status')


class ZabbixProxyGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    proxy_groupid = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixProxyGroup
        fields = ('pk', 'id', 'name', 'zabbix_server', 'proxy_groupid', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'proxy_groupid')


class ZabbixTemplateTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    templateid = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixTemplate
        fields = ('pk', 'id', 'name', 'zabbix_server', 'templateid', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'templateid')


class ZabbixTemplateGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    template_groupid = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixTemplateGroup
        fields = ('pk', 'id', 'name', 'zabbix_server', 'template_groupid', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'template_groupid')


class ZabbixMacroTable(NetBoxTable):
    macro = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    value = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixMacro
        fields = ('pk', 'id', 'macro', 'zabbix_server', 'value', 'description')
        default_columns = ('pk', 'macro', 'zabbix_server', 'value')


class ZabbixTagTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    value = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixTag
        fields = ('pk', 'id', 'name', 'zabbix_server', 'value', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'value')


class ZabbixHostGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    groupid = tables.Column()
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixHostGroup
        fields = ('pk', 'id', 'name', 'zabbix_server', 'groupid', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'groupid')


class ZabbixHostTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zabbix_server = tables.Column(linkify=True)
    hostid = tables.Column()
    status = tables.TemplateColumn(
        template_code='''
        {% if record.status == 0 %}
            <span class="badge bg-success">Monitored</span>
        {% else %}
            <span class="badge bg-warning">Unmonitored</span>
        {% endif %}
        '''
    )
    description = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = ZabbixHost
        fields = ('pk', 'id', 'name', 'zabbix_server', 'hostid', 'status', 'description')
        default_columns = ('pk', 'name', 'zabbix_server', 'hostid', 'status')
