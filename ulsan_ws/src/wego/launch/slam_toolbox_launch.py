import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node


def generate_launch_description():
    wego_2d_nav_dir = get_package_share_directory('wego_2d_nav')
    slam_params_file = os.path.join(
        wego_2d_nav_dir, 'params', 'slam_toolbox_slam_params.yaml'
    )

    use_rviz = LaunchConfiguration('use_rviz', default='true')
    rviz_config = os.path.join(
        get_package_share_directory('wego'), 'rviz', 'cartographer.rviz'
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='RViz 실행 여부. SSH/헤드리스 환경에서는 false로 설정'
        ),

        # SLAM Toolbox — Online Async 매핑 모드
        # async: 스캔 처리를 별도 스레드에서 수행 → 실시간 주행 중 맵 업데이트 가능
        Node(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[slam_params_file],
        ),

        Node(
            condition=IfCondition(use_rviz),
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            output='screen',
        ),
    ])
