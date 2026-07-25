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
        return details, 2, "SNMPv3"
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


def get_or_create_hostgroup_id(api, role_name):
    """
    Case-insensitive lookup for Zabbix Host Group ID by role_name.
    Creates Host Group if it doesn't exist.
    """
    if not role_name:
        return "2"

    all_groups = api.get_host_groups()
    if isinstance(all_groups, list):
        for g in all_groups:
            if g.get("name", "").strip().lower() == role_name.strip().lower():
                return g.get("groupid")

    res = api.call("hostgroup.create", {"name": role_name})
    if isinstance(res, dict) and "groupids" in res and len(res["groupids"]) > 0:
        return res["groupids"][0]

    if isinstance(all_groups, list) and len(all_groups) > 0:
        return all_groups[0].get("groupid")
    return "2"


def apply_monitoring_mode(params, proxy_id_str):
    """
    Sets Zabbix 7.0 monitoring mode parameters on host payload:
    - Server: monitored_by = 0 (omit proxyid)
    - Proxy: monitored_by = 1, proxyid = proxy_id_str
    - Proxy Group: monitored_by = 2, proxy_groupid = group_id
    """
    p_str = str(proxy_id_str or "0").strip()
    if p_str == "0" or not p_str:
        params["monitored_by"] = 0
        params.pop("proxyid", None)
        params.pop("proxy_groupid", None)
    elif p_str.startswith("group_"):
        params["monitored_by"] = 2
        params["proxy_groupid"] = p_str.replace("group_", "")
        params.pop("proxyid", None)
    else:
        params["monitored_by"] = 1
        params["proxyid"] = p_str
        params.pop("proxy_groupid", None)


def execute_zabbix_host_save(api, is_update, params, proxy_id_str):
    """
    Executes host.create or host.update with Zabbix 7.0 schema compliance and version fallbacks.
    """
    apply_monitoring_mode(params, proxy_id_str)
    method = "host.update" if is_update else "host.create"
    res = api.call(method, params)

    if isinstance(res, dict) and "error" in res:
        err_msg = str(res["error"])
        logger.warning(f"[Zabbix Signal API Warning] {method} payload failed: {err_msg}. Retrying with legacy parameters...")
        
        clean_params = dict(params)
        clean_params.pop("monitored_by", None)
        clean_params.pop("proxy_groupid", None)
        
        p_str = str(proxy_id_str or "0").strip()
        if p_str != "0" and not p_str.startswith("group_"):
            clean_params["proxyid"] = p_str
            clean_params["proxy_hostid"] = p_str
        else:
            clean_params.pop("proxyid", None)
            clean_params.pop("proxy_hostid", None)

        res = api.call(method, clean_params)

    return res


# ==========================================
# DEVICE ROLE SIGNALS
# ==========================================

@receiver(pre_save, sender=DeviceRole)
def device_role_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = DeviceRole.objects.get(pk=instance.pk)
            instance._old_name = old_instance.name
        except DeviceRole.DoesNotExist:
            instance._old_name = None


@receiver(post_save, sender=DeviceRole)
def sync_device_role_to_zabbix_on_save(sender, instance, created, **kwargs):
    api = ZabbixAPI()
    role_name = instance.name

    if created:
        logger.info(f"[Zabbix Signal] NetBox DeviceRole created: '{role_name}'. Creating Host Group in Zabbix...")
        try:
            get_or_create_hostgroup_id(api, role_name)
        except Exception as e:
            logger.error(f"[Zabbix Signal Error] Failed to auto-create Zabbix Host Group for '{role_name}': {e}")
    else:
        old_name = getattr(instance, '_old_name', None)
        if old_name and old_name != role_name:
            logger.info(f"[Zabbix Signal] NetBox DeviceRole renamed from '{old_name}' to '{role_name}'. Updating Zabbix Host Group...")
            try:
                all_groups = api.get_host_groups()
                group_id = None
                if isinstance(all_groups, list):
                    for g in all_groups:
                        if g.get("name", "").strip().lower() == old_name.strip().lower():
                            group_id = g.get("groupid")
                            break
                if group_id:
                    res = api.call("hostgroup.update", {"groupid": group_id, "name": role_name})
                    logger.info(f"[Zabbix Signal] Host Group updated in Zabbix: {res}")
                else:
                    get_or_create_hostgroup_id(api, role_name)
            except Exception as e:
                logger.error(f"[Zabbix Signal Error] Failed to auto-update Zabbix Host Group for '{role_name}': {e}")


@receiver(post_delete, sender=DeviceRole)
def sync_device_role_to_zabbix_on_delete(sender, instance, **kwargs):
    api = ZabbixAPI()
    role_name = instance.name
    logger.info(f"[Zabbix Signal] NetBox DeviceRole deleted: '{role_name}'. Deleting Host Group from Zabbix...")
    try:
        all_groups = api.get_host_groups()
        if isinstance(all_groups, list):
            for g in all_groups:
                if g.get("name", "").strip().lower() == role_name.strip().lower():
                    group_id = g.get("groupid")
                    res = api.call("hostgroup.delete", [group_id])
                    logger.info(f"[Zabbix Signal] Host Group deleted from Zabbix: {res}")
                    break
    except Exception as e:
        logger.error(f"[Zabbix Signal Error] Failed to auto-delete Zabbix Host Group for '{role_name}': {e}")


# ==========================================
# DEVICE REAL-TIME SYNC SIGNALS
# ==========================================

@receiver(post_save, sender=Device)
def sync_device_to_zabbix_on_save(sender, instance, created, **kwargs):
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
        hostgroup_id = get_or_create_hostgroup_id(api, role_name)

        # 2. Configured Zabbix Settings for this Role
        settings = get_role_zabbix_settings(role_name) if role_name else {}
        mapped_tmpls = settings.get("templates", [])
        tmpl_payload = [{"templateid": str(t["id"])} for t in mapped_tmpls]

        cf_data = getattr(instance, 'custom_field_data', {}) or {}

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
            if_type_num = 2
            port_num = "161"
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

        interfaces_list = [if_payload]

        # If Agent mode, but SNMP community exists OR templates are attached, add SNMP interface as secondary
        # so SNMP templates linked to the host will not throw Zabbix API interface errors
        if if_type_str == "Agent":
            has_snmp_cf = bool(cf_data.get('snmp_community') or cf_data.get('security_name') or cf_data.get('security_level'))
            has_templates = bool(tmpl_payload)
            if has_snmp_cf or has_templates:
                snmp_details, _, _ = build_snmp_details(cf_data)
                snmp_if_payload = {
                    "type": 2,
                    "main": 1,
                    "useip": 1,
                    "ip": nb_ip,
                    "dns": "",
                    "port": "161",
                    "details": snmp_details
                }
                interfaces_list.append(snmp_if_payload)

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
                "interfaces": interfaces_list
            }
            if tmpl_payload:
                upd_params["templates"] = tmpl_payload

            res = execute_zabbix_host_save(api, True, upd_params, proxy_id)
            logger.info(f"[Zabbix Signal] Host '{device_name}' updated in Zabbix: {res}")
        else:
            create_params = {
                "host": device_name,
                "name": device_name,
                "interfaces": interfaces_list,
                "groups": [{"groupid": hostgroup_id}]
            }
            if tmpl_payload:
                create_params["templates"] = tmpl_payload

            res = execute_zabbix_host_save(api, False, create_params, proxy_id)
            logger.info(f"[Zabbix Signal] Host '{device_name}' created in Zabbix ({if_type_str}/{snmp_ver_name}): {res}")

    except Exception as e:
        logger.error(f"[Zabbix Signal Error] Failed to sync Device '{device_name}' to Zabbix: {e}")


@receiver(post_delete, sender=Device)
def sync_device_to_zabbix_on_delete(sender, instance, **kwargs):
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
