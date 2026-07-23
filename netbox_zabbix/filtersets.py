from netbox.filtersets import NetBoxModelFilterSet
from .models import (
    ZabbixServer, ZabbixProxy, ZabbixProxyGroup, ZabbixTemplate,
    ZabbixTemplateGroup, ZabbixMacro, ZabbixTag, ZabbixHostGroup, ZabbixHost
)

class ZabbixServerFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixServer
        fields = ('id', 'name')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixProxyFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixProxy
        fields = ('id', 'name', 'proxyid', 'zabbix_server', 'status')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixProxyGroupFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixProxyGroup
        fields = ('id', 'name', 'proxy_groupid', 'zabbix_server')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixTemplateFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixTemplate
        fields = ('id', 'name', 'templateid', 'zabbix_server')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixTemplateGroupFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixTemplateGroup
        fields = ('id', 'name', 'template_groupid', 'zabbix_server')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixMacroFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixMacro
        fields = ('id', 'macro', 'zabbix_server')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(macro__icontains=value)


class ZabbixTagFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixTag
        fields = ('id', 'name', 'value', 'zabbix_server')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixHostGroupFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixHostGroup
        fields = ('id', 'name', 'groupid', 'zabbix_server')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)


class ZabbixHostFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = ZabbixHost
        fields = ('id', 'name', 'hostid', 'zabbix_server', 'status')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)
