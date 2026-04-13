import os
from launch import LaunchDescription
from launch_ros.actions import Node, PushRosNamespace
from ament_index_python.packages import get_package_share_directory

from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, GroupAction
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration, PythonExpression
from launch_ros.substitutions import FindPackageShare

from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml

def generate_launch_description():
    wego_share_dir = get_package_share_directory('wego')
    wego_nav_share_dir = get_package_share_directory('wego_2d_nav')

    # setting for rviz configuration path
    rviz_file_name = 'navigation.rviz'
    rviz_config_path = os.path.join(wego_share_dir, 'rviz', rviz_file_name)

    # set the parameters
    parameter_file_name = 'diff_navigation_params.yaml'
    parameter_file_path = os.path.join(wego_nav_share_dir, 'params', parameter_file_name)

    # set the map yaml file
    map_file_name = 'map.yaml'
    map_file_path = os.path.join(wego_nav_share_dir, 'maps', map_file_name)

    # remapping tf topic
    # /tf, /tf_static를 상대경로(tf, tf_static)로 remapping.
    # PushRosNamespace 적용 시 각 로봇의 TF가 /limo_001/tf, /limo_002/tf로 격리되어
    # 두 로봇의 TF 트리가 충돌하지 않음.
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]

    # [멀티로봇] namespace 인자 추가.
    # 로봇마다 다르게 지정하여 토픽/노드를 격리.
    # 예: ros2 launch wego navigation_diff_launch.py namespace:=limo_001
    #     ros2 launch wego navigation_diff_launch.py namespace:=limo_002
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='limo_001',
        description='Robot namespace. 로봇마다 고유하게 지정 (limo_001 or limo_002)'
    )

    # set container for composable node
    # nav2_container: localization, navigation composable 노드들이 올라타는 컨테이너.
    # PushRosNamespace 안에 있으므로 /limo_001/nav2_container 형태로 생성됨.
    nav2_container = Node(
        name='nav2_container',
        package='rclcpp_components',
        executable='component_container_isolated',
        parameters=[ParameterFile(parameter_file_path), {'autostart': True}],
        arguments=['--ros-args', '--log-level', 'info'],
        remappings=remappings,
        output='screen',
    )

    # For localization
    # [멀티로봇] container_name을 fully qualified name으로 전달.
    # localization_launch.py의 LoadComposableNodes가 올바른 컨테이너를 찾으려면
    # /limo_001/nav2_container 형태의 절대경로가 필요함.
    localization_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('wego_2d_nav'),
            'launch',
            'localization_launch.py',
        ]),
        launch_arguments={
            'map': map_file_path,
            'params_file': parameter_file_path,
            'container_name': PythonExpression([
                '"/" + "', LaunchConfiguration('namespace'), '" + "/nav2_container"'
            ]),
        }.items()
    )

    # For navigation
    # [멀티로봇] localization_launch와 동일하게 container_name 전달.
    navigation_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('wego_2d_nav'),
            'launch',
            'navigation_only_launch.py',
        ]),
        launch_arguments={
            'params_file': parameter_file_path,
            'container_name': PythonExpression([
                '"/" + "', LaunchConfiguration('namespace'), '" + "/nav2_container"'
            ]),
        }.items()
    )

    # setting for rviz
    rviz_config_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config_path],
    )

    # [멀티로봇] GroupAction + PushRosNamespace로 모든 노드를 감쌈.
    # 이 블록 안의 모든 노드/토픽에 namespace가 자동으로 prefix로 붙음.
    # 예: nav2_container      → /limo_001/nav2_container
    #     odometry/filtered   → /limo_001/odometry/filtered
    #     /cmd_vel            → /limo_001/cmd_vel
    bringup_group = GroupAction([
        PushRosNamespace(LaunchConfiguration('namespace')),
        nav2_container,
        localization_launch,
        navigation_launch,
        rviz_config_node,
    ])

    return LaunchDescription([
        namespace_arg,
        bringup_group,
    ])
