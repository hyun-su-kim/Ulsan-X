from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wego_aruco',
            executable='aruco_localizer',
            name='aruco_localizer',
            output='screen',
            parameters=[{
                'correction_interval': 2.0,   # 보정 발행 최소 간격 (초)
                'max_marker_distance': 2.0,   # 마커 감지 최대 거리 (m)
            }],
        )
    ])
