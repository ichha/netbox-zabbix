from netbox.forms import NetBoxModelForm
from .models import (
    ZabbixServer, ZabbixProxy, ZabbixProxyGroup, ZabbixTemplate,
    ZabbixTemplateGroup, ZabbixMacro, ZabbixTag, ZabbixHostGroup, ZabbixHost
)

class ZabbixServerForm(NetBoxModelForm):
    class Meta:
        model = ZabbixServer
        fields = ('name', 'url', 'token', 'description', 'tags')


class ZabbixProxyForm(NetBoxModelForm):
    class Meta:
        model = ZabbixProxy
        fields = ('zabbix_server', 'proxyid', 'name', 'status', 'description', 'tags')


class ZabbixProxyGroupForm(NetBoxModelForm):
    class Meta:
        model = ZabbixProxyGroup
        fields = ('zabbix_server', 'proxy_groupid', 'name', 'description', 'tags')


class ZabbixTemplateForm(NetBoxModelForm):
    class Meta:
        model = ZabbixTemplate
        fields = ('zabbix_server', 'templateid', 'name', 'description', 'tags')


class ZabbixTemplateGroupForm(NetBoxModelForm):
    class Meta:
        model = ZabbixTemplateGroup
        fields = ('zabbix_server', 'template_groupid', 'name', 'description', 'tags')


class ZabbixMacroForm(NetBoxModelForm):
    class Meta:
        model = ZabbixMacro
        fields = ('zabbix_server', 'macro', 'value', 'description', 'tags')


class ZabbixTagForm(NetBoxModelForm):
    class Meta:
        model = ZabbixTag
        fields = ('zabbix_server', 'name', 'value', 'description', 'tags')


class ZabbixHostGroupForm(NetBoxModelForm):
    class Meta:
        model = ZabbixHostGroup
        fields = ('zabbix_server', 'groupid', 'name', 'description', 'tags')


class ZabbixHostForm(NetBoxModelForm):
    class Meta:
        model = ZabbixHost
        fields = ('zabbix_server', 'hostid', 'name', 'status', 'description', 'tags')
