import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    config_dir = os.path.join(get_package_share_directory('wego_bridge'), 'config')

    return LaunchDescription([
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='bridge_limo1',
            arguments=[os.path.join(config_dir, 'bridge_limo1.yaml')],
            output='screen',
        ),
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='bridge_limo2',
            arguments=[os.path.join(config_dir, 'bridge_limo2.yaml')],
            output='screen',
        ),
    ])
