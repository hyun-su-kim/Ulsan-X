# 실행 위치: 관제 노트북 (ROS_DOMAIN_ID=5)
#
# 멀티로봇 도메인 격리 구조:
#   LIMO 1 — domain 6,  LIMO 2 — domain 7,  관제/트래픽 — domain 5
#
# ROS2 DDS는 같은 domain_id 내에서만 통신하므로
# domain_bridge 없이는 관제 노트북이 LIMO의 amcl_pose를 수신하거나
# LIMO에게 pause/resume을 전달할 수 없다.
#
# bridge_limo1.yaml: domain 6 ↔ domain 5 양방향
#   /amcl_pose      (6→5, /limo1/amcl_pose 로 리맵)
#   /robot_status   (6→5, /limo1/robot_status 로 리맵)
#   /limo1/pause    (5→6, /pause 로 리맵)
#   /limo1/resume   (5→6, /resume 로 리맵)
#
# bridge_limo2.yaml: domain 7 ↔ domain 5 양방향 (같은 구조)

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    config_dir = os.path.join(get_package_share_directory('wego_bridge'), 'config')

    return LaunchDescription([
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='bridge_limo1',
            arguments=[os.path.join(config_dir, 'bridge_limo1.yaml')],
            output='screen',
        ),
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='bridge_limo2',
            arguments=[os.path.join(config_dir, 'bridge_limo2.yaml')],
            output='screen',
        ),
    ])
