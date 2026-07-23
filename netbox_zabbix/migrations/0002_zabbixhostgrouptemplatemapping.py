from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_zabbix', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZabbixHostGroupTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role_name', models.CharField(max_length=255, unique=True)),
                ('template_ids', models.JSONField(blank=True, default=list)),
                ('template_names', models.JSONField(blank=True, default=list)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
            ],
            options={
                'verbose_name': 'Zabbix Host Group Template Mapping',
                'verbose_name_plural': 'Zabbix Host Group Template Mappings',
                'ordering': ('role_name',),
            },
        ),
    ]
