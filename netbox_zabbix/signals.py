import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from dcim.models import DeviceRole
from .zabbix_api import ZabbixAPI

logger = logging.getLogger('netbox.plugins.netbox_zabbix')


@receiver(pre_save, sender=DeviceRole)
def device_role_pre_save(sender, instance, **kwargs):
    """
    Capture the existing role name before update to handle rename in Zabbix.
    """
    if instance.pk:
        try:
            old_instance = DeviceRole.objects.get(pk=instance.pk)
            instance._old_name = old_instance.name
        except DeviceRole.DoesNotExist:
            instance._old_name = None


@receiver(post_save, sender=DeviceRole)
def sync_device_role_to_zabbix_on_save(sender, instance, created, **kwargs):
    """
    Automatically create or rename Zabbix Host Group when a NetBox DeviceRole is saved.
    """
    api = ZabbixAPI()
    role_name = instance.name

    if created:
        logger.info(f"[Zabbix Signal] NetBox DeviceRole created: '{role_name}'. Creating Host Group in Zabbix...")
        try:
            groups = api.call("hostgroup.get", {"filter": {"name": role_name}})
            if isinstance(groups, list) and len(groups) == 0:
                res = api.call("hostgroup.create", {"name": role_name})
                logger.info(f"[Zabbix Signal] Host Group '{role_name}' created in Zabbix: {res}")
        except Exception as e:
            logger.error(f"[Zabbix Signal Error] Failed to auto-create Zabbix Host Group for '{role_name}': {e}")
    else:
        old_name = getattr(instance, '_old_name', None)
        if old_name and old_name != role_name:
            logger.info(f"[Zabbix Signal] NetBox DeviceRole renamed from '{old_name}' to '{role_name}'. Updating Zabbix Host Group...")
            try:
                groups = api.call("hostgroup.get", {"filter": {"name": old_name}})
                if isinstance(groups, list) and len(groups) > 0:
                    group_id = groups[0].get("groupid")
                    res = api.call("hostgroup.update", {"groupid": group_id, "name": role_name})
                    logger.info(f"[Zabbix Signal] Host Group updated in Zabbix: {res}")
                else:
                    # If old name not found, create new group
                    api.call("hostgroup.create", {"name": role_name})
            except Exception as e:
                logger.error(f"[Zabbix Signal Error] Failed to auto-update Zabbix Host Group for '{role_name}': {e}")


@receiver(post_delete, sender=DeviceRole)
def sync_device_role_to_zabbix_on_delete(sender, instance, **kwargs):
    """
    Automatically delete Zabbix Host Group when a NetBox DeviceRole is deleted.
    """
    api = ZabbixAPI()
    role_name = instance.name
    logger.info(f"[Zabbix Signal] NetBox DeviceRole deleted: '{role_name}'. Deleting Host Group from Zabbix...")
    try:
        groups = api.call("hostgroup.get", {"filter": {"name": role_name}})
        if isinstance(groups, list) and len(groups) > 0:
            group_id = groups[0].get("groupid")
            res = api.call("hostgroup.delete", [group_id])
            logger.info(f"[Zabbix Signal] Host Group deleted from Zabbix: {res}")
    except Exception as e:
        logger.error(f"[Zabbix Signal Error] Failed to auto-delete Zabbix Host Group for '{role_name}': {e}")
