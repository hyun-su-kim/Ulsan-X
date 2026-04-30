from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wego_aruco',
            executable='aruco_calibrator',
            name='aruco_calibrator',
            output='screen',
            # 터미널 입력을 받아야 하므로 emulate_tty 활성화
            emulate_tty=True,
        )
    ])
