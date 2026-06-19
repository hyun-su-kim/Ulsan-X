import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    params = os.path.join(
        get_package_share_directory('ulsan_voice'), 'config', 'voice_params.yaml'
    )
    return LaunchDescription([
        Node(
            package='ulsan_voice',
            executable='voice_node',
            name='voice_node',
            parameters=[params],
            output='screen',
        )
    ])
