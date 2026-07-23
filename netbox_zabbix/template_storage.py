import os
import json
import logging

logger = logging.getLogger('netbox.plugins.netbox_zabbix')

MAPPING_FILE = os.path.join(os.path.dirname(__file__), 'hostgroup_templates.json')


def get_mapped_templates(role_name):
    """
    Retrieve list of dicts [{'id': '10001', 'name': 'Linux by Zabbix agent'}] for role_name.
    """
    # 1. Try Database model first
    try:
        from .models import ZabbixHostGroupTemplate
        obj = ZabbixHostGroupTemplate.objects.filter(role_name=role_name).first()
        if obj and isinstance(obj.template_ids, list):
            res = []
            ids = obj.template_ids
            names = obj.template_names if isinstance(obj.template_names, list) else []
            for i, tid in enumerate(ids):
                tname = names[i] if i < len(names) else f"Template {tid}"
                res.append({"id": str(tid), "name": tname})
            return res
    except Exception as e:
        logger.debug(f"DB lookup for template mapping failed: {e}")

    # 2. Try JSON file storage fallback
    try:
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, 'r') as f:
                data = json.load(f)
                return data.get(role_name, [])
    except Exception as e:
        logger.error(f"JSON file lookup failed: {e}")

    return []


def save_mapped_templates(role_name, template_ids, template_names):
    """
    Save template mapping for role_name.
    """
    # 1. Save to Database
    try:
        from .models import ZabbixHostGroupTemplate
        obj, _ = ZabbixHostGroupTemplate.objects.get_or_create(role_name=role_name)
        obj.template_ids = [str(t) for t in template_ids]
        obj.template_names = template_names
        obj.save()
    except Exception as e:
        logger.debug(f"DB save for template mapping failed: {e}")

    # 2. Save to JSON file fallback
    try:
        data = {}
        if os.path.exists(MAPPING_FILE):
            try:
                with open(MAPPING_FILE, 'r') as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data[role_name] = [
            {"id": str(tid), "name": template_names[i] if i < len(template_names) else f"Template {tid}"}
            for i, tid in enumerate(template_ids)
        ]

        with open(MAPPING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"JSON file save failed: {e}")
