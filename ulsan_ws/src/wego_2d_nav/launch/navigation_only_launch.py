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

    # [멀티로봇] container_name 인자 추가.
    # localization_launch.py와 동일한 이유:
    # navigation_diff_launch.py에서 /limo_001/nav2_container 형태로 전달받아
    # namespace 안에 있는 컨테이너를 올바르게 찾기 위함.
    declare_container_name_cmd = DeclareLaunchArgument(
        'container_name',
        default_value='nav2_container',
        description='Composable node container name (fully qualified, e.g. /limo_001/nav2_container)')

    # for remapping tf topic
    # /tf, /tf_static를 상대경로로 remapping하여 각 로봇의 TF 트리를 격리.
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    
    # set the lifecycle nodes
    lifecycle_nodes = [
        'controller_server',
        'smoother_server',
        'planner_server',
        'behavior_server',
        'bt_navigator',
        'waypoint_follower',
        'velocity_smoother'
    ]

    load_composable_nodes = GroupAction(
        actions=[
            LoadComposableNodes(
                # [멀티로봇] 하드코딩된 'nav2_container' → LaunchConfiguration으로 변경.
                # localization_launch.py와 동일한 이유.
                target_container=LaunchConfiguration('container_name'),
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
        declare_container_name_cmd,
        load_composable_nodes,
    ])