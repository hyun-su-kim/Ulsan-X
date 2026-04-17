import launch

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def launch_setup(context, *args, **kwargs):
    degree      = LaunchConfiguration('degree').perform(context)
    robot_name  = LaunchConfiguration('robot_name').perform(context)

    # [멀티로봇] 모든 카메라 TF 프레임에 robot_name/ 접두사 적용.
    # teleop_launch.py의 robot_state_publisher(frame_prefix)와 EKF가
    # robot_name/base_link 를 발행하므로, 카메라 체인도 동일 접두사를 써야 TF가 연결됨.
    base_frame          = robot_name + '/base_link'
    camera_mount_frame  = robot_name + '/camera_mount'
    camera_rotate_frame = robot_name + '/camera_rotate'
    camera_link_frame   = robot_name + '_camera_link'

    return [
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_link_to_camera_mount',
            arguments=['--x', '0.2',
                       '--y', '0.1',
                       '--z', '0.06',
                       '--yaw', '0',
                       '--pitch', '0',
                       '--roll', '0',
                       '--frame-id', base_frame,
                       '--child-frame-id', camera_mount_frame]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='camera_mount_to_rotate',
            arguments=['--x', '0.00',
                       '--y', '0.00',
                       '--z', '0.00',
                       '--yaw', '0',
                       '--pitch', degree,
                       '--roll', '0',
                       '--frame-id', camera_mount_frame,
                       '--child-frame-id', camera_rotate_frame]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='rotate_to_camera_link',
            arguments=['--x', '0.03',
                       '--y', '-0.05',
                       '--z', '0.00',
                       '--yaw', '0',
                       '--pitch', '0',
                       '--roll', '0',
                       '--frame-id', camera_rotate_frame,
                       '--child-frame-id', camera_link_frame]
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('degree', default_value='0.0'),

        # [멀티로봇] robot_name: 카메라 TF 프레임 접두사.
        # teleop_launch.py에서 robot_name 인자를 그대로 전달받음.
        # 예) robot_name:=robot1  →  robot1/base_link, robot1/camera_mount ...
        DeclareLaunchArgument(
            'robot_name',
            default_value='robot1',
            description='Robot name prefix for TF frame IDs (robot1, robot2)',
        ),

        OpaqueFunction(function=launch_setup),
    ])
