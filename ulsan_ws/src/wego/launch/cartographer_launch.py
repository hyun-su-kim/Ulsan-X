import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import ThisLaunchFileDir
from launch.conditions import IfCondition


def generate_launch_description():
    wego_share_dir = get_package_share_directory('wego')
    cartographer_config_dir = LaunchConfiguration('cartographer_config_dir',
                                    default=os.path.join(wego_share_dir, 'config'))
    configuration_file = LaunchConfiguration('configuration_file', default='limo_lds_2d.lua')

    resolution = LaunchConfiguration('resolution', default='0.05')
    publish_period_sec = LaunchConfiguration('publish_period_sec', default='1.0')

    # RViz 실행 여부 인자 (기본값: true)
    # SSH 환경이나 헤드리스 실행 시: use_rviz:=false
    use_rviz = LaunchConfiguration('use_rviz', default='true')

    rviz_config_dir = os.path.join(get_package_share_directory('wego'), 'rviz', 'cartographer.rviz')

    return LaunchDescription([
        DeclareLaunchArgument(
            'cartographer_config_dir',
            default_value=cartographer_config_dir,
            description='Full path to config file to load'),
        DeclareLaunchArgument(
            'configuration_file',
            default_value=configuration_file,
            description='Name of lua file for cartographer'),
        Node(
            package='cartographer_ros',
            executable='cartographer_node',
            name='cartographer_node',
            remappings=[('odom','odometry/filtered'),],
            output='screen',
            arguments=['-configuration_directory', cartographer_config_dir,
                       '-configuration_basename', configuration_file]),

        DeclareLaunchArgument(
            'resolution',
            default_value=resolution,
            description='Resolution of a grid cell in the published occupancy grid'),

        DeclareLaunchArgument(
            'publish_period_sec',
            default_value=publish_period_sec,
            description='OccupancyGrid publishing period'),

        # RViz 실행 여부 인자 선언
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='RViz 실행 여부. SSH/헤드리스 환경에서는 false로 설정'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([ThisLaunchFileDir(), '/occupancy_grid_launch.py']),
            launch_arguments={'resolution': resolution,
                              'publish_period_sec': publish_period_sec}.items(),
        ),

        # use_rviz:=false 이면 이 노드는 실행되지 않음
        Node(
            condition=IfCondition(use_rviz),
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config_dir],
            output='screen'),
    ])