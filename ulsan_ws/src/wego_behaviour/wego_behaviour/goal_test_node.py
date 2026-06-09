"""
[임시 테스트 노드 — wego_voice 완성 후 삭제]
wego_voice(음성 파이프라인) 구현 전까지 /on_duty, /goal_destination을
키보드로 수동 발행하여 behaviour_node FSM 동작을 검증하는 용도.
wego_voice가 /goal_destination을, wego_coordinator가 /on_duty를 담당하게 되면 불필요.
"""
import yaml
import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
from std_msgs.msg import Bool
from limo_msgs.msg import GuideGoal


class GoalTestNode(Node):
    def __init__(self, waypoints: dict):
        super().__init__('goal_test_node')
        self._waypoints = waypoints
        self._on_duty_pub = self.create_publisher(Bool, '/on_duty', 10)
        self._dest_pub = self.create_publisher(GuideGoal, '/goal_destination', 10)

        # on_duty=True 고정 발행 (1Hz)
        self.create_timer(1.0, self._publish_on_duty)
        self.get_logger().info('goal_test_node 기동. /on_duty=True 발행 중.')
        self._print_menu()

    def _publish_on_duty(self):
        msg = Bool()
        msg.data = True
        self._on_duty_pub.publish(msg)

    def send_goal(self, key: str):
        if key not in self._waypoints:
            print(f'[!] 없는 키: {key}')
            self._print_menu()
            return
        label = self._waypoints[key]['label']
        msg = GuideGoal()
        msg.destination = key
        msg.tts_text = '테스트 시작합니다.'   # 발화 테스트용 — 비우면 발화 생략
        self._dest_pub.publish(msg)
        print(f'[→] /goal_destination 발행: {key} ({label})')

    def _print_menu(self):
        print('\n─── 목적지 목록 ───')
        for k, v in self._waypoints.items():
            print(f'  {k:30s} ({v["label"]})')
        print('───────────────────')
        print('키 입력 + Enter=발행 | q=종료\n')


def main():
    rclpy.init()

    pkg = get_package_share_directory('wego_behaviour')
    with open(f'{pkg}/config/waypoints.yaml') as f:
        waypoints = yaml.safe_load(f)['waypoints']

    node = GoalTestNode(waypoints)

    import threading
    def keyboard_loop():
        while rclpy.ok():
            try:
                cmd = input('> ').strip()
            except EOFError:
                break
            if cmd == 'q':
                rclpy.shutdown()
                break
            elif cmd:
                node.send_goal(cmd)

    t = threading.Thread(target=keyboard_loop, daemon=True)
    t.start()

    rclpy.spin(node)
    node.destroy_node()
