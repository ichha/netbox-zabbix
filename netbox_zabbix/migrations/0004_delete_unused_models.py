from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_zabbix', '0003_zabbixsyncstate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='zabbixsyncstate',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.DeleteModel(
            name='ZabbixHost',
        ),
        migrations.DeleteModel(
            name='ZabbixHostGroup',
        ),
        migrations.DeleteModel(
            name='ZabbixMacro',
        ),
        migrations.DeleteModel(
            name='ZabbixProxy',
        ),
        migrations.DeleteModel(
            name='ZabbixProxyGroup',
        ),
        migrations.DeleteModel(
            name='ZabbixTag',
        ),
        migrations.DeleteModel(
            name='ZabbixTemplate',
        ),
        migrations.DeleteModel(
            name='ZabbixTemplateGroup',
        ),
        migrations.DeleteModel(
            name='ZabbixServer',
        ),
    ]
