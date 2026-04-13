import launch

from launch import LaunchDescription

from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, GroupAction, SetRemap
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration, TextSubstitution, PythonExpression

from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition

from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    wego_share_dir = get_package_share_directory('wego')
    rviz_config_path = os.path.join(wego_share_dir, 'rviz', 'display.rviz')

    degree = LaunchConfiguration('degree')
    degree_launch_arg = DeclareLaunchArgument(
        'degree',
        default_value='0.0'
    )

    viz_launch_arg = DeclareLaunchArgument(
        'viz',
        default_value='false'
    )

    # [멀티로봇] namespace 인자 추가.
    # 로봇마다 다르게 지정하여 모든 하드웨어 노드/토픽을 격리.
    # 예: ros2 launch wego teleop_launch.py namespace:=limo_001
    #     ros2 launch wego teleop_launch.py namespace:=limo_002
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='limo_001',
        description='Robot namespace. 로봇마다 고유하게 지정 (limo_001 or limo_002)'
    )

    # [멀티로봇] GroupAction + PushRosNamespace로 모든 하드웨어 노드를 감쌈.
    # limo_base, ydlidar, EKF 등이 발행하는 토픽에 namespace가 자동으로 붙음.
    # 예: odom              → /limo_001/odom
    #     odometry/filtered → /limo_001/odometry/filtered
    #     scan              → /limo_001/scan
    #
    # TF remapping (/tf → tf):
    # static_transform_publisher(camera_tilt), robot_state_publisher(load_urdf) 등이
    # 발행하는 TF가 /limo_001/tf로 격리되어 두 로봇의 TF 트리가 충돌하지 않음.
    bringup_group = GroupAction([
        PushRosNamespace(LaunchConfiguration('namespace')),

        # [멀티로봇] TF remapping 추가.
        # /tf, /tf_static는 절대경로라 PushRosNamespace만으로는 namespace가 적용 안 됨.
        # SetRemap으로 상대경로(tf)로 변환하면 PushRosNamespace가 적용되어
        # /limo_001/tf, /limo_002/tf로 격리됨.
        # GroupAction 안의 모든 노드(포함된 launch 파일 포함)에 적용됨.
        SetRemap('/tf', 'tf'),
        SetRemap('/tf_static', 'tf_static'),

        # URDF 로드 및 robot_state_publisher 실행
        # base_link, odom 등 TF 프레임을 /limo_001/tf에 발행
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('limo_description'), 'launch', 'load_urdf.launch.py'])
        ),

        # 카메라 틸트 초기 위치 설정 (static TF 발행)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('wego'),
                    'launch',
                    'camera_tilt_launch.py'
                ])
            ]),
            launch_arguments={
                'degree': degree
            }.items()
        ),

        # LIMO PRO 모터 드라이버
        # namespace='limo' 제거됨 → PushRosNamespace가 올바르게 적용됨
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('limo_base'), 'launch', 'limo_base.launch.py'])
        ),

        # Orbbec 깊이 카메라
        # [멀티로봇] camera_name을 namespace 기반으로 전달.
        # orbbec launch 내부에서 ComposableNode/Container에 namespace=""가 명시되어
        # 상위 PushRosNamespace가 무시됨. camera_name에 로봇 이름을 포함시켜
        # /limo_001_camera/... 형태로 격리.
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('orbbec_camera'), 'launch', 'astra_stereo_u3.launch.py']),
            launch_arguments={
                'camera_name': PythonExpression([
                    '"', LaunchConfiguration('namespace'), '" + "_camera"'
                ])
            }.items()
        ),

        # YDLidar 드라이버
        # namespace='/' 제거됨 → PushRosNamespace가 올바르게 적용됨
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('ydlidar_ros2_driver'), 'launch', 'ydlidar.launch.py'])
        ),

        # EKF (odom + imu 융합 → odometry/filtered 발행)
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('robot_localization'), 'launch', 'limo_ekf_launch.py'])
        ),

        # RViz (기본 비활성화)
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            condition=IfCondition(LaunchConfiguration('viz')),
            arguments=['-d', rviz_config_path]
        ),
    ])

    return LaunchDescription([
        degree_launch_arg,
        viz_launch_arg,
        namespace_arg,
        bringup_group,
    ])
