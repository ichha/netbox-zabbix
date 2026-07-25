import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from dcim.models import Device, DeviceRole
from .zabbix_api import ZabbixAPI
from .template_storage import get_role_zabbix_settings

logger = logging.getLogger('netbox.plugins.netbox_zabbix')


def build_snmp_details(cf_data):
    """
    Extract SNMP v2 and v3 custom fields from NetBox Device custom_field_data
    and construct Zabbix host interface details dictionary.
    Supports both choice keys (choice1, choice2...) and string labels.
    """
    if not isinstance(cf_data, dict):
        cf_data = {}

    comm_str = str(cf_data.get('snmp_community') or '').strip()
    sec_name = str(cf_data.get('security_name') or '').strip()
    sec_level_raw = str(cf_data.get('security_level') or '').strip()
    auth_proto_raw = str(cf_data.get('authentication_protocol') or '').strip()
    auth_pass = str(cf_data.get('authentication_passphrase') or '').strip()
    priv_proto_raw = str(cf_data.get('privacy_protocol') or '').strip()
    priv_pass = str(cf_data.get('privacy_passphrase') or '').strip()
    context_name = str(cf_data.get('context_name') or '').strip()

    # Prioritize SNMPv3 if security_name or security_level or auth_pass is present
    has_v3 = bool(sec_name or sec_level_raw or auth_pass)

    if has_v3:
        sec_level_map = {
            'choice1': 0, 'noauthnopriv': 0, '0': 0,
            'choice2': 1, 'authnopriv': 1, '1': 1,
            'choice3': 2, 'authpriv': 2, '2': 2
        }
        sec_level = sec_level_map.get(sec_level_raw.lower(), 0)

        auth_proto_map = {
            'choice1': 0, 'md5': 0, '0': 0,
            'choice2': 1, 'sha1': 1, 'sha': 1, '1': 1,
            'choice3': 2, 'sha224': 2, '2': 2,
            'choice4': 3, 'sha256': 3, '3': 3,
            'choice5': 4, 'sha384': 4, '4': 4,
            'choice6': 5, 'sha512': 5, '5': 5
        }
        auth_proto = auth_proto_map.get(auth_proto_raw.lower(), 0)

        priv_proto_map = {
            'choice1': 0, 'des': 0, '0': 0,
            'choice2': 1, 'aes128': 1, 'aes': 1, '1': 1,
            'choice3': 2, 'aes192': 2, '2': 2,
            'choice4': 3, 'aes256': 3, '3': 3,
            'choice5': 4, 'aes192c': 4, 'aes192c3gpp': 4, '4': 4,
            'choice6': 5, 'aes256c': 5, 'aes256c3gpp': 5, '5': 5
        }
        priv_proto = priv_proto_map.get(priv_proto_raw.lower(), 0)

        details = {
            "version": 3,
            "securityname": sec_name,
            "securitylevel": sec_level,
            "authprotocol": auth_proto,
            "authpassphrase": auth_pass,
            "privprotocol": priv_proto,
            "privpassphrase": priv_pass,
            "contextname": context_name
        }
        return details, 2, "SNMPv3"  # Type 2 = SNMP
    elif comm_str:
        details = {
            "version": 2,
            "community": comm_str,
            "bulk": 1,
            "max_repetitions": 10
        }
        return details, 2, "SNMPv2c"
    else:
        details = {
            "version": 2,
            "community": "{$SNMP_COMMUNITY}",
            "bulk": 1,
            "max_repetitions": 10
        }
        return details, 2, "SNMPv2c (Default)"


# ==========================================
# DEVICE ROLE SIGNALS
# ==========================================

@receiver(pre_save, sender=DeviceRole)
def device_role_pre_save(sender, instance, **kwargs):
    """
    Capture existing role name before update to handle rename in Zabbix.
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


# ==========================================
# DEVICE REAL-TIME SYNC SIGNALS
# ==========================================

@receiver(post_save, sender=Device)
def sync_device_to_zabbix_on_save(sender, instance, created, **kwargs):
    """
    Automatically create or update Zabbix Host when a NetBox Device is created or updated.
    Supports Agent, SNMP, IPMI, JMX interfaces and Server / Proxy / Proxy Group monitoring modes.
    """
    nb_ip = None
    if instance.primary_ip4:
        nb_ip = str(instance.primary_ip4.address).split('/')[0]
    elif instance.primary_ip6:
        nb_ip = str(instance.primary_ip6.address).split('/')[0]

    api = ZabbixAPI()
    device_name = instance.name

    if not device_name or not nb_ip:
        logger.info(f"[Zabbix Signal] Device '{device_name}' saved without Primary IP. Skipping Zabbix host creation.")
        return

    logger.info(f"[Zabbix Signal] NetBox Device saved: '{device_name}' (IP: {nb_ip}). Syncing to Zabbix...")

    try:
        role_name = instance.role.name if instance.role else None

        # 1. Host Group ID
        hostgroup_id = None
        if role_name:
            groups = api.call("hostgroup.get", {"filter": {"name": role_name}})
            if isinstance(groups, list) and len(groups) > 0:
                hostgroup_id = groups[0].get("groupid")
            else:
                create_grp = api.call("hostgroup.create", {"name": role_name})
                if isinstance(create_grp, dict) and "groupids" in create_grp and len(create_grp["groupids"]) > 0:
                    hostgroup_id = create_grp["groupids"][0]

        if not hostgroup_id:
            groups = api.call("hostgroup.get", {"output": ["groupid", "name"]})
            if isinstance(groups, list) and len(groups) > 0:
                hostgroup_id = groups[0].get("groupid")
            else:
                hostgroup_id = "2"

        # 2. Configured Zabbix Settings for this Role
        settings = get_role_zabbix_settings(role_name) if role_name else {}
        mapped_tmpls = settings.get("templates", [])
        tmpl_payload = [{"templateid": str(t["id"])} for t in mapped_tmpls]

        # 3. Determine Interface Type & Parameters
        if_type_str = settings.get("interface_type") or "SNMP"
        if if_type_str == "Agent":
            if_type_num = 1
            port_num = "10050"
            details_payload = None
            snmp_ver_name = "Agent"
        elif if_type_str == "IPMI":
            if_type_num = 3
            port_num = "623"
            details_payload = None
            snmp_ver_name = "IPMI"
        elif if_type_str == "JMX":
            if_type_num = 4
            port_num = "12345"
            details_payload = None
            snmp_ver_name = "JMX"
        else:
            # Default to SNMP
            if_type_num = 2
            port_num = "161"
            cf_data = getattr(instance, 'custom_field_data', {}) or {}
            details_payload, _, snmp_ver_name = build_snmp_details(cf_data)

        if_payload = {
            "type": if_type_num,
            "main": 1,
            "useip": 1,
            "ip": nb_ip,
            "dns": "",
            "port": port_num
        }
        if details_payload:
            if_payload["details"] = details_payload

        # 4. Monitored By (Server / Proxy / Proxy Group)
        proxy_id = str(settings.get("proxy_id") or "0")

        # 5. Check existing Zabbix Host
        existing = api.call("host.get", {
            "filter": {"host": device_name},
            "selectInterfaces": ["interfaceid", "type", "main", "ip", "port"]
        })
        if not (isinstance(existing, list) and len(existing) > 0):
            existing = api.call("host.get", {
                "filter": {"name": device_name},
                "selectInterfaces": ["interfaceid", "type", "main", "ip", "port"]
            })

        if isinstance(existing, list) and len(existing) > 0:
            hid = existing[0].get("hostid")
            existing_ifaces = existing[0].get("interfaces", [])
            if isinstance(existing_ifaces, list) and len(existing_ifaces) > 0:
                main_iface = existing_ifaces[0]
                for ifc in existing_ifaces:
                    if str(ifc.get("main")) == "1":
                        main_iface = ifc
                        break
                if "interfaceid" in main_iface:
                    if_payload["interfaceid"] = main_iface["interfaceid"]

            upd_params = {
                "hostid": hid,
                "groups": [{"groupid": hostgroup_id}],
                "interfaces": [if_payload]
            }
            if tmpl_payload:
                upd_params["templates"] = tmpl_payload

            if proxy_id == "0":
                upd_params["monitored_by"] = 0
                upd_params["proxyid"] = "0"
            elif proxy_id.startswith("group_"):
                upd_params["monitored_by"] = 2
                upd_params["proxy_groupid"] = proxy_id.replace("group_", "")
                upd_params["proxyid"] = "0"
            else:
                upd_params["monitored_by"] = 1
                upd_params["proxyid"] = proxy_id

            res = api.call("host.update", upd_params)
            logger.info(f"[Zabbix Signal] Host '{device_name}' updated in Zabbix: {res}")
        else:
            create_params = {
                "host": device_name,
                "name": device_name,
                "interfaces": [if_payload],
                "groups": [{"groupid": hostgroup_id}]
            }
            if tmpl_payload:
                create_params["templates"] = tmpl_payload

            if proxy_id == "0":
                create_params["monitored_by"] = 0
                create_params["proxyid"] = "0"
            elif proxy_id.startswith("group_"):
                create_params["monitored_by"] = 2
                create_params["proxy_groupid"] = proxy_id.replace("group_", "")
                create_params["proxyid"] = "0"
            else:
                create_params["monitored_by"] = 1
                create_params["proxyid"] = proxy_id

            res = api.call("host.create", create_params)
            logger.info(f"[Zabbix Signal] Host '{device_name}' created in Zabbix ({if_type_str}/{snmp_ver_name}): {res}")

    except Exception as e:
        logger.error(f"[Zabbix Signal Error] Failed to sync Device '{device_name}' to Zabbix: {e}")


@receiver(post_delete, sender=Device)
def sync_device_to_zabbix_on_delete(sender, instance, **kwargs):
    """
    Automatically delete Zabbix Host when a NetBox Device is deleted.
    """
    api = ZabbixAPI()
    device_name = instance.name
    if not device_name:
        return

    logger.info(f"[Zabbix Signal] NetBox Device deleted: '{device_name}'. Deleting Host from Zabbix...")
    try:
        existing = api.call("host.get", {"filter": {"host": device_name}})
        if not (isinstance(existing, list) and len(existing) > 0):
            existing = api.call("host.get", {"filter": {"name": device_name}})

        if isinstance(existing, list) and len(existing) > 0:
            hid = existing[0].get("hostid")
            res = api.call("host.delete", [hid])
            logger.info(f"[Zabbix Signal] Host '{device_name}' deleted from Zabbix: {res}")
    except Exception as e:
        logger.error(f"[Zabbix Signal Error] Failed to delete Host '{device_name}' from Zabbix: {e}")
