# wego_bridge 런치 파일
#
# 실행 위치: 서버 노트북 — LIMO 도메인 터미널 (ROS_DOMAIN_ID=6 or 7)
#
# ROS_DOMAIN_ID를 읽어 robot_config.yaml에서 robot_name을 결정하고,
# bridge_robot.yaml 템플릿의 ROBOT_DOMAIN / ROBOT_NAME을 치환하여
# domain_bridge 노드에 전달한다.
#
# 브릿지를 LIMO 도메인에서 실행하는 이유:
#   - 생명주기 일치: LIMO 시스템이 죽으면 브릿지도 함께 종료
#     → domain 5에 stale 데이터가 남지 않아 연결 끊김 감지 가능
#   - LIMO 추가 시 robot_config.yaml과 waypoints.yaml만 수정하면 됨
#
# 실행 예시:
#   export ROS_DOMAIN_ID=6 && ros2 launch wego_bridge bridge_launch.py  # LIMO 1
#   export ROS_DOMAIN_ID=7 && ros2 launch wego_bridge bridge_launch.py  # LIMO 2

import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import OpaqueFunction
from launch_ros.actions import Node


def launch_setup(context):
    config_dir = os.path.join(get_package_share_directory('wego_bridge'), 'config')
    behaviour_config_dir = os.path.join(
        get_package_share_directory('wego_behaviour'), 'config'
    )

    # robot_config.yaml에서 도메인 → robot_name 매핑 읽기 (로봇 추가 시 yaml만 수정)
    with open(os.path.join(behaviour_config_dir, 'robot_config.yaml')) as f:
        domain_robot_map = yaml.safe_load(f)['domain_robot_map']

    # ROS_DOMAIN_ID로 robot_name 결정
    domain_id = os.environ.get('ROS_DOMAIN_ID', '6')
    robot_name = domain_robot_map.get(domain_id, 'limo1')

    # bridge_robot.yaml 템플릿 읽기
    template_path = os.path.join(config_dir, 'bridge_robot.yaml')
    with open(template_path) as f:
        template = f.read()

    # ROBOT_DOMAIN, ROBOT_NAME 치환 (DEC-007 OpaqueFunction + tempfile 패턴)
    filled = template.replace('ROBOT_DOMAIN', domain_id).replace('ROBOT_NAME', robot_name)

    # 치환된 내용을 tempfile에 저장 → domain_bridge에 경로로 전달
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    tmp.write(filled)
    tmp.flush()

    return [
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name=f'bridge_{robot_name}',
            arguments=[tmp.name],
            output='screen',
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup),
    ])
