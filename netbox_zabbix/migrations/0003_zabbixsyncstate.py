from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_zabbix', '0002_zabbixhostgrouptemplatemapping'),
    ]
    operations = [
        migrations.CreateModel(
            name='ZabbixSyncState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('auto_sync_enabled', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Zabbix Sync State'},
        ),
    ]
