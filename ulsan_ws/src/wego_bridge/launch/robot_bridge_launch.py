import os
import tempfile

from launch import LaunchDescription
from launch.actions import OpaqueFunction
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


# domain ID → robot 식별 정보 매핑 테이블
DOMAIN_MAP = {
    6: {'robot_name': 'limo_1', 'peer_domain': 7},
    7: {'robot_name': 'limo_2', 'peer_domain': 6},
}


def launch_setup(context):
    # ROS_DOMAIN_ID 환경변수에서 현재 로봇 domain 읽기
    try:
        robot_domain = int(os.environ['ROS_DOMAIN_ID'])
    except KeyError:
        raise RuntimeError(
            '[robot_bridge_launch] ROS_DOMAIN_ID 환경변수가 설정되지 않았습니다. '
            '~/.bashrc에 export ROS_DOMAIN_ID=6 (또는 7) 을 추가하세요.'
        )

    if robot_domain not in DOMAIN_MAP:
        raise RuntimeError(
            f'[robot_bridge_launch] ROS_DOMAIN_ID={robot_domain} 은 지원하지 않습니다. '
            f'지원 domain: {list(DOMAIN_MAP.keys())}'
        )

    robot_name  = DOMAIN_MAP[robot_domain]['robot_name']
    peer_domain = DOMAIN_MAP[robot_domain]['peer_domain']

    # 템플릿 YAML 읽기
    config_path = os.path.join(
        get_package_share_directory('wego_bridge'),
        'config',
        'domain_bridge_robot.yaml'
    )
    with open(config_path, 'r') as f:
        content = f.read()

    def make_bridge_node(dest_domain, node_suffix):
        """템플릿 YAML에서 플레이스홀더를 치환해 임시 파일 생성 후 domain_bridge Node 반환."""
        bridged = content \
            .replace('ROBOT_DOMAIN', str(robot_domain)) \
            .replace('DEST_DOMAIN',  str(dest_domain)) \
            .replace('ROBOT_NAME',   robot_name)

        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False,
            prefix=f'domain_bridge_{robot_name}_to{dest_domain}_'
        )
        tmp.write(bridged)
        tmp.flush()
        tmp.close()

        return Node(
            package='domain_bridge',
            executable='domain_bridge',
            name=f'{robot_name}_bridge_{node_suffix}',
            arguments=[tmp.name],
            output='screen',
        )

    return [
        make_bridge_node(dest_domain=5,           node_suffix='laptop'),
        make_bridge_node(dest_domain=peer_domain, node_suffix='peer'),
    ]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])
