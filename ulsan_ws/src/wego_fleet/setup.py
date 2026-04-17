from setuptools import setup
import os
from glob import glob

package_name = 'wego_fleet'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'rviz'),   glob('rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hyun-su-kim',
    maintainer_email='todo@todo.com',
    description='멀티로봇 fleet 관리 패키지',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [],
    },
)
