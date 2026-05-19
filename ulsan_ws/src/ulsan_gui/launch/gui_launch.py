from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='ulsan_gui',
            executable='ulsan_gui',
            name='ulsan_gui',
            output='screen',
        ),
    ])
