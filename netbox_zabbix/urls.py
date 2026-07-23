from django.urls import path
from . import views

urlpatterns = [
    # ZabbixServer URLs
    path('servers/', views.ZabbixServerListView.as_view(), name='zabbixserver_list'),
    path('servers/add/', views.ZabbixServerEditView.as_view(), name='zabbixserver_add'),
    path('servers/<int:pk>/', views.ZabbixServerView.as_view(), name='zabbixserver'),
    path('servers/<int:pk>/edit/', views.ZabbixServerEditView.as_view(), name='zabbixserver_edit'),
    path('servers/<int:pk>/delete/', views.ZabbixServerDeleteView.as_view(), name='zabbixserver_delete'),
    path('servers/<int:pk>/sync/', views.ZabbixServerSyncView.as_view(), name='zabbixserver_sync'),

    # ZabbixProxy URLs
    path('proxies/', views.ZabbixProxyListView.as_view(), name='zabbixproxy_list'),
    path('proxies/add/', views.ZabbixProxyEditView.as_view(), name='zabbixproxy_add'),
    path('proxies/<int:pk>/', views.ZabbixProxyView.as_view(), name='zabbixproxy'),
    path('proxies/<int:pk>/edit/', views.ZabbixProxyEditView.as_view(), name='zabbixproxy_edit'),
    path('proxies/<int:pk>/delete/', views.ZabbixProxyDeleteView.as_view(), name='zabbixproxy_delete'),

    # ZabbixProxyGroup URLs
    path('proxy-groups/', views.ZabbixProxyGroupListView.as_view(), name='zabbixproxygroup_list'),
    path('proxy-groups/add/', views.ZabbixProxyGroupEditView.as_view(), name='zabbixproxygroup_add'),
    path('proxy-groups/<int:pk>/', views.ZabbixProxyGroupView.as_view(), name='zabbixproxygroup'),
    path('proxy-groups/<int:pk>/edit/', views.ZabbixProxyGroupEditView.as_view(), name='zabbixproxygroup_edit'),
    path('proxy-groups/<int:pk>/delete/', views.ZabbixProxyGroupDeleteView.as_view(), name='zabbixproxygroup_delete'),

    # ZabbixTemplate URLs
    path('templates/', views.ZabbixTemplateListView.as_view(), name='zabbixtemplate_list'),
    path('templates/add/', views.ZabbixTemplateEditView.as_view(), name='zabbixtemplate_add'),
    path('templates/<int:pk>/', views.ZabbixTemplateView.as_view(), name='zabbixtemplate'),
    path('templates/<int:pk>/edit/', views.ZabbixTemplateEditView.as_view(), name='zabbixtemplate_edit'),
    path('templates/<int:pk>/delete/', views.ZabbixTemplateDeleteView.as_view(), name='zabbixtemplate_delete'),

    # ZabbixTemplateGroup URLs
    path('template-groups/', views.ZabbixTemplateGroupListView.as_view(), name='zabbixtemplategroup_list'),
    path('template-groups/add/', views.ZabbixTemplateGroupEditView.as_view(), name='zabbixtemplategroup_add'),
    path('template-groups/<int:pk>/', views.ZabbixTemplateGroupView.as_view(), name='zabbixtemplategroup'),
    path('template-groups/<int:pk>/edit/', views.ZabbixTemplateGroupEditView.as_view(), name='zabbixtemplategroup_edit'),
    path('template-groups/<int:pk>/delete/', views.ZabbixTemplateGroupDeleteView.as_view(), name='zabbixtemplategroup_delete'),

    # ZabbixMacro URLs
    path('macros/', views.ZabbixMacroListView.as_view(), name='zabbixmacro_list'),
    path('macros/add/', views.ZabbixMacroEditView.as_view(), name='zabbixmacro_add'),
    path('macros/<int:pk>/', views.ZabbixMacroView.as_view(), name='zabbixmacro'),
    path('macros/<int:pk>/edit/', views.ZabbixMacroEditView.as_view(), name='zabbixmacro_edit'),
    path('macros/<int:pk>/delete/', views.ZabbixMacroDeleteView.as_view(), name='zabbixmacro_delete'),

    # ZabbixTag URLs
    path('tags/', views.ZabbixTagListView.as_view(), name='zabbixtag_list'),
    path('tags/add/', views.ZabbixTagEditView.as_view(), name='zabbixtag_add'),
    path('tags/<int:pk>/', views.ZabbixTagView.as_view(), name='zabbixtag'),
    path('tags/<int:pk>/edit/', views.ZabbixTagEditView.as_view(), name='zabbixtag_edit'),
    path('tags/<int:pk>/delete/', views.ZabbixTagDeleteView.as_view(), name='zabbixtag_delete'),

    # ZabbixHostGroup URLs
    path('hostgroups/', views.ZabbixHostGroupListView.as_view(), name='zabbixhostgroup_list'),
    path('hostgroups/add/', views.ZabbixHostGroupEditView.as_view(), name='zabbixhostgroup_add'),
    path('hostgroups/<int:pk>/', views.ZabbixHostGroupView.as_view(), name='zabbixhostgroup'),
    path('hostgroups/<int:pk>/edit/', views.ZabbixHostGroupEditView.as_view(), name='zabbixhostgroup_edit'),
    path('hostgroups/<int:pk>/delete/', views.ZabbixHostGroupDeleteView.as_view(), name='zabbixhostgroup_delete'),

    # ZabbixHost URLs
    path('hosts/', views.ZabbixHostListView.as_view(), name='zabbixhost_list'),
    path('hosts/add/', views.ZabbixHostEditView.as_view(), name='zabbixhost_add'),
    path('hosts/<int:pk>/', views.ZabbixHostView.as_view(), name='zabbixhost'),
    path('hosts/<int:pk>/edit/', views.ZabbixHostEditView.as_view(), name='zabbixhost_edit'),
    path('hosts/<int:pk>/delete/', views.ZabbixHostDeleteView.as_view(), name='zabbixhost_delete'),
]
