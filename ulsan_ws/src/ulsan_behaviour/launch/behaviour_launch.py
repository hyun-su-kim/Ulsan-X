from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='ulsan_behaviour',
            executable='behaviour_node',
            name='ulsan_behaviour',
            output='screen',
        ),
    ])
