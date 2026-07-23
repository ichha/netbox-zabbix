from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import View
from netbox.views import generic

from .models import (
    ZabbixServer, ZabbixProxy, ZabbixProxyGroup, ZabbixTemplate,
    ZabbixTemplateGroup, ZabbixMacro, ZabbixTag, ZabbixHostGroup, ZabbixHost
)
from . import forms, tables, filtersets
from .zabbix_api import sync_zabbix_data

# Base detail view for Zabbix objects to render dynamically without template duplication
class BaseZabbixObjectView(generic.ObjectView):
    template_name = 'netbox_zabbix/object_detail.html'

    def get_extra_context(self, request, instance):
        fields = []
        for field in instance._meta.fields:
            if field.name in ['id', 'created', 'last_updated']:
                continue
            value = getattr(instance, field.name)
            if field.is_relation and value:
                value = str(value)
            fields.append({
                'label': field.verbose_name.capitalize(),
                'value': value
            })
        return {
            'fields': fields
        }


# --- ZabbixServer Views ---
class ZabbixServerListView(generic.ObjectListView):
    queryset = ZabbixServer.objects.all()
    table = tables.ZabbixServerTable
    filterset = filtersets.ZabbixServerFilterSet


class ZabbixServerView(generic.ObjectView):
    queryset = ZabbixServer.objects.all()
    template_name = 'netbox_zabbix/zabbixserver.html'


class ZabbixServerEditView(generic.ObjectEditView):
    queryset = ZabbixServer.objects.all()
    form_class = forms.ZabbixServerForm


class ZabbixServerDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixServer.objects.all()


class ZabbixServerSyncView(View):
    def post(self, request, pk):
        server = get_object_or_404(ZabbixServer, pk=pk)
        try:
            sync_zabbix_data(server)
            messages.success(request, f"Successfully synchronized data from Zabbix Server '{server.name}'.")
        except Exception as e:
            messages.error(request, f"Synchronization failed: {e}")
        return redirect('plugins:netbox_zabbix:zabbixserver', pk=pk)


# --- ZabbixProxy Views ---
class ZabbixProxyListView(generic.ObjectListView):
    queryset = ZabbixProxy.objects.all()
    table = tables.ZabbixProxyTable
    filterset = filtersets.ZabbixProxyFilterSet


class ZabbixProxyView(BaseZabbixObjectView):
    queryset = ZabbixProxy.objects.all()


class ZabbixProxyEditView(generic.ObjectEditView):
    queryset = ZabbixProxy.objects.all()
    form_class = forms.ZabbixProxyForm


class ZabbixProxyDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixProxy.objects.all()


# --- ZabbixProxyGroup Views ---
class ZabbixProxyGroupListView(generic.ObjectListView):
    queryset = ZabbixProxyGroup.objects.all()
    table = tables.ZabbixProxyGroupTable
    filterset = filtersets.ZabbixProxyGroupFilterSet


class ZabbixProxyGroupView(BaseZabbixObjectView):
    queryset = ZabbixProxyGroup.objects.all()


class ZabbixProxyGroupEditView(generic.ObjectEditView):
    queryset = ZabbixProxyGroup.objects.all()
    form_class = forms.ZabbixProxyGroupForm


class ZabbixProxyGroupDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixProxyGroup.objects.all()


# --- ZabbixTemplate Views ---
class ZabbixTemplateListView(generic.ObjectListView):
    queryset = ZabbixTemplate.objects.all()
    table = tables.ZabbixTemplateTable
    filterset = filtersets.ZabbixTemplateFilterSet


class ZabbixTemplateView(BaseZabbixObjectView):
    queryset = ZabbixTemplate.objects.all()


class ZabbixTemplateEditView(generic.ObjectEditView):
    queryset = ZabbixTemplate.objects.all()
    form_class = forms.ZabbixTemplateForm


class ZabbixTemplateDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixTemplate.objects.all()


# --- ZabbixTemplateGroup Views ---
class ZabbixTemplateGroupListView(generic.ObjectListView):
    queryset = ZabbixTemplateGroup.objects.all()
    table = tables.ZabbixTemplateGroupTable
    filterset = filtersets.ZabbixTemplateGroupFilterSet


class ZabbixTemplateGroupView(BaseZabbixObjectView):
    queryset = ZabbixTemplateGroup.objects.all()


class ZabbixTemplateGroupEditView(generic.ObjectEditView):
    queryset = ZabbixTemplateGroup.objects.all()
    form_class = forms.ZabbixTemplateGroupForm


class ZabbixTemplateGroupDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixTemplateGroup.objects.all()


# --- ZabbixMacro Views ---
class ZabbixMacroListView(generic.ObjectListView):
    queryset = ZabbixMacro.objects.all()
    table = tables.ZabbixMacroTable
    filterset = filtersets.ZabbixMacroFilterSet


class ZabbixMacroView(BaseZabbixObjectView):
    queryset = ZabbixMacro.objects.all()


class ZabbixMacroEditView(generic.ObjectEditView):
    queryset = ZabbixMacro.objects.all()
    form_class = forms.ZabbixMacroForm


class ZabbixMacroDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixMacro.objects.all()


# --- ZabbixTag Views ---
class ZabbixTagListView(generic.ObjectListView):
    queryset = ZabbixTag.objects.all()
    table = tables.ZabbixTagTable
    filterset = filtersets.ZabbixTagFilterSet


class ZabbixTagView(BaseZabbixObjectView):
    queryset = ZabbixTag.objects.all()


class ZabbixTagEditView(generic.ObjectEditView):
    queryset = ZabbixTag.objects.all()
    form_class = forms.ZabbixTagForm


class ZabbixTagDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixTag.objects.all()


# --- ZabbixHostGroup Views ---
class ZabbixHostGroupListView(generic.ObjectListView):
    queryset = ZabbixHostGroup.objects.all()
    table = tables.ZabbixHostGroupTable
    filterset = filtersets.ZabbixHostGroupFilterSet


class ZabbixHostGroupView(BaseZabbixObjectView):
    queryset = ZabbixHostGroup.objects.all()


class ZabbixHostGroupEditView(generic.ObjectEditView):
    queryset = ZabbixHostGroup.objects.all()
    form_class = forms.ZabbixHostGroupForm


class ZabbixHostGroupDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixHostGroup.objects.all()


# --- ZabbixHost Views ---
class ZabbixHostListView(generic.ObjectListView):
    queryset = ZabbixHost.objects.all()
    table = tables.ZabbixHostTable
    filterset = filtersets.ZabbixHostFilterSet


class ZabbixHostView(BaseZabbixObjectView):
    queryset = ZabbixHost.objects.all()


class ZabbixHostEditView(generic.ObjectEditView):
    queryset = ZabbixHost.objects.all()
    form_class = forms.ZabbixHostForm


class ZabbixHostDeleteView(generic.ObjectDeleteView):
    queryset = ZabbixHost.objects.all()
