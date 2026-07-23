from django.urls import path
from . import views

urlpatterns = [
    path('servers/', views.ZabbixServersView.as_view(), name='servers'),
    path('proxies/', views.ZabbixProxiesView.as_view(), name='proxies'),
    path('proxy-groups/', views.ZabbixProxyGroupsView.as_view(), name='proxy_groups'),
    path('templates/', views.ZabbixTemplatesView.as_view(), name='templates'),
    path('template-groups/', views.ZabbixTemplateGroupsView.as_view(), name='template_groups'),
    path('macros/', views.ZabbixMacrosView.as_view(), name='macros'),
    path('tags/', views.ZabbixTagsView.as_view(), name='tags'),
    path('hostgroups/', views.ZabbixHostGroupsView.as_view(), name='hostgroups'),
    path('create-hostgroup/', views.ZabbixCreateHostGroupView.as_view(), name='create_hostgroup'),
    path('hosts/', views.ZabbixHostsView.as_view(), name='hosts'),
    path('sync-role/', views.ZabbixSyncRoleView.as_view(), name='sync_role'),
]
