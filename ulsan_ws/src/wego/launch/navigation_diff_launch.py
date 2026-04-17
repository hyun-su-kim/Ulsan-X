import os
import tempfile
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch_ros.substitutions import FindPackageShare

from launch_ros.descriptions import ParameterFile


def launch_setup(context, *args, **kwargs):
    robot_name = LaunchConfiguration('robot_name').perform(context)

    wego_share_dir = get_package_share_directory('wego')
    wego_nav_share_dir = get_package_share_directory('wego_2d_nav')

    rviz_config_path = os.path.join(wego_share_dir, 'rviz', 'navigation.rviz')
    map_file_path = os.path.join(wego_nav_share_dir, 'maps', 'map.yaml')
    template_path = os.path.join(wego_nav_share_dir, 'params', 'diff_navigation_params.yaml')

    # [멀티로봇] ROBOT_NAME 플레이스홀더를 robot_name 인자 값으로 치환.
    # Python str.replace()는 값(value) 안의 문자열만 바꾸므로,
    # 키(key)가 같아도 값에 ROBOT_NAME이 없으면 영향을 주지 않음.
    # 예) global_costmap.global_frame: map    → 그대로 (map에 ROBOT_NAME 없음)
    #     local_costmap.global_frame: ROBOT_NAME/odom → robot1/odom 으로 치환
    with open(template_path, 'r') as f:
        content = f.read()

    content = content.replace('ROBOT_NAME', robot_name)

    # [멀티로봇] OTHER_ROBOT_NAME: fleet_obstacle_layer가 구독할 상대 로봇 pose 토픽.
    # robot1이면 robot2/amcl_pose, robot2이면 robot1/amcl_pose를 구독.
    # 로봇이 3대 이상이 되면 launch 인자로 직접 지정하도록 확장 가능.
    other_robot_map = {'robot1': 'robot2', 'robot2': 'robot1'}
    other_robot_name = other_robot_map.get(robot_name, 'unknown')
    content = content.replace('OTHER_ROBOT_NAME', other_robot_name)

    # [멀티로봇] 치환된 내용을 임시 파일에 저장.
    # Nav2는 파라미터를 파일 경로로 받기 때문에 임시 파일이 필요함.
    tmp_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', delete=False,
        prefix=f'nav2_params_{robot_name}_'
    )
    tmp_file.write(content)
    tmp_file.close()
    parameter_file_path = tmp_file.name

    # remapping tf topic
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]

    # set container for composable node
    nav2_container = Node(
        name='nav2_container',
        package='rclcpp_components',
        executable='component_container_isolated',
        parameters=[ParameterFile(parameter_file_path), {'autostart': True}],
        arguments=['--ros-args', '--log-level', 'info'],
        remappings=remappings,
        output='screen',
    )

    # For localization (map_server + amcl)
    localization_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('wego_2d_nav'),
            'launch',
            'localization_launch.py',
        ]),
        launch_arguments={
            'map': map_file_path,
            'params_file': parameter_file_path
        }.items()
    )

    # For navigation (Nav2 전체 스택)
    navigation_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('wego_2d_nav'),
            'launch',
            'navigation_only_launch.py',
        ]),
        launch_arguments={
            'params_file': parameter_file_path
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

    return [
        nav2_container,
        localization_launch,
        navigation_launch,
        rviz_config_node,
    ]


def generate_launch_description():
    # [멀티로봇] robot_name 인자: yaml의 ROBOT_NAME 플레이스홀더를 치환하는 데 사용.
    #
    # 사용 예:
    #   LIMO 1:  ros2 launch wego navigation_diff_launch.py robot_name:=robot1
    #   LIMO 2:  ros2 launch wego navigation_diff_launch.py robot_name:=robot2
    #   LIMO 3:  ros2 launch wego navigation_diff_launch.py robot_name:=robot3  (확장 시)
    #
    # 결과 TF tree (노트북 domain 5에서 확인):
    #   map → robot1/odom → robot1/base_link  (domain 6에서 브릿지)
    #   map → robot2/odom → robot2/base_link  (domain 7에서 브릿지)
    declare_robot_name = DeclareLaunchArgument(
        'robot_name',
        default_value='robot1',
        description='Robot name used for TF frame IDs (e.g. robot1, robot2, robot3)'
    )

    return LaunchDescription([
        declare_robot_name,
        OpaqueFunction(function=launch_setup),
    ])
