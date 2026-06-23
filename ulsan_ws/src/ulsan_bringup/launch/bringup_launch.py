import launch

from launch import LaunchDescription

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration, TextSubstitution, PythonExpression

from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition

from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    ulsan_bringup_share_dir = get_package_share_directory('ulsan_bringup')
    rviz_config_path = os.path.join(ulsan_bringup_share_dir, 'rviz', 'display.rviz')

    degree = LaunchConfiguration('degree')
    degree_launch_arg = DeclareLaunchArgument(
        'degree',
        default_value='0.0'
    )

    viz_launch_arg = DeclareLaunchArgument(
        'viz',
        default_value='false'
    )

    return launch.LaunchDescription([
        degree_launch_arg,
        viz_launch_arg,

        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('limo_description'), 'launch', 'load_urdf.launch.py'])
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('ulsan_bringup'),
                    'launch',
                    'camera_tilt_launch.py'
                    ])
            ]),
            launch_arguments={
                'degree': degree
            }.items()
        ),
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('limo_base'), 'launch', 'limo_base.launch.py'])
        ),
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('orbbec_camera'), 'launch', 'dabai_dcw.launch.py']),
            launch_arguments={
                'depth_width':  '640',
                'depth_height': '400',
                'depth_fps':    '30',
                'color_width':  '640',
                'color_height': '480',
                'color_fps':    '30',
            }.items()
        ),
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('ydlidar_ros2_driver'), 'launch', 'ydlidar.launch.py'])
        ),
        # EKF (robot_localization): apt 패키지 ekf_node 를 ulsan_bringup 소유 설정으로 실행.
        # wego_ws 의 limo_ekf_launch.py include 를 대체 (설정 소유권을 ulsan_ws 로 이전).
        # name='ekf_filter_node_odom' 은 limo_ekf.yaml 최상위 키와 일치해야 파라미터가 적용됨.
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node_odom',
            output='screen',
            parameters=[os.path.join(ulsan_bringup_share_dir, 'config', 'limo_ekf.yaml')],
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            condition=IfCondition(LaunchConfiguration('viz')),
            arguments=['-d', rviz_config_path]
        )
  ])
