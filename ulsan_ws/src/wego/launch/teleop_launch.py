import os
import tempfile

import launch
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.actions import (
    IncludeLaunchDescription,
    DeclareLaunchArgument,
    OpaqueFunction,
)
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command
from ament_index_python.packages import get_package_share_directory


def launch_setup(context, *args, **kwargs):
    # ── 런치 인자 값 확정 ────────────────────────────────────────────────────
    # OpaqueFunction 내부에서 perform(context)로 실제 문자열 값을 꺼냄.
    # LaunchConfiguration은 지연 평가 객체라 함수 밖에서는 str 연산 불가.
    robot_name = LaunchConfiguration('robot_name').perform(context)
    degree     = LaunchConfiguration('degree').perform(context)

    wego_share_dir = get_package_share_directory('wego')
    rviz_config_path = os.path.join(wego_share_dir, 'rviz', 'display.rviz')

    # ── URDF 경로 ─────────────────────────────────────────────────────────────
    limo_description_dir = get_package_share_directory('limo_description')
    model_path = os.path.join(limo_description_dir, 'urdf', 'limo_four_diff.xacro')

    # xacro로 URDF 문자열 생성 (robot_state_publisher에 robot_description 파라미터로 전달)
    robot_description = ParameterValue(
        Command(['xacro ', model_path]),
        value_type=str,
    )

    # ── EKF 파라미터 치환 ──────────────────────────────────────────────────────
    # [멀티로봇] nav2 params(diff_navigation_params.yaml)와 동일한 ROBOT_NAME 치환 방식.
    # limo_ekf_robot.yaml의 ROBOT_NAME 플레이스홀더를 robot_name 값으로 교체 후
    # 임시 파일에 저장 → ekf_node의 parameters 경로로 전달.
    ekf_template_path = os.path.join(wego_share_dir, 'config', 'limo_ekf_robot.yaml')
    with open(ekf_template_path, 'r') as f:
        ekf_content = f.read()

    ekf_content = ekf_content.replace('ROBOT_NAME', robot_name)
    # 예) odom_frame: ROBOT_NAME/odom  →  odom_frame: robot1/odom

    tmp_ekf = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', delete=False,
        prefix=f'ekf_params_{robot_name}_',
    )
    tmp_ekf.write(ekf_content)
    tmp_ekf.close()

    # ── joint_state_publisher ──────────────────────────────────────────────────
    # URDF에 정의된 조인트 상태를 /joint_states 토픽으로 발행.
    # robot_state_publisher가 이 값을 받아 TF를 계산함.
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
    )

    # ── robot_state_publisher ─────────────────────────────────────────────────
    # URDF 기반 TF를 /tf, /tf_static으로 발행.
    #
    # [멀티로봇] frame_prefix: robot_name + "/"
    #   URDF 내 모든 프레임 이름 앞에 접두사를 붙임.
    #   예) base_link → robot1/base_link
    #       base_scan → robot1/base_scan
    #       imu_link  → robot1/imu_link
    #
    #   map 프레임은 URDF에 포함되지 않으므로 영향 없음.
    #   EKF가 발행하는 robot1/odom → robot1/base_link TF와 연결되어
    #   최종 체인: map → robot1/odom → robot1/base_link → robot1/base_scan
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'frame_prefix': robot_name + '/',  # [멀티로봇] URDF 프레임에 robot_name/ 접두사 적용
        }],
    )

    # ── EKF 노드 ──────────────────────────────────────────────────────────────
    # [멀티로봇] 원본 limo_ekf_launch.py(wego_ws, 수정 불가)의 고정 파라미터 경로를
    # 직접 노드로 실행하는 방식으로 대체.
    # limo_ekf_robot.yaml의 ROBOT_NAME 치환 결과(임시 파일)를 파라미터로 전달.
    #
    # 치환 결과:
    #   odom_frame:      robot1/odom       → EKF가 발행하는 odom TF 프레임
    #   base_link_frame: robot1/base_link  → robot_state_publisher의 frame_prefix와 일치
    #   world_frame:     robot1/odom       → odom 레벨 필터 (map 레벨은 AMCL이 담당)
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node_odom',
        output='screen',
        parameters=[tmp_ekf.name],
    )

    # ── 기존 런치 포함 (변경 없음) ──────────────────────────────────────────
    camera_tilt_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('wego'), 'launch', 'camera_tilt_launch.py',
        ]),
        # [멀티로봇] robot_name 전달 → camera_tilt_launch.py에서 프레임 ID에 접두사 적용
        launch_arguments={'degree': degree, 'robot_name': robot_name}.items(),
    )

    limo_base_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('limo_base'), 'launch', 'limo_base.launch.py',
        ]),
    )

    orbbec_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('orbbec_camera'), 'launch', 'astra_stereo_u3.launch.py',
        ]),
        # [멀티로봇] camera_name을 robot_name 기반으로 설정.
        # Orbbec 내부: camera_link_frame_id_ = camera_name_ + "_link"
        # → camera_name = "robot1/camera" 이면 camera_link_frame_id = "robot1/camera_link"
        # camera_tilt_launch.py의 체인 끝(robot1/camera_link)과 자연스럽게 연결됨.
        # 결과 TF: robot1/camera_link → robot1/camera_color_frame → robot1/camera_color_optical_frame
        #                             → robot1/camera_depth_frame → robot1/camera_depth_optical_frame
        launch_arguments={'camera_name': robot_name + '_camera'}.items(),
    )

    ydlidar_launch = IncludeLaunchDescription(
        PathJoinSubstitution([
            FindPackageShare('ydlidar_ros2_driver'), 'launch', 'ydlidar.launch.py',
        ]),
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        condition=IfCondition(LaunchConfiguration('viz')),
        arguments=['-d', rviz_config_path],
    )

    return [
        joint_state_publisher_node,
        robot_state_publisher_node,
        ekf_node,
        camera_tilt_launch,
        limo_base_launch,
        orbbec_launch,
        ydlidar_launch,
        rviz_node,
    ]


def generate_launch_description():
    return LaunchDescription([
        # 기존 인자
        DeclareLaunchArgument('degree', default_value='0.0'),
        DeclareLaunchArgument('viz',    default_value='false'),

        # [멀티로봇] robot_name 인자.
        # robot_state_publisher의 frame_prefix와 EKF의 odom/base_link 프레임 이름에 적용.
        #
        # 사용 예:
        #   LIMO 1: ros2 launch wego teleop_launch.py robot_name:=robot1
        #   LIMO 2: ros2 launch wego teleop_launch.py robot_name:=robot2
        #
        # navigation_diff_launch.py와 동일한 robot_name 값을 사용해야
        # AMCL/Nav2와 EKF/robot_state_publisher의 프레임 이름이 일치함.
        DeclareLaunchArgument(
            'robot_name',
            default_value='robot1',
            description='로봇 이름. TF frame 접두사로 사용됨 (robot1, robot2)',
        ),

        # OpaqueFunction: robot_name 값을 런치 실행 시점에 확정하여
        # frame_prefix 파라미터와 EKF yaml 치환에 사용.
        OpaqueFunction(function=launch_setup),
    ])
