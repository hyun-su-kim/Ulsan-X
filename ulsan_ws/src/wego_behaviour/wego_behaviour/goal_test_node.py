"""
behaviour_node 테스트용 — /on_duty + /goal_destination 수동 발행
사용법: ros2 run wego_behaviour goal_test_node
"""
import yaml
import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
from std_msgs.msg import Bool, String


class GoalTestNode(Node):
    def __init__(self, waypoints: dict):
        super().__init__('goal_test_node')
        self._waypoints = waypoints
        self._on_duty_pub = self.create_publisher(Bool, '/on_duty', 10)
        self._dest_pub = self.create_publisher(String, '/goal_destination', 10)

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
        msg = String()
        msg.data = key
        self._dest_pub.publish(msg)
        label = self._waypoints[key]['label']
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
