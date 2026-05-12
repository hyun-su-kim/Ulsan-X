from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wego_traffic',
            executable='wego_traffic_node',
            name='wego_traffic',
            output='screen',
            parameters=[{
                'pause_dist':  0.7,
                'resume_dist': 1.0,
            }],
        ),
    ])
