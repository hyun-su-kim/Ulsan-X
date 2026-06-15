import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg = get_package_share_directory('wego_aruco')
    markers_file = os.path.join(pkg, 'config', 'markers.yaml')

    domain = os.environ.get('ROS_DOMAIN_ID', '6')
    domain_home_map = {'6': 'home_robot1', '7': 'home_robot2'}
    home_key = domain_home_map.get(domain, 'home_robot1')

    # target_dist는 "home 정차 시 마커까지 실측 depth" — 로봇(카메라 개체차)마다 다름.
    # LIMO1(dom6)=0.480, LIMO2(dom7)=0.471 (aruco_measure 실측, lateral~0/yaw~0)
    domain_target_dist = {'6': 0.480, '7': 0.471}
    target_dist = domain_target_dist.get(domain, 0.519)

    return LaunchDescription([
        Node(
            package='wego_aruco',
            executable='aruco_home_dock',
            name='aruco_home_dock',
            output='screen',
            parameters=[{
                'markers_file': markers_file,
                'home_key':     home_key,
                'target_dist':  target_dist,
                'rho_tol':      0.02,
                'yaw_tol':      0.04,
                'max_linear':   0.08,
                'max_angular':  0.3,
                # 단계 분리(staged) 게인
                'kp_turn':      0.8,
                'kp_drive':     0.4,
                'kp_steer':     0.6,
                'alpha_tol':    0.05,
            }],
        ),
    ])
