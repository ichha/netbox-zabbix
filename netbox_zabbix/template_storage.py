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
        'interface_type': 'SNMP', # 'SNMP', 'Agent', 'JMX', 'IPMI'
        'proxy_id': '0',          # '0' for Server, or proxyid
        'proxy_name': 'Server'
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
                        return {
                            'has_settings': entry.get('has_settings', True),
                            'templates': entry.get('templates', []),
                            'interface_type': entry.get('interface_type', 'SNMP'),
                            'proxy_id': str(entry.get('proxy_id', '0')),
                            'proxy_name': entry.get('proxy_name', 'Server')
                        }
                    elif isinstance(entry, list):
                        default_res['templates'] = entry
                        default_res['has_settings'] = len(entry) > 0
                        return default_res
    except Exception as e:
        logger.error(f"JSON file lookup failed: {e}")

    # 2. Try DB model fallback for legacy templates
    try:
        from .models import ZabbixHostGroupTemplate
        obj = ZabbixHostGroupTemplate.objects.filter(role_name=role_name).first()
        if obj and isinstance(obj.template_ids, list) and len(obj.template_ids) > 0:
            res = []
            ids = obj.template_ids
            names = obj.template_names if isinstance(obj.template_names, list) else []
            for i, tid in enumerate(ids):
                tname = names[i] if i < len(names) else f"Template {tid}"
                res.append({"id": str(tid), "name": tname})
            default_res['templates'] = res
            default_res['has_settings'] = True
            default_res['interface_type'] = 'SNMP'
            default_res['proxy_id'] = '0'
            default_res['proxy_name'] = 'Server'
            return default_res
    except Exception as e:
        logger.debug(f"DB lookup for template mapping failed: {e}")

    return default_res


def save_mapped_templates(role_name, template_ids, template_names, interface_type='SNMP', proxy_id='0', proxy_name='Server'):
    """
    Save complete Zabbix settings (Templates, Interface Type, Proxy) for role_name.
    """
    formatted_templates = [
        {"id": str(tid), "name": template_names[i] if i < len(template_names) else f"Template {tid}"}
        for i, tid in enumerate(template_ids)
    ]

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
            'interface_type': interface_type if interface_type in ['SNMP', 'Agent', 'JMX', 'IPMI'] else 'SNMP',
            'proxy_id': str(proxy_id),
            'proxy_name': proxy_name if proxy_name else 'Server'
        }

        with open(MAPPING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"JSON file save failed: {e}")

    # 2. Save legacy templates DB model
    try:
        from .models import ZabbixHostGroupTemplate
        obj, _ = ZabbixHostGroupTemplate.objects.get_or_create(role_name=role_name)
        obj.template_ids = [str(t) for t in template_ids]
        obj.template_names = template_names
        obj.save()
    except Exception as e:
        logger.debug(f"DB save for template mapping failed: {e}")


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

    # 2. Remove from DB model if present
    try:
        from .models import ZabbixHostGroupTemplate
        ZabbixHostGroupTemplate.objects.filter(role_name=role_name).delete()
    except Exception as e:
        logger.debug(f"DB delete failed: {e}")
