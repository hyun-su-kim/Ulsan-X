import os
from launch import LaunchDescription
from launch.actions import GroupAction, DeclareLaunchArgument
from launch_ros.actions import Node, LoadComposableNodes
from ament_index_python.packages import get_package_share_directory
from launch_ros.descriptions import ComposableNode, ParameterFile
from nav2_common.launch import RewrittenYaml
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    wego_share_dir = get_package_share_directory('wego_2d_nav')

    # setting for map and parameter
    map_yaml_file = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')

    declare_map_yaml_cmd = DeclareLaunchArgument(
        'map',
        default_value=os.path.join(wego_share_dir, 'maps', 'map.yaml'),
        description='Full path to map yaml file to load')

    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(wego_share_dir, 'params', 'diff_navigation_params.yaml'),
        description='Full path to parameter yaml file to load')

    # [멀티로봇] container_name 인자 추가.
    # navigation_diff_launch.py에서 /limo_001/nav2_container 형태로 전달받음.
    # LoadComposableNodes의 target_container는 fully qualified name이어야
    # namespace 안에 있는 컨테이너를 올바르게 찾을 수 있음.
    declare_container_name_cmd = DeclareLaunchArgument(
        'container_name',
        default_value='nav2_container',
        description='Composable node container name (fully qualified, e.g. /limo_001/nav2_container)')

    # remapping the topic and set lifecycle node
    # /tf, /tf_static를 상대경로로 remapping하여 각 로봇의 TF 트리를 격리.
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    lifecycle_nodes = ['map_server', 'amcl']

    load_composable_nodes = GroupAction(
        actions=[
            LoadComposableNodes(
                # [멀티로봇] 하드코딩된 'nav2_container' → LaunchConfiguration으로 변경.
                # /limo_001/nav2_container 처럼 fully qualified name을 받아야
                # namespace 안에 있는 컨테이너를 올바르게 찾을 수 있음.
                target_container=LaunchConfiguration('container_name'),
                composable_node_descriptions=[
                    ComposableNode( # loading the map to map server
                        package='nav2_map_server',
                        plugin='nav2_map_server::MapServer',
                        name='map_server',
                        parameters=[{'yaml_filename': map_yaml_file}],
                        remappings=remappings,
                    ),
                    ComposableNode( # amcl localization
                        package='nav2_amcl',
                        plugin='nav2_amcl::AmclNode',
                        name='amcl',
                        parameters=[ParameterFile(params_file)],
                    ),
                    ComposableNode( # For lifecycle
                        package='nav2_lifecycle_manager',
                        plugin='nav2_lifecycle_manager::LifecycleManager',
                        name='lifecycle_manager_localization',
                        parameters=[
                            {'autostart': True,
                            'node_names': lifecycle_nodes}
                        ],
                    ),
                ],
            ),
        ],
    )

    return LaunchDescription([
        declare_map_yaml_cmd,
        declare_params_file_cmd,
        declare_container_name_cmd,
        load_composable_nodes,
    ])
