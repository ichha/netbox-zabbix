from setuptools import find_packages, setup

setup(
    name='netbox-zabbix',
    version='0.1.0',
    description='A NetBox plugin to synchronize data with Zabbix.',
    install_requires=[
        'requests',
    ],
    author='Nepal Telecom',
    author_email='info@ntc.net.np',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'netbox_zabbix': ['templates/*/*', 'templates/*'],
    },
    zip_safe=False,
)
