import os
import yaml
from launch import LaunchDescription
from launch.actions import GroupAction, DeclareLaunchArgument
from launch_ros.actions import Node, LoadComposableNodes
from ament_index_python.packages import get_package_share_directory
from launch_ros.descriptions import ComposableNode, ParameterFile
from nav2_common.launch import RewrittenYaml
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    wego_share_dir = get_package_share_directory('wego_2d_nav')

    # robot_config.yaml에서 도메인 → home_key 매핑 읽기
    # domain_home_map 사용 — domain_robot_map은 브릿지/dispatcher 토픽 prefix용(limo1/limo2)
    behaviour_share_dir = get_package_share_directory('wego_behaviour')
    with open(os.path.join(behaviour_share_dir, 'config', 'robot_config.yaml')) as f:
        domain_home_map = yaml.safe_load(f)['domain_home_map']

    # waypoints.yaml에서 홈 좌표 참조 — 좌표 정본은 wego_behaviour/config/waypoints.yaml 한 곳
    with open(os.path.join(behaviour_share_dir, 'config', 'waypoints.yaml')) as f:
        waypoints = yaml.safe_load(f)['waypoints']

    # ROS_DOMAIN_ID로 home_key 결정 → AMCL 초기 파티클 위치 설정
    # AMCL이 처음부터 올바른 홈 위치에서 시작해야 (0,0,0) 기준 라이다 스캔이 costmap에 오염되지 않음
    domain_id = os.environ.get('ROS_DOMAIN_ID', '6')
    home_key = domain_home_map.get(domain_id, 'home_robot1')
    home = waypoints[home_key]
    initial_pose_params = {
        'set_initial_pose': True,
        'initial_pose.x':   float(home['x']),
        'initial_pose.y':   float(home['y']),
        'initial_pose.yaw': float(home['yaw']),
    }

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

    
    # remapping the topic and set lifecycle node
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    lifecycle_nodes = ['map_server', 'amcl']

    load_composable_nodes = GroupAction(
        actions=[
            LoadComposableNodes(
                target_container='nav2_container',
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
                        # ParameterFile 뒤에 dict를 추가하면 ROS2가 병합하여 초기 위치를 덮어씀
                        parameters=[ParameterFile(params_file), initial_pose_params],
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
        load_composable_nodes,
    ])