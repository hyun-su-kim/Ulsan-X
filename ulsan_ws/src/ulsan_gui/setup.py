from setuptools import find_packages, setup

package_name = 'ulsan_gui'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/gui_launch.py', 'launch/server_launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cks2904',
    maintainer_email='rpehd2904@gmail.com',
    description='관제 대시보드 — PyQt5 기반 wego 멀티로봇 모니터링 UI',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'ulsan_gui = ulsan_gui.main:main',
        ],
    },
)
