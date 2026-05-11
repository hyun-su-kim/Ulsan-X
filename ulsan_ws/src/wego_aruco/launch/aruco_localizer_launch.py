import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg = get_package_share_directory('wego_aruco')

    return LaunchDescription([
        Node(
            package='wego_aruco',
            executable='aruco_pose_corrector',
            name='aruco_pose_corrector',
            output='screen',
            parameters=[{
                'markers_file': os.path.join(pkg, 'config', 'markers.yaml'),
            }],
        ),
    ])
