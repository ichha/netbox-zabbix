import os
import json
import logging

logger = logging.getLogger('netbox.plugins.netbox_zabbix')

MAPPING_FILE = os.path.join(os.path.dirname(__file__), 'hostgroup_zabbix_settings.json')


def get_mapped_templates(role_name):
    """
    Retrieve list of dicts [{'id': '10001', 'name': 'Linux by Zabbix agent'}] for role_name.
    """
    settings = get_role_zabbix_settings(role_name)
    return settings.get('templates', [])


def get_role_zabbix_settings(role_name):
    """
    Retrieve complete Zabbix settings for a NetBox Role / Host Group.
    Returns dict:
    {
        'has_settings': True/False,
        'templates': [{'id': '10001', 'name': 'Template Name'}],
        'interface_type': 'SNMP', # 'SNMP', 'Agent', 'JMX', 'IPMI', or None
        'proxy_id': '0',          # '0' for Server, or proxyid, or None
        'proxy_name': 'Server'    # 'Server' or 'Proxy: name' or None
    }
    """
    default_res = {
        'has_settings': False,
        'templates': [],
        'interface_type': None,
        'proxy_id': None,
        'proxy_name': None
    }

    # 1. Try JSON storage
    try:
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, 'r') as f:
                data = json.load(f)
                if role_name in data:
                    entry = data[role_name]
                    if isinstance(entry, dict):
                        tmpls = entry.get('templates', [])
                        itype = entry.get('interface_type')
                        pxid = entry.get('proxy_id')
                        pxname = entry.get('proxy_name')

                        has_st = bool(tmpls) or bool(itype) or pxid is not None
                        return {
                            'has_settings': has_st,
                            'templates': tmpls,
                            'interface_type': itype if itype else None,
                            'proxy_id': str(pxid) if pxid is not None and str(pxid) != "" else None,
                            'proxy_name': pxname if pxname else None
                        }
                    elif isinstance(entry, list):
                        default_res['templates'] = entry
                        default_res['has_settings'] = len(entry) > 0
                        return default_res
    except Exception as e:
        logger.error(f"JSON file lookup failed: {e}")

    # 2. Try DB model fallback
    try:
        from .models import ZabbixHostGroupTemplate
        obj = ZabbixHostGroupTemplate.objects.filter(role_name=role_name).first()
        if obj:
            res = []
            ids = obj.template_ids if isinstance(obj.template_ids, list) else []
            names = obj.template_names if isinstance(obj.template_names, list) else []
            for i, tid in enumerate(ids):
                tname = names[i] if i < len(names) else f"Template {tid}"
                res.append({"id": str(tid), "name": tname})
            
            itype = obj.interface_type if obj.interface_type else None
            pxid = str(obj.proxy_id) if obj.proxy_id is not None and str(obj.proxy_id) != "" else None
            pxname = obj.proxy_name if obj.proxy_name else None

            has_st = bool(res) or bool(itype) or pxid is not None

            return {
                'has_settings': has_st,
                'templates': res,
                'interface_type': itype,
                'proxy_id': pxid,
                'proxy_name': pxname
            }
    except Exception as e:
        logger.debug(f"DB lookup for ZabbixHostGroupTemplate failed: {e}")

    return default_res


def save_mapped_templates(role_name, template_ids, template_names, interface_type=None, proxy_id=None, proxy_name=None):
    """
    Save Zabbix settings (Templates, Interface Type, Proxy) for role_name.
    """
    formatted_templates = [
        {"id": str(tid), "name": template_names[i] if i < len(template_names) else f"Template {tid}"}
        for i, tid in enumerate(template_ids)
    ]

    valid_itype = interface_type if interface_type in ['SNMP', 'Agent', 'JMX', 'IPMI'] else None
    valid_pxid = str(proxy_id) if proxy_id is not None and str(proxy_id) != "" else None
    valid_pxname = proxy_name if proxy_name else None

    # 1. Save to JSON file
    try:
        data = {}
        if os.path.exists(MAPPING_FILE):
            try:
                with open(MAPPING_FILE, 'r') as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data[role_name] = {
            'has_settings': True,
            'templates': formatted_templates,
            'interface_type': valid_itype,
            'proxy_id': valid_pxid,
            'proxy_name': valid_pxname
        }

        with open(MAPPING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"JSON file save failed: {e}")

    # 2. Save to DB model
    try:
        from .models import ZabbixHostGroupTemplate
        obj, _ = ZabbixHostGroupTemplate.objects.get_or_create(role_name=role_name)
        obj.template_ids = [str(t) for t in template_ids]
        obj.template_names = template_names
        obj.interface_type = valid_itype
        obj.proxy_id = valid_pxid
        obj.proxy_name = valid_pxname
        obj.save()
    except Exception as e:
        logger.debug(f"DB save for template mapping failed: {e}")


def remove_role_setting_field(role_name, field_name):
    """
    Remove specific field setting ('interface_type' or 'proxy') for role_name.
    """
    # 1. JSON file update
    try:
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, 'r') as f:
                data = json.load(f)

            if role_name in data and isinstance(data[role_name], dict):
                entry = data[role_name]
                if field_name == 'interface_type':
                    entry['interface_type'] = None
                elif field_name in ['proxy', 'proxy_id', 'proxy_name']:
                    entry['proxy_id'] = None
                    entry['proxy_name'] = None

                tmpls = entry.get('templates', [])
                itype = entry.get('interface_type')
                pxid = entry.get('proxy_id')

                if not tmpls and not itype and pxid is None:
                    del data[role_name]
                else:
                    data[role_name] = entry

                with open(MAPPING_FILE, 'w') as f:
                    json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to remove setting field '{field_name}' in JSON for '{role_name}': {e}")

    # 2. DB model update
    try:
        from .models import ZabbixHostGroupTemplate
        obj = ZabbixHostGroupTemplate.objects.filter(role_name=role_name).first()
        if obj:
            if field_name == 'interface_type':
                obj.interface_type = None
            elif field_name in ['proxy', 'proxy_id', 'proxy_name']:
                obj.proxy_id = None
                obj.proxy_name = None

            if not obj.template_ids and not obj.interface_type and obj.proxy_id is None:
                obj.delete()
            else:
                obj.save()
    except Exception as e:
        logger.debug(f"Failed to remove setting field '{field_name}' in DB for '{role_name}': {e}")


def remove_role_zabbix_settings(role_name):
    """
    Completely remove configured Zabbix settings for role_name.
    """
    # 1. Remove from JSON file
    try:
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, 'r') as f:
                data = json.load(f)
            if role_name in data:
                del data[role_name]
                with open(MAPPING_FILE, 'w') as f:
                    json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"JSON file remove failed: {e}")

    # 2. Remove from DB model
    try:
        from .models import ZabbixHostGroupTemplate
        ZabbixHostGroupTemplate.objects.filter(role_name=role_name).delete()
    except Exception as e:
        logger.debug(f"DB delete failed: {e}")
