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

    # setting for parameter
    params_file = LaunchConfiguration('params_file')
 
    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(wego_share_dir, 'params', 'diff_navigation_params.yaml'),
        description='Full path to parameter yaml file to load')

    # for remapping tf topic 
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    
    maps_dir = os.path.join(wego_share_dir, 'maps')

    # set the lifecycle nodes
    lifecycle_nodes = [
        'controller_server',
        'smoother_server',
        'planner_server',
        'behavior_server',
        'bt_navigator',
        'waypoint_follower',
        'velocity_smoother',
        'filter_mask_server',        # keepout filter mask 제공
        'costmap_filter_info_server' # KeepoutFilter에 메타데이터 제공
    ]

    load_composable_nodes = GroupAction(
        actions=[
            LoadComposableNodes(
                target_container='nav2_container',
                composable_node_descriptions=[
                    ComposableNode( # loading controller server
                        package='nav2_controller',
                        plugin='nav2_controller::ControllerServer',
                        name='controller_server',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings + [('cmd_vel', 'cmd_vel_nav')]
                    ),
                    ComposableNode( # smoother server
                        package='nav2_smoother',
                        plugin='nav2_smoother::SmootherServer',
                        name='smoother_server',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings
                    ),
                    ComposableNode(
                        package='nav2_planner',
                        plugin='nav2_planner::PlannerServer',
                        name='planner_server',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings
                    ),
                    ComposableNode(
                        package='nav2_behaviors',
                        plugin='behavior_server::BehaviorServer',
                        name='behavior_server',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings
                    ),
                    ComposableNode(
                        package='nav2_bt_navigator',
                        plugin='nav2_bt_navigator::BtNavigator',
                        name='bt_navigator',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings
                    ),
                    ComposableNode(
                        package='nav2_waypoint_follower',
                        plugin='nav2_waypoint_follower::WaypointFollower',
                        name='waypoint_follower',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings
                    ),
                    ComposableNode(
                        package='nav2_velocity_smoother',
                        plugin='nav2_velocity_smoother::VelocitySmoother',
                        name='velocity_smoother',
                        parameters=[ParameterFile(params_file)],
                        remappings=remappings +
                            [('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', 'cmd_vel')]
                    ),
                    # filter_map.pgm을 OccupancyGrid로 /keepout_filter_mask 토픽에 publish
                    ComposableNode(
                        package='nav2_map_server',
                        plugin='nav2_map_server::MapServer',
                        name='filter_mask_server',
                        parameters=[{
                            'yaml_filename': os.path.join(maps_dir, 'filter_map.yaml'),
                            'topic_name': '/keepout_filter_mask',
                            'frame_id': 'map',
                        }],
                        remappings=remappings
                    ),
                    # 마스크 해석 메타데이터(type, base, multiplier)를 /costmap_filter_info로 publish
                    # type=0: KeepoutFilter, KeepoutFilter 플러그인이 이를 구독해 마스크 셀을 LETHAL_OBSTACLE로 변환
                    ComposableNode(
                        package='nav2_map_server',
                        plugin='nav2_map_server::CostmapFilterInfoServer',
                        name='costmap_filter_info_server',
                        parameters=[{
                            'type': 0,
                            'filter_info_topic': '/costmap_filter_info',
                            'mask_topic': '/keepout_filter_mask',
                            'base': 0.0,
                            'multiplier': 1.0,
                        }],
                        remappings=remappings
                    ),
                    ComposableNode( # set the lifecycle manager
                        package='nav2_lifecycle_manager',
                        plugin='nav2_lifecycle_manager::LifecycleManager',
                        name='lifecycle_manager_navigation',
                        parameters=[{
                            'autostart': True,
                            'node_names': lifecycle_nodes}
                        ],
                    ),
                ],
            ),
        ],
    )
    
    return LaunchDescription([
        declare_params_file_cmd,
        load_composable_nodes,
    ])