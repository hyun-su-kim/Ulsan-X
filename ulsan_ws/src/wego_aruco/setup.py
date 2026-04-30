from setuptools import setup
import os
from glob import glob

package_name = 'wego_aruco'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='wego',
    maintainer_email='rpehd2904@gmail.com',
    description='ArUco 마커 기반 캘리브레이션 및 AMCL 보정 패키지',
    license='MIT',
    entry_points={
        'console_scripts': [
            'aruco_calibrator = wego_aruco.aruco_calibrator:main',
            'aruco_localizer  = wego_aruco.aruco_localizer:main',
            'waypoint_goto    = wego_aruco.waypoint_goto:main',
        ],
    },
)
