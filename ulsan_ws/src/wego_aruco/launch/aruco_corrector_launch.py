import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import EnvironmentVariable
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg = get_package_share_directory('wego_aruco')
    markers_file = os.path.join(pkg, 'config', 'markers.yaml')

    domain_home_map = {'6': 'home_robot1', '7': 'home_robot2'}
    import os as _os
    home_key = domain_home_map.get(_os.environ.get('ROS_DOMAIN_ID', '6'), 'home_robot1')

    return LaunchDescription([
        Node(
            package='wego_aruco',
            executable='aruco_pose_corrector',
            name='aruco_pose_corrector',
            output='screen',
            parameters=[{'markers_file': markers_file}],
        ),
        Node(
            package='wego_aruco',
            executable='aruco_home_dock',
            name='aruco_home_dock',
            output='screen',
            parameters=[{
                'markers_file': markers_file,
                'home_key':     home_key,
                'target_dist':  0.5,
            }],
        ),
    ])
