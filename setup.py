from setuptools import find_packages, setup

setup(
    name='netbox-zabbix',
    version='0.1.0',
    description='A NetBox plugin to synchronize data with Zabbix.',
    install_requires=[
        'requests',
    ],
    author='Antigravity',
    author_email='antigravity@example.com',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'netbox_zabbix': ['templates/*/*', 'templates/*'],
    },
    zip_safe=False,
)
