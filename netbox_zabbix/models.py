from django.db import models


class ZabbixHostGroupTemplate(models.Model):
    """
    Stores mapped Zabbix templates and settings (Interface Type, Proxy) per NetBox Device Role / Host Group.
    These settings are applied when pushing devices from NetBox to Zabbix.
    """
    role_name = models.CharField(max_length=255, unique=True)
    template_ids = models.JSONField(default=list, blank=True)
    template_names = models.JSONField(default=list, blank=True)
    interface_type = models.CharField(max_length=20, null=True, blank=True)
    proxy_id = models.CharField(max_length=50, null=True, blank=True)
    proxy_name = models.CharField(max_length=255, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ('role_name',)
        verbose_name = 'Zabbix Host Group Template Mapping'
        verbose_name_plural = 'Zabbix Host Group Template Mappings'

    def __str__(self):
        return f"{self.role_name} ({len(self.template_ids)} templates, Type: {self.interface_type}, Proxy: {self.proxy_name})"
