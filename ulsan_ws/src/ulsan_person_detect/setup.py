from setuptools import find_packages, setup

package_name = 'ulsan_person_detect'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ulsan',
    maintainer_email='ulsan@todo.todo',
    description='YOLOv8 person detection with depth gating for Nav2 BT pause/resume',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'person_detect_node = ulsan_person_detect.person_detect_node:main',
        ],
    },
)
