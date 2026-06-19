import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, LifecycleNode


MAP_YAML = os.path.join(
    get_package_share_directory('ulsan_2d_nav'),
    'maps', 'map.yaml',
)


def generate_launch_description():
    map_server = LifecycleNode(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        namespace='',
        output='screen',
        parameters=[{'yaml_filename': MAP_YAML}],
    )

    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_map',
        output='screen',
        parameters=[{
            'autostart': True,
            'node_names': ['map_server'],
        }],
    )

    gui = Node(
        package='ulsan_gui',
        executable='ulsan_gui',
        name='ulsan_gui',
        output='screen',
    )

    return LaunchDescription([map_server, lifecycle_manager, gui])
