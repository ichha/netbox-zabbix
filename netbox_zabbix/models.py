from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel

class ZabbixServer(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    url = models.CharField(max_length=255)
    token = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixserver', args=[self.pk])


class ZabbixProxy(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='proxies')
    proxyid = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('zabbix_server', 'proxyid')

    def __str__(self):
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixproxy', args=[self.pk])


class ZabbixProxyGroup(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='proxy_groups')
    proxy_groupid = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('zabbix_server', 'proxy_groupid')

    def __str__(self):
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixproxygroup', args=[self.pk])


class ZabbixTemplate(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='templates')
    templateid = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('zabbix_server', 'templateid')

    def __str__(self):
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixtemplate', args=[self.pk])


class ZabbixTemplateGroup(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='template_groups')
    template_groupid = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('zabbix_server', 'template_groupid')

    def __str__(self):
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixtemplategroup', args=[self.pk])


class ZabbixMacro(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='macros')
    macro = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('macro',)

    def __str__(self):
        return f"{self.macro} = {self.value} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixmacro', args=[self.pk])


class ZabbixTag(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name', 'value')

    def __str__(self):
        if self.value:
            return f"{self.name}: {self.value} ({self.zabbix_server.name})"
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixtag', args=[self.pk])


class ZabbixHostGroup(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='host_groups')
    groupid = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('zabbix_server', 'groupid')

    def __str__(self):
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixhostgroup', args=[self.pk])


class ZabbixHost(NetBoxModel):
    zabbix_server = models.ForeignKey(ZabbixServer, on_delete=models.CASCADE, related_name='hosts')
    hostid = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    status = models.IntegerField(default=0)  # 0 = Monitored, 1 = Unmonitored
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('zabbix_server', 'hostid')

    def __str__(self):
        return f"{self.name} ({self.zabbix_server.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_zabbix:zabbixhost', args=[self.pk])
