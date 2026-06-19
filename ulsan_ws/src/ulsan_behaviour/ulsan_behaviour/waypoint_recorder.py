import math
import threading
import yaml
import os
import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseWithCovarianceStamped

YAML_PATH = os.path.join(
    get_package_share_directory('ulsan_behaviour'), 'config', 'waypoints.yaml'
)


def quat_to_yaw(qz, qw):
    return round(math.atan2(2.0 * qw * qz, 1.0 - 2.0 * qz * qz), 4)


class WaypointRecorder(Node):
    def __init__(self):
        super().__init__('waypoint_recorder')
        self._lock = threading.Lock()
        self._pose = None

        with open(YAML_PATH, 'r') as f:
            self._data = yaml.safe_load(f)

        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._cb, 10
        )
        self.get_logger().info(f'로드: {YAML_PATH}')
        self._print_remaining()

    def _cb(self, msg):
        p = msg.pose.pose
        with self._lock:
            self._pose = (
                round(p.position.x, 4),
                round(p.position.y, 4),
                quat_to_yaw(p.orientation.z, p.orientation.w),
            )

    def save(self, key):
        wp = self._data['waypoints']
        if key not in wp:
            print(f'[!] "{key}" 없음. 아래 키 목록 확인')
            self._print_remaining()
            return

        with self._lock:
            pose = self._pose
        if pose is None:
            print('[!] amcl_pose 미수신 — AMCL 기동 확인')
            return

        x, y, yaw = pose
        wp[key]['x'] = x
        wp[key]['y'] = y
        wp[key]['yaw'] = yaw
        print(f'[OK] {key} ({wp[key]["label"]}) → x={x}, y={y}, yaw={yaw}')
        self._print_remaining()

    def write_yaml(self):
        with open(YAML_PATH, 'w') as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)
        print(f'[저장] {YAML_PATH}')

    def _print_remaining(self):
        remaining = [
            f'  {k:30s} ({v["label"]})'
            for k, v in self._data['waypoints'].items()
            if v['x'] == 0.0 and v['y'] == 0.0
        ]
        if remaining:
            print('\n─── 미입력 목적지 ───')
            print('\n'.join(remaining))
            print('─────────────────────')
        else:
            print('\n[완료] 모든 목적지 입력됨')
        print('키 입력 + Enter=저장 | q=yaml쓰고종료\n')


def keyboard_loop(node):
    while rclpy.ok():
        try:
            cmd = input('> ').strip()
        except EOFError:
            break
        if cmd == 'q':
            node.write_yaml()
            rclpy.shutdown()
            break
        elif cmd:
            node.save(cmd)


def main():
    rclpy.init()
    node = WaypointRecorder()
    kb = threading.Thread(target=keyboard_loop, args=(node,), daemon=True)
    kb.start()
    rclpy.spin(node)
    node.destroy_node()
