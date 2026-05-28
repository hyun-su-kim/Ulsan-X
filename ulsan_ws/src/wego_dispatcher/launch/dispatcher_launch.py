import os

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wego_dispatcher',
            executable='dispatcher_node',
            name='wego_dispatcher',
            output='screen',
            parameters=[{
                'api_base': os.environ.get('FASTAPI_URL', 'http://localhost:8000'),
            }],
        ),
    ])
