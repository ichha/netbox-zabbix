import logging

logger = logging.getLogger('netbox.plugins.netbox_zabbix')


def get_mapped_templates(role_name):
    """
    Retrieve list of dicts [{'id': '10001', 'name': 'Linux by Zabbix agent'}] for role_name.
    """
    settings = get_role_zabbix_settings(role_name)
    return settings.get('templates', [])


def get_role_zabbix_settings(role_name):
    """
    Retrieve complete Zabbix settings for a NetBox Role / Host Group directly from PostgreSQL DB.
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

    try:
        from .models import ZabbixHostGroupTemplate
        obj = ZabbixHostGroupTemplate.objects.filter(role_name=role_name).first()
        if obj:
            res = []
            ids = obj.template_ids if isinstance(obj.template_ids, list) else []
            tnames = obj.template_names

            if isinstance(tnames, dict):
                names_list = tnames.get('names', [])
                itype = tnames.get('interface_type')
                pxid = tnames.get('proxy_id')
                pxname = tnames.get('proxy_name')
            elif isinstance(tnames, list):
                names_list = tnames
                itype = None
                pxid = None
                pxname = None
            else:
                names_list = []
                itype = None
                pxid = None
                pxname = None

            for i, tid in enumerate(ids):
                tname = names_list[i] if i < len(names_list) else f"Template {tid}"
                res.append({"id": str(tid), "name": tname})

            valid_pxid = str(pxid) if pxid is not None and str(pxid) != "" else "0"
            valid_itype = itype if itype in ['SNMP', 'Agent', 'JMX', 'IPMI'] else None

            has_st = bool(res) and bool(valid_itype)

            return {
                'has_settings': has_st,
                'templates': res,
                'interface_type': valid_itype,
                'proxy_id': valid_pxid,
                'proxy_name': pxname if pxname else ('Server' if valid_pxid == '0' else None)
            }
    except Exception as e:
        logger.error(f"Error retrieving Zabbix settings for '{role_name}': {e}")

    return default_res


def save_mapped_templates(role_name, template_ids, template_names, interface_type=None, proxy_id=None, proxy_name=None):
    """
    Save Zabbix settings (Templates, Interface Type, Proxy) for role_name into PostgreSQL DB.
    """
    valid_itype = interface_type if interface_type in ['SNMP', 'Agent', 'JMX', 'IPMI'] else None
    valid_pxid = str(proxy_id) if proxy_id is not None and str(proxy_id) != "" else None
    valid_pxname = proxy_name if proxy_name else None

    payload_names = {
        'names': template_names,
        'interface_type': valid_itype,
        'proxy_id': valid_pxid,
        'proxy_name': valid_pxname
    }

    try:
        from .models import ZabbixHostGroupTemplate
        obj, _ = ZabbixHostGroupTemplate.objects.get_or_create(role_name=role_name)
        obj.template_ids = [str(t) for t in template_ids]
        obj.template_names = payload_names
        obj.save()
        logger.info(f"Successfully saved Zabbix settings for role '{role_name}' in DB (Type: {valid_itype}, Proxy: {valid_pxname})")
    except Exception as e:
        logger.error(f"Error saving Zabbix settings for '{role_name}': {e}")


def remove_role_setting_field(role_name, field_name):
    """
    Remove specific field setting ('interface_type' or 'proxy') for role_name.
    """
    try:
        from .models import ZabbixHostGroupTemplate
        obj = ZabbixHostGroupTemplate.objects.filter(role_name=role_name).first()
        if obj:
            tnames = obj.template_names if isinstance(obj.template_names, dict) else {'names': obj.template_names if isinstance(obj.template_names, list) else []}

            if field_name == 'interface_type':
                tnames['interface_type'] = None
            elif field_name in ['proxy', 'proxy_id', 'proxy_name']:
                tnames['proxy_id'] = None
                tnames['proxy_name'] = None

            obj.template_names = tnames

            has_tmpls = bool(obj.template_ids)
            has_itype = bool(tnames.get('interface_type'))
            has_proxy = tnames.get('proxy_id') is not None

            if not has_tmpls and not has_itype and not has_proxy:
                obj.delete()
            else:
                obj.save()
    except Exception as e:
        logger.error(f"Error removing setting field '{field_name}' for '{role_name}': {e}")


def remove_role_zabbix_settings(role_name):
    """
    Completely remove configured Zabbix settings for role_name.
    """
    try:
        from .models import ZabbixHostGroupTemplate
        ZabbixHostGroupTemplate.objects.filter(role_name=role_name).delete()
    except Exception as e:
        logger.error(f"Error deleting Zabbix settings for '{role_name}': {e}")
