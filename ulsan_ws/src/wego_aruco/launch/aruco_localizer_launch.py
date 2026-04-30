import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg = get_package_share_directory('wego_aruco')

    return LaunchDescription([
        DeclareLaunchArgument(
            'home_key',
            default_value='home_robot1',
            description='Which home marker to target: home_robot1 or home_robot2',
        ),
        Node(
            package='wego_aruco',
            executable='aruco_localizer',
            name='aruco_localizer',
            output='screen',
            parameters=[{
                'home_key': LaunchConfiguration('home_key'),
                'markers_file': os.path.join(pkg, 'config', 'markers.yaml'),
            }],
        ),
    ])
