from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wego_behaviour',
            executable='behaviour_node',
            name='wego_behaviour',
            output='screen',
        ),
    ])
