from setuptools import find_packages, setup
from glob import glob

package_name = 'wego_dispatcher'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='yechan',
    maintainer_email='rpehd2904@gmail.com',
    description='Mission dispatcher: bridges tablet UI and ROS robots via FastAPI polling',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dispatcher_node = wego_dispatcher.dispatcher_node:main',
        ],
    },
)
