from django.urls import path
from . import views

urlpatterns = [
    path('servers/', views.ZabbixPlaceholderView.as_view(), {'title': 'Servers'}, name='servers'),
    path('proxies/', views.ZabbixPlaceholderView.as_view(), {'title': 'Proxies'}, name='proxies'),
    path('proxy-groups/', views.ZabbixPlaceholderView.as_view(), {'title': 'Proxy Groups'}, name='proxy_groups'),
    path('templates/', views.ZabbixPlaceholderView.as_view(), {'title': 'Templates'}, name='templates'),
    path('template-groups/', views.ZabbixPlaceholderView.as_view(), {'title': 'Template Groups'}, name='template_groups'),
    path('macros/', views.ZabbixPlaceholderView.as_view(), {'title': 'Macros'}, name='macros'),
    path('tags/', views.ZabbixPlaceholderView.as_view(), {'title': 'Tags'}, name='tags'),
    path('hostgroups/', views.ZabbixPlaceholderView.as_view(), {'title': 'Hostgroups'}, name='hostgroups'),
    path('hosts/', views.ZabbixPlaceholderView.as_view(), {'title': 'Hosts'}, name='hosts'),
]
