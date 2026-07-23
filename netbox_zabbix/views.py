from django.views.generic import View
from django.shortcuts import render

class ZabbixPlaceholderView(View):
    def get(self, request, title):
        return render(request, 'netbox_zabbix/placeholder.html', {'title': title})
