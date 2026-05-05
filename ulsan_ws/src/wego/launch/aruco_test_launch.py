"""임시 편의 런치 — ArUco 정밀 정차 테스트용 (2026-05-04)

포함 노드/런치:
  1. wego        teleop_launch.py            (드라이버)
  2. wego        navigation_diff_launch.py   (Nav2 통합, RViz 없음)
  3. wego_behaviour  behaviour_node          (FSM, home_key:=home_robot1)
  4. wego_aruco   aruco_localizer_launch.py  (ArUco visual servoing)

goal_test_node는 별도 터미널에서 실행:
  ros2 run wego_behaviour goal_test_node
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    wego_pkg = get_package_share_directory('wego')
    aruco_pkg = get_package_share_directory('wego_aruco')

    return LaunchDescription([
        # 1. 드라이버 (LiDAR, base, EKF)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [wego_pkg, '/launch/teleop_launch.py']
            ),
        ),

        # 2. Nav2 통합 (AMCL + Nav2 + map_server), RViz 없음
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [wego_pkg, '/launch/navigation_diff_launch.py']
            ),
            launch_arguments={'use_rviz': 'false'}.items(),
        ),

        # 3. FSM (IDLE → GUIDING → RETURNING)
        Node(
            package='wego_behaviour',
            executable='behaviour_node',
            name='behaviour_node',
            output='screen',
            parameters=[{'home_key': 'home_robot1'}],
        ),

        # 4. ArUco visual servoing + AMCL 리셋
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [aruco_pkg, '/launch/aruco_localizer_launch.py']
            ),
            launch_arguments={'home_key': 'home_robot1'}.items(),
        ),
    ])
