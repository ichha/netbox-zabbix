import django.db.models.deletion
import taggit.managers
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('extras', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZabbixServer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('url', models.CharField(max_length=255)),
                ('token', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='ZabbixTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(max_length=255)),
                ('value', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name', 'value'),
            },
        ),
        migrations.CreateModel(
            name='ZabbixTemplateGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('template_groupid', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='template_groups', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('zabbix_server', 'template_groupid')},
            },
        ),
        migrations.CreateModel(
            name='ZabbixTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('templateid', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('zabbix_server', 'templateid')},
            },
        ),
        migrations.CreateModel(
            name='ZabbixProxyGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('proxy_groupid', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proxy_groups', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('zabbix_server', 'proxy_groupid')},
            },
        ),
        migrations.CreateModel(
            name='ZabbixProxy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('proxyid', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('status', models.CharField(blank=True, max_length=50, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proxies', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('zabbix_server', 'proxyid')},
            },
        ),
        migrations.CreateModel(
            name='ZabbixMacro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('macro', models.CharField(max_length=255)),
                ('value', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='macros', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('macro',),
            },
        ),
        migrations.CreateModel(
            name='ZabbixHostGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('groupid', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='host_groups', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('zabbix_server', 'groupid')},
            },
        ),
        migrations.CreateModel(
            name='ZabbixHost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('hostid', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('status', models.IntegerField(default=0)),
                ('description', models.TextField(blank=True, null=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
                ('zabbix_server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hosts', to='netbox_zabbix.zabbixserver')),
            ],
            options={
                'ordering': ('name',),
                'unique_together': {('zabbix_server', 'hostid')},
            },
        ),
    ]
