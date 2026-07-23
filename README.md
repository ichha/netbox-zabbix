# NetBox Zabbix Plugin (`netbox-zabbix`)

A NetBox plugin to integrate and view live monitoring parameters from **Zabbix**.

## Compatibility

- **Zabbix Versions**: Fully supports **Zabbix 7.0 LTS (v7.0.22+)**, **Zabbix 7.2+**, **Zabbix 7.4+**, **Zabbix 8.0+**, as well as Zabbix 6.0 LTS.
- **NetBox Versions**: NetBox **v4.0+**, **v4.5.9+**.

## Features

- **Live Dashboard Overview**: Real-time connection metrics for Hosts, Templates, Proxies, Host Groups, Macros, and Tags.
- **Zabbix 7.0+ Native Proxy Support**: Monitors active/passive proxy status, versions, and proxy group assignments.
- **Host Protocol & Monitoring Info**: Displays live SNMP, Agent, IPMI, JMX interface types, ports, and proxy/server designations (`Proxy: <name>` vs `Server`).
- **NetBox UI & Pagination**: NetBox breadcrumbs, quick search filtering, per-page dropdown selection (25, 50, 100, 250, 500, All), and page navigation.

## Installation

1. Add `netbox-zabbix` to your NetBox Docker `plugin_requirements.txt`:
   ```text
   git+https://github.com/ichha/netbox-zabbix.git
   ```

2. Enable the plugin in NetBox `PLUGINS`:
   ```python
   PLUGINS = [
       'netbox_zabbix',
   ]

   PLUGINS_CONFIG = {
       'netbox_zabbix': {
           'zabbix_url': 'http://10.26.192.125/zabbix/api_jsonrpc.php',
           'zabbix_token': '7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61',
       },
   }
   ```

3. Rebuild and restart NetBox Docker containers:
   ```bash
   docker compose build --no-cache
   docker compose down && docker compose up -d
   ```
