import logging
from django.db.models.signals import pre_save, post_save, post_delete, m2m_changed
from django.dispatch import receiver
from dcim.models import Device, DeviceRole, Site
from .zabbix_api import ZabbixAPI
from .template_storage import get_role_zabbix_settings

logger = logging.getLogger('netbox.plugins.netbox_zabbix')

import threading
_sync_state = threading.local()
_tag_sync_state = threading.local()

def is_sync_paused():
    return getattr(_sync_state, 'paused', False)

def set_sync_paused(value: bool):
    _sync_state.paused = value

def is_tag_syncing():
    return getattr(_tag_sync_state, 'active', False)

class TagSyncContext:
    def __enter__(self):
        _tag_sync_state.active = True
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        _tag_sync_state.active = False


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
        # No SNMP community found
        return None, None, None


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


def sync_device_tags_from_site(device):
    """
    Synchronizes NetBox tags from device's site to the device itself.
    If site has 'KEY:VALUE' tag (e.g. 'IMU:Jumla'), replaces any existing 'KEY:...' tag on device.
    Adds all site tags to the device if not already present.
    """
    if not device or not hasattr(device, 'site') or not device.site:
        return
    site = device.site
    if not hasattr(site, 'tags') or not hasattr(device, 'tags'):
        return

    site_tags = list(site.tags.all())
    if not site_tags:
        return

    cur_dev_tags = list(device.tags.all())
    cur_dev_tag_names = {getattr(t, 'name', str(t)) for t in cur_dev_tags}

    tags_to_add = []
    tags_to_remove = []

    for st in site_tags:
        st_name = getattr(st, 'name', str(st)).strip()
        if not st_name:
            continue

        if ':' in st_name:
            st_key, _ = st_name.split(':', 1)
            st_key_clean = st_key.strip().lower()
            # If device has existing tag with same key but different value, remove it
            for dt in cur_dev_tags:
                dt_name = getattr(dt, 'name', str(dt)).strip()
                if ':' in dt_name:
                    dt_key, _ = dt_name.split(':', 1)
                    if dt_key.strip().lower() == st_key_clean and dt_name != st_name:
                        if dt not in tags_to_remove:
                            tags_to_remove.append(dt)

        if st_name not in cur_dev_tag_names:
            tags_to_add.append(st)

    if tags_to_remove or tags_to_add:
        with TagSyncContext():
            if tags_to_remove:
                device.tags.remove(*tags_to_remove)
            if tags_to_add:
                device.tags.add(*tags_to_add)
        logger.info(f"[Zabbix Signal] Synced site tags from '{site.name}' to device '{device.name}' (Added: {[getattr(t, 'name', str(t)) for t in tags_to_add]}, Removed: {[getattr(t, 'name', str(t)) for t in tags_to_remove]}).")


def sync_site_tags_to_devices(site, old_tags=None):
    """
    Called when Site tags are changed/saved.
    Retrieves all devices in the site and updates their tags in NetBox.
    If Auto-Sync is enabled, pushes each device to Zabbix.
    """
    if not site or not hasattr(site, 'tags'):
        return

    from dcim.models import Device
    devices = list(Device.objects.filter(site=site))
    if not devices:
        return

    site_tags = list(site.tags.all())
    old_tag_names = {getattr(t, 'name', str(t)).strip() for t in (old_tags or [])}
    cur_tag_names = {getattr(t, 'name', str(t)).strip() for t in site_tags}
    removed_site_tag_names = old_tag_names - cur_tag_names

    logger.info(f"[Zabbix Signal] Site '{site.name}' tags changed. Syncing {len(devices)} devices in site...")

    updated_count = 0
    with TagSyncContext():
        for device in devices:
            if not hasattr(device, 'tags'):
                continue
            cur_dev_tags = list(device.tags.all())
            cur_dev_tag_names = {getattr(t, 'name', str(t)) for t in cur_dev_tags}

            tags_to_remove = []
            tags_to_add = []

            # 1. Remove tags that were removed from the site
            for dt in cur_dev_tags:
                dt_name = getattr(dt, 'name', str(dt)).strip()
                if dt_name in removed_site_tag_names:
                    tags_to_remove.append(dt)

            # 2. Check for key:value prefix overrides (e.g. IMU:Jumla replacing IMU:Attariya)
            for st in site_tags:
                st_name = getattr(st, 'name', str(st)).strip()
                if not st_name:
                    continue
                if ':' in st_name:
                    st_key, _ = st_name.split(':', 1)
                    st_key_clean = st_key.strip().lower()
                    for dt in cur_dev_tags:
                        dt_name = getattr(dt, 'name', str(dt)).strip()
                        if ':' in dt_name:
                            dt_key, _ = dt_name.split(':', 1)
                            if dt_key.strip().lower() == st_key_clean and dt_name != st_name:
                                if dt not in tags_to_remove:
                                    tags_to_remove.append(dt)

                if st_name not in cur_dev_tag_names:
                    tags_to_add.append(st)

            if tags_to_remove or tags_to_add:
                if tags_to_remove:
                    device.tags.remove(*tags_to_remove)
                if tags_to_add:
                    device.tags.add(*tags_to_add)
                updated_count += 1

    logger.info(f"[Zabbix Signal] Updated NetBox tags for {updated_count}/{len(devices)} devices in site '{site.name}'.")

    # If Auto-Sync is enabled, push each device to Zabbix!
    if is_sync_paused():
        logger.info(f"[Zabbix Signal] Auto-sync is paused. Skipping Zabbix push for site '{site.name}' devices.")
        return

    try:
        from .models import ZabbixSyncState
        if not ZabbixSyncState.is_enabled():
            logger.info(f"[Zabbix Signal] Auto-sync is disabled. Skipping Zabbix push for site '{site.name}' devices (use Bulk Push).")
            return
    except Exception:
        pass

    # Push to Zabbix
    for dev in devices:
        push_device_to_zabbix(dev, reason=f"Site '{site.name}' tags updated")


def build_zabbix_tags(device):
    """
    Extract tags from device's site and device itself for Zabbix host tags.
    If tag name is in format 'Key:Value' (e.g. 'IMU:Attariya'),
    maps to {'tag': 'IMU', 'value': 'Attariya'}.
    If tag name has no colon, maps to {'tag': tag_name, 'value': ''}.
    Authoritative order: site tags first, then device tags.
    Deduplicates by tag key so conflicting values for the same key are avoided.
    """
    tags_payload = []
    seen_keys = set()

    tags_sources = []
    site = getattr(device, 'site', None)
    if site and hasattr(site, 'tags'):
        tags_sources.extend(list(site.tags.all()))
    if hasattr(device, 'tags'):
        tags_sources.extend(list(device.tags.all()))

    for tag_obj in tags_sources:
        tag_name_str = getattr(tag_obj, 'name', str(tag_obj)).strip()
        if not tag_name_str:
            continue

        if ':' in tag_name_str:
            t_key, t_val = tag_name_str.split(':', 1)
            t_key = t_key.strip()
            t_val = t_val.strip()
        else:
            t_key = tag_name_str
            t_val = ""

        if not t_key:
            continue

        k_lower = t_key.lower()
        if k_lower in seen_keys:
            continue
        seen_keys.add(k_lower)
        tags_payload.append({"tag": t_key, "value": t_val})

    return tags_payload


def execute_zabbix_host_save(api, is_update, params, proxy_id_str):
    """
    Executes host.create or host.update strictly preserving configured interfaces.
    """
    apply_monitoring_mode(params, proxy_id_str)
    method = "host.update" if is_update else "host.create"
    res = api.call(method, params)

    if isinstance(res, dict) and "error" in res:
        err_msg = str(res["error"])
        logger.warning(f"[Zabbix Signal API Warning] {method} payload failed: {err_msg}. Retrying with legacy parameters...")

        # Fallback for older Zabbix versions (Zabbix 6.0/6.4)
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


def push_device_to_zabbix(device, reason=""):
    """
    Core function to push a single NetBox Device to Zabbix.
    Enforces all guard conditions before pushing:
      1. Device must have a name
      2. Device must have a Primary IP
      3. Device Role must have Zabbix settings configured (interface_type + at least 1 template OR proxy)
      4. For SNMP interface type: device must have SNMP community or SNMPv3 credentials

    Returns: (success: bool, message: str)
    """
    device_name = device.name
    if not device_name:
        return False, "Device has no name."

    # Ensure device tags in NetBox are synchronized with site tags
    try:
        sync_device_tags_from_site(device)
    except Exception as e:
        logger.debug(f"[Zabbix Signal] Error syncing site tags to device: {e}")

    # Guard 1: Primary IP required
    nb_ip = None
    if device.primary_ip4:
        nb_ip = str(device.primary_ip4.address).split('/')[0]
    elif device.primary_ip6:
        nb_ip = str(device.primary_ip6.address).split('/')[0]

    if not nb_ip:
        logger.info(f"[Zabbix] '{device_name}': No Primary IP assigned. Skipping.{' Reason: ' + reason if reason else ''}")
        return False, "No Primary IP assigned."

    # Guard 2: Zabbix settings must be FULLY configured for the role (Type + Server/Proxy + Template required)
    role_name = device.role.name if device.role else None
    settings = get_role_zabbix_settings(role_name) if role_name else {}

    if_type_str = settings.get("interface_type")
    mapped_tmpls = settings.get("templates", [])
    proxy_id = settings.get("proxy_id") or "0"

    has_all_three = bool(if_type_str) and len(mapped_tmpls) > 0
    if not has_all_three:
        missing = []
        if not if_type_str:
            missing.append("Interface Type")
        if not mapped_tmpls:
            missing.append("Templates")
        err_msg = f"Incomplete Zabbix settings for role '{role_name}' (Missing: {', '.join(missing)})."
        logger.info(f"[Zabbix] '{device_name}': {err_msg} Skipping.{' Reason: ' + reason if reason else ''}")
        return False, err_msg

    # Default interface type to SNMP if not set but templates exist
    if not if_type_str:
        if_type_str = "SNMP"

    # Guard 3: For SNMP type — community or SNMPv3 credentials required
    cf_data = getattr(device, 'custom_field_data', {}) or {}
    details_payload = None

    if if_type_str == "SNMP":
        details_payload, _, snmp_ver_name = build_snmp_details(cf_data)
        if details_payload is None:
            logger.info(f"[Zabbix] '{device_name}': SNMP type configured but no SNMP community or SNMPv3 credentials found. Skipping.{' Reason: ' + reason if reason else ''}")
            return False, "SNMP type configured but no SNMP community or SNMPv3 credentials found."
        if_type_num = 2
        port_num = "161"
    elif if_type_str == "Agent":
        if_type_num = 1
        port_num = "10050"
        snmp_ver_name = "Agent"
    elif if_type_str == "IPMI":
        if_type_num = 3
        port_num = "623"
        snmp_ver_name = "IPMI"
    elif if_type_str == "JMX":
        if_type_num = 4
        port_num = "12345"
        snmp_ver_name = "JMX"
    else:
        if_type_num = 2
        port_num = "161"
        snmp_ver_name = "SNMP"

    # Build interface payload
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
    tmpl_payload = [{"templateid": str(t["id"])} for t in mapped_tmpls]
    tags_payload = build_zabbix_tags(device)

    # Determine Zabbix host status from NetBox device status
    # status=0 → Monitored (Enabled), status=1 → Unmonitored (Disabled)
    nb_status = str(getattr(device.status, 'value', None) or getattr(device, 'status', 'active') or 'active').lower()
    zabbix_status = 0 if nb_status == 'active' else 1
    status_label = "Monitored" if zabbix_status == 0 else f"Disabled (NetBox status: {nb_status})"
    logger.info(f"[Zabbix] '{device_name}': NetBox status='{nb_status}' → Zabbix status={zabbix_status} ({status_label})")

    # Execute push
    try:
        api = ZabbixAPI()
        hostgroup_id = get_or_create_hostgroup_id(api, role_name)

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
                "interfaces": interfaces_list,
                "status": zabbix_status,
                "tags": tags_payload
            }
            if tmpl_payload:
                upd_params["templates"] = tmpl_payload

            res = execute_zabbix_host_save(api, True, upd_params, proxy_id)
            logger.info(f"[Zabbix] '{device_name}' updated in Zabbix ({if_type_str}).{' Reason: ' + reason if reason else ''} Result: {res}")
        else:
            create_params = {
                "host": device_name,
                "name": device_name,
                "interfaces": interfaces_list,
                "groups": [{"groupid": hostgroup_id}],
                "status": zabbix_status,
                "tags": tags_payload
            }
            if tmpl_payload:
                create_params["templates"] = tmpl_payload

            res = execute_zabbix_host_save(api, False, create_params, proxy_id)
            logger.info(f"[Zabbix] '{device_name}' created in Zabbix ({if_type_str}/{snmp_ver_name}).{' Reason: ' + reason if reason else ''} Result: {res}")

        if isinstance(res, dict) and "error" in res:
            return False, str(res["error"])
        return True, f"OK ({if_type_str}/{snmp_ver_name})"

    except Exception as e:
        logger.error(f"[Zabbix Error] Failed to push '{device_name}': {e}")
        return False, str(e)


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

from django.db import transaction

@receiver(post_save, sender=Device)
def sync_device_to_zabbix_on_save(sender, instance, created, raw=False, **kwargs):
    """
    Triggered on every NetBox Device save.
    Guards: Primary IP required, Zabbix settings required, SNMP credentials required for SNMP type.
    """
    if raw:
        logger.info(f"[Zabbix Signal] Skipping '{instance.name}' — raw fixture load.")
        return
    if is_sync_paused():
        logger.info(f"[Zabbix Signal] Skipping '{instance.name}' — auto-sync is paused.")
        return

    device_id = instance.pk

    def _do_device_sync():
        try:
            dev = Device.objects.get(pk=device_id)
            sync_device_tags_from_site(dev)
            from .models import ZabbixSyncState
            if not ZabbixSyncState.is_enabled():
                logger.info(f"[Zabbix Signal] Auto-sync disabled. Skipping '{dev.name}'.")
                return
            push_device_to_zabbix(dev, reason="Device saved in NetBox")
        except Exception as e:
            logger.error(f"[Zabbix Signal Error] Failed to sync device on commit: {e}")

    transaction.on_commit(_do_device_sync)


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


# ==========================================
# ZABBIX SETTINGS SAVE SIGNAL
# Auto-push all devices in a role when Zabbix settings are saved/updated
# ==========================================

def connect_zabbix_settings_signal():
    """
    Auto-sync from Host Group settings page is disabled per requirements.
    User configures parameters in Host Groups and syncs manually from Bulk Push page.
    """
    logger.info("[Zabbix Signal] Host Group settings auto-sync disabled. Parameters must be synced from Bulk Push page.")


# ==========================================
# SITE & TAG SIGNALS
# Auto-propagate Site tag changes to Devices
# Auto-push Device to Zabbix on tag change
# ==========================================

@receiver(pre_save, sender=Site)
def site_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_inst = Site.objects.get(pk=instance.pk)
            instance._old_tags = list(old_inst.tags.all())
        except Exception:
            instance._old_tags = []


@receiver(post_save, sender=Site)
def site_post_save(sender, instance, created, raw=False, **kwargs):
    if raw or is_tag_syncing():
        return
    site_id = instance.pk
    old_tags = getattr(instance, '_old_tags', None)

    def _do_site_sync():
        try:
            fresh_site = Site.objects.get(pk=site_id)
            sync_site_tags_to_devices(fresh_site, old_tags=old_tags)
        except Exception as e:
            logger.error(f"[Zabbix Signal Error] Failed to sync site tags on commit: {e}")

    transaction.on_commit(_do_site_sync)


try:
    from extras.models import TaggedItem

    @receiver(post_save, sender=TaggedItem)
    def tagged_item_post_save(sender, instance, created, **kwargs):
        if is_tag_syncing():
            return
        try:
            obj = instance.content_object
            if isinstance(obj, Site):
                sync_site_tags_to_devices(obj)
            elif isinstance(obj, Device):
                # Ensure device gets site tags if missing
                sync_device_tags_from_site(obj)
                if not is_sync_paused():
                    from .models import ZabbixSyncState
                    if ZabbixSyncState.is_enabled():
                        push_device_to_zabbix(obj, reason="Device tag added")
        except Exception as e:
            logger.debug(f"[Zabbix Signal] TaggedItem post_save error: {e}")

    @receiver(post_delete, sender=TaggedItem)
    def tagged_item_post_delete(sender, instance, **kwargs):
        if is_tag_syncing():
            return
        try:
            obj = instance.content_object
            if isinstance(obj, Site):
                sync_site_tags_to_devices(obj)
            elif isinstance(obj, Device):
                if not is_sync_paused():
                    from .models import ZabbixSyncState
                    if ZabbixSyncState.is_enabled():
                        push_device_to_zabbix(obj, reason="Device tag removed")
        except Exception as e:
            logger.debug(f"[Zabbix Signal] TaggedItem post_delete error: {e}")
except Exception as e:
    logger.warning(f"[Zabbix Signal] Could not connect TaggedItem signals: {e}")

