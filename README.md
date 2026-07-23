# NetBox Zabbix Sync Plugin

This plugin integrates NetBox with Zabbix, allowing you to configure Zabbix servers, sync Zabbix data (proxies, templates, macros, tags, host groups, and hosts) into NetBox, and view them directly within the NetBox administration interface.

## Features
- **Sidebar Integration**: Adds a clean, dedicated **ZABBIX** sidebar menu.
- **Full Object Tracking**: Track Zabbix Servers, Proxies, Proxy Groups, Templates, Template Groups, Global Macros, Tags, Host Groups, and Hosts.
- **Dynamic Zabbix Sync**: A "Sync from Zabbix" action button on the Zabbix Server details page downloads and populates the records dynamically using Zabbix's JSON-RPC API.
- **Modern Bootstrap 5 UI**: Matches the NetBox design language seamlessly.

---

## Installation

### 1. Install the Plugin Package
From your NetBox server environment (with the virtual environment active):
```bash
pip install -e /path/to/netbox-zabbix
```
*(Or add the path of the directory to your `local_requirements.txt` file and run `pip install -r local_requirements.txt` if you run NetBox in Docker).*

### 2. Enable in NetBox Config
Open your NetBox configuration file (usually `configuration.py` or `configuration/plugins.py` if using docker):
```python
PLUGINS = [
    'netbox_zabbix',
]

PLUGINS_CONFIG = {
    'netbox_zabbix': {
        # Default settings if none are provided
        'zabbix_url': 'http://10.26.192.125/zabbix/api_jsonrpc.php',
        'zabbix_token': '7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61',
    }
}
```

### 3. Run Database Migrations
Generate and apply database migrations to create the plugin's tables:
```bash
python manage.py makemigrations netbox_zabbix
python manage.py migrate
```

### 4. Restart NetBox
Restart the NetBox web service and any background workers:
```bash
sudo systemctl restart netbox netbox-rq
```
*(Or `docker compose restart` if running inside Docker).*

---

## Usage

1. Open NetBox and look for the new **ZABBIX** sidebar menu section.
2. Click **Servers** -> Click **Add** (`+`) button -> Register your Zabbix server:
   - **Name**: e.g., `Zabbix Primary`
   - **API URL**: `http://10.26.192.125/zabbix/api_jsonrpc.php`
   - **API Token**: `7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61`
3. Click **Save**.
4. On the Zabbix Server details screen, click the **Sync from Zabbix** button.
5. All proxies, templates, groups, macros, tags, and hosts from the Zabbix instance will be populated in NetBox!
