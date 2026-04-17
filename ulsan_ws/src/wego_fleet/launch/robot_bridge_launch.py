import os
import tempfile

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


# leader==true 일 때만 MAP_SECTION 자리에 삽입되는 /map 설정.
# 두 로봇이 동일한 맵을 사용하므로 리더 로봇 한 대만 전송.
MAP_YAML = """\

  /map:
    type: nav_msgs/msg/OccupancyGrid
    qos:
      reliability: reliable
      durability: transient_local
      depth: 1
"""


def launch_setup(context, *args, **kwargs):
    is_leader = LaunchConfiguration('leader').perform(context).lower() == 'true'

    # ROS_DOMAIN_ID 환경변수에서 from_domain 자동 결정.
    # 각 LIMO의 bashrc에 설정되어 있음 (LIMO 1: 6, LIMO 2: 7, ...)
    robot_domain = os.environ.get('ROS_DOMAIN_ID', '0')

    pkg_dir = get_package_share_directory('wego_fleet')
    template_path = os.path.join(pkg_dir, 'config', 'domain_bridge_robot.yaml')

    with open(template_path, 'r') as f:
        content = f.read()

    content = content.replace('ROBOT_DOMAIN', robot_domain)

    # /map은 리더 로봇만 전송
    if is_leader:
        content = content.replace('MAP_SECTION', MAP_YAML)
    else:
        content = content.replace('MAP_SECTION', '')

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', delete=False,
        prefix=f'domain_bridge_domain{robot_domain}_',
    )
    tmp.write(content)
    tmp.close()

    bridge_node = Node(
        package='domain_bridge',
        executable='domain_bridge',
        name='robot_bridge',
        output='screen',
        arguments=[tmp.name],
    )

    return [bridge_node]


def generate_launch_description():
    return LaunchDescription([
        # leader: /map 전송 여부 결정.
        # from_domain은 ROS_DOMAIN_ID 환경변수에서 자동으로 읽음.
        #
        # 사용 예:
        #   리더 로봇: ros2 launch wego_fleet robot_bridge_launch.py leader:=true
        #   나머지:    ros2 launch wego_fleet robot_bridge_launch.py
        DeclareLaunchArgument(
            'leader',
            default_value='false',
            description='true면 /map을 domain 5로 전송. 리더 로봇 한 대만 true로 설정.',
        ),
        OpaqueFunction(function=launch_setup),
    ])
