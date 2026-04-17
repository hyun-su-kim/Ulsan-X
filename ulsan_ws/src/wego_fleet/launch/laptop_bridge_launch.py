import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

# 노트북(domain 5)에서 실행하는 런치 파일.
#
# 실행:
#   ros2 launch wego_fleet laptop_bridge_launch.py
#
# 역할:
#   1. domain_bridge x2 실행
#      - robot1_bridge: domain 6(LIMO1) → domain 5, /amcl_pose → domain 7
#      - robot2_bridge: domain 7(LIMO2) → domain 5, /amcl_pose → domain 6
#   2. RViz 실행 (fleet_monitor.rviz: 두 로봇 위치 + 지도 표시)
#
# 전제:
#   - 각 LIMO에서 teleop_launch.py + navigation_diff_launch.py 실행 중
#   - CycloneDDS 유니캐스트 설정 (cyclone_peers.xml에 실제 IP 입력)
#   - 노트북 ROS_DOMAIN_ID=5


def generate_launch_description():
    pkg_dir = get_package_share_directory('wego_fleet')

    # ── domain_bridge: robot1 (domain 6 → domain 5, domain 7) ───────────────
    # /tf, /tf_static, /map 을 domain 5로 수신
    # /amcl_pose 를 domain 7에 /robot1/amcl_pose 로 전달
    bridge_robot1 = Node(
        package='domain_bridge',
        executable='domain_bridge',
        name='bridge_robot1',
        output='screen',
        arguments=[os.path.join(pkg_dir, 'config', 'domain_bridge_robot1.yaml')],
    )

    # ── domain_bridge: robot2 (domain 7 → domain 5, domain 6) ───────────────
    # /tf, /tf_static 을 domain 5로 수신
    # /amcl_pose 를 domain 6에 /robot2/amcl_pose 로 전달
    bridge_robot2 = Node(
        package='domain_bridge',
        executable='domain_bridge',
        name='bridge_robot2',
        output='screen',
        arguments=[os.path.join(pkg_dir, 'config', 'domain_bridge_robot2.yaml')],
    )

    # ── RViz: 두 로봇 위치 + 지도 표시 ──────────────────────────────────────
    # fleet_monitor.rviz:
    #   - Fixed frame: map
    #   - Map 표시 (/map, robot1에서 bridge)
    #   - TF 표시 (robot1/base_link, robot2/base_link 프레임 포함)
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2_fleet',
        output='screen',
        arguments=['-d', os.path.join(pkg_dir, 'rviz', 'fleet_monitor.rviz')],
    )

    return LaunchDescription([
        bridge_robot1,
        bridge_robot2,
        rviz_node,
    ])
