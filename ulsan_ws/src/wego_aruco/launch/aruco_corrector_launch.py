import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg = get_package_share_directory('wego_aruco')
    markers_file = os.path.join(pkg, 'config', 'markers.yaml')

    domain_home_map = {'6': 'home_robot1', '7': 'home_robot2'}
    home_key = domain_home_map.get(os.environ.get('ROS_DOMAIN_ID', '6'), 'home_robot1')

    return LaunchDescription([
        Node(
            package='wego_aruco',
            executable='aruco_home_dock',
            name='aruco_home_dock',
            output='screen',
            parameters=[{
                'markers_file': markers_file,
                'home_key':     home_key,
                'target_dist':  0.513,
                'rho_tol':      0.03,
                'yaw_tol':      0.10,
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
