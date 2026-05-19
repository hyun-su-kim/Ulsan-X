import json
import os
import time
import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import String, Empty
from std_srvs.srv import Trigger
from geometry_msgs.msg import PoseWithCovarianceStamped
from yasmin import StateMachine, Blackboard

from wego_behaviour.states import GuidingState, IdleState, ReturningState, WaitingState
from wego_msgs.srv import WaypointCRUD
from nav2_simple_commander.robot_navigator import BasicNavigator


class BehaviourNode(Node):
    def __init__(self, waypoints: dict, waypoints_path: str, domain_home_map: dict):
        super().__init__('wego_behaviour')

        self._waypoints_lock = threading.Lock()
        self.waypoints = waypoints
        self._waypoints_path = waypoints_path

        domain_id = os.environ.get('ROS_DOMAIN_ID', '6')
        self.home_key: str = domain_home_map.get(domain_id, 'home_robot1')
        self.get_logger().info(f'home_key: {self.home_key} (DOMAIN_ID={domain_id})')

        self.pending_destination: str | None = None
        self.latest_amcl_pose: PoseWithCovarianceStamped | None = None
        self._pause_flag  = False
        self._resume_flag = False

        self._status_pub = self.create_publisher(String, '/robot_status', 10)
        self._speak_pub  = self.create_publisher(String, '/speak_text', 10)

        self.create_subscription(String, '/goal_destination', self._dest_cb, 10)
        self.create_subscription(Empty,  '/pause',  self._pause_cb,  10)
        self.create_subscription(Empty,  '/resume', self._resume_cb, 10)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl_cb, 1)

        self.create_service(WaypointCRUD, '/waypoint_crud', self._waypoint_crud_cb)
        self.get_logger().info('/waypoint_crud 서비스 준비 완료')

        self._home_dock_cli = self.create_client(Trigger, '/aruco_home_dock')

    # ── 콜백 ──────────────────────────────────────────────────────────

    def _pause_cb(self, _: Empty) -> None:
        self._pause_flag  = True
        self._resume_flag = False
        self.get_logger().info('pause 수신')

    def _resume_cb(self, _: Empty) -> None:
        self._resume_flag = True
        self._pause_flag  = False
        self.get_logger().info('resume 수신')

    def _amcl_cb(self, msg: PoseWithCovarianceStamped) -> None:
        self.latest_amcl_pose = msg

    def _dest_cb(self, msg: String) -> None:
        with self._waypoints_lock:
            if msg.data in self.waypoints:
                self.pending_destination = msg.data
            else:
                self.get_logger().warn(f'알 수 없는 목적지 키: {msg.data}')

    # ── Waypoint CRUD 서비스 ──────────────────────────────────────────

    def _waypoint_crud_cb(self, req: WaypointCRUD.Request, res: WaypointCRUD.Response):
        action = req.action.strip().lower()

        if action == 'list':
            with self._waypoints_lock:
                res.waypoints_json = json.dumps(self.waypoints, ensure_ascii=False)
            res.success = True
            res.message = f'{len(self.waypoints)}개 waypoint 반환'

        elif action == 'add':
            if not req.key:
                res.success = False
                res.message = 'key가 비어 있습니다'
                return res
            with self._waypoints_lock:
                if req.key in self.waypoints:
                    res.success = False
                    res.message = f'이미 존재하는 key: {req.key}'
                    return res
                self.waypoints[req.key] = {
                    'label': req.label,
                    'x': req.x, 'y': req.y, 'yaw': req.yaw,
                }
                self._save_waypoints()
            res.success = True
            res.message = f'추가 완료: {req.key}'
            self.get_logger().info(f'waypoint 추가: {req.key}')

        elif action == 'update':
            with self._waypoints_lock:
                if req.key not in self.waypoints:
                    res.success = False
                    res.message = f'존재하지 않는 key: {req.key}'
                    return res
                self.waypoints[req.key] = {
                    'label': req.label,
                    'x': req.x, 'y': req.y, 'yaw': req.yaw,
                }
                self._save_waypoints()
            res.success = True
            res.message = f'수정 완료: {req.key}'
            self.get_logger().info(f'waypoint 수정: {req.key}')

        elif action == 'delete':
            with self._waypoints_lock:
                if req.key not in self.waypoints:
                    res.success = False
                    res.message = f'존재하지 않는 key: {req.key}'
                    return res
                del self.waypoints[req.key]
                self._save_waypoints()
            res.success = True
            res.message = f'삭제 완료: {req.key}'
            self.get_logger().info(f'waypoint 삭제: {req.key}')

        else:
            res.success = False
            res.message = f'알 수 없는 action: {action}'

        return res

    def _save_waypoints(self) -> None:
        """현재 waypoints 딕셔너리를 YAML 파일에 저장. Lock 안에서 호출할 것."""
        data = {'waypoints': self.waypoints}
        with open(self._waypoints_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    # ── 발행 헬퍼 ────────────────────────────────────────────────────

    def publish_status(self, status: str) -> None:
        msg = String()
        msg.data = status
        self._status_pub.publish(msg)

    def speak_text(self, text: str) -> None:
        msg = String()
        msg.data = text
        self._speak_pub.publish(msg)

    def call_home_dock(self) -> bool:
        if not self._home_dock_cli.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn('/aruco_home_dock 서비스 없음 — Nav2 정차 유지')
            return False
        future = self._home_dock_cli.call_async(Trigger.Request())
        while not future.done():
            time.sleep(0.05)
        result = future.result()
        self.get_logger().info(f'aruco_home_dock 결과: {result.message}')
        return result.success


def main():
    rclpy.init()

    pkg_share = get_package_share_directory('wego_behaviour')
    waypoints_path = f'{pkg_share}/config/waypoints.yaml'

    with open(waypoints_path) as f:
        waypoints = yaml.safe_load(f)['waypoints']

    with open(f'{pkg_share}/config/robot_config.yaml') as f:
        config = yaml.safe_load(f)
        domain_home_map = config['domain_home_map']

    node = BehaviourNode(waypoints, waypoints_path, domain_home_map)

    navigator = BasicNavigator()
    navigator.waitUntilNav2Active()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    sm = StateMachine(outcomes=['finished'])
    sm.add_state('IDLE',      IdleState(node),                transitions={'goto_destination': 'GUIDING'})
    sm.add_state('GUIDING',   GuidingState(node, navigator),  transitions={'succeeded': 'RETURNING', 'failed': 'IDLE', 'paused': 'WAITING'})
    sm.add_state('RETURNING', ReturningState(node, navigator), transitions={'succeeded': 'IDLE',      'failed': 'IDLE', 'paused': 'WAITING'})
    sm.add_state('WAITING',   WaitingState(node),             transitions={'resume_guiding': 'GUIDING', 'resume_returning': 'RETURNING'})

    try:
        sm(Blackboard())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
