import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    wego_2d_nav_dir = get_package_share_directory('wego_2d_nav')
    wego_ui_dir = get_package_share_directory('wego_ui')

    map_yaml_file = LaunchConfiguration('map')
    declare_map_cmd = DeclareLaunchArgument(
        'map',
        default_value=os.path.join(wego_2d_nav_dir, 'maps', 'map.yaml'),
        description='Full path to map yaml file to load')

    map_server_node = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[{'yaml_filename': map_yaml_file, 'use_sim_time': False}],
    )

    lifecycle_manager_node = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_map',
        output='screen',
        parameters=[{
            'autostart': True,
            'node_names': ['map_server'],
        }],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(wego_ui_dir, 'rviz', 'dual_robot_monitor.rviz')],
        output='screen',
    )

    return LaunchDescription([
        declare_map_cmd,
        map_server_node,
        lifecycle_manager_node,
        rviz_node,
    ])
