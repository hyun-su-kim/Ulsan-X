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

from wego_behaviour.states import FailedState, GuidingState, IdleState, ReturningState, WaitingState
from nav2_simple_commander.robot_navigator import BasicNavigator


class BehaviourNode(Node):
    def __init__(self, waypoints: dict, domain_home_map: dict):
        super().__init__('wego_behaviour')

        self._waypoints_lock = threading.Lock()
        self.waypoints = waypoints

        domain_id = os.environ.get('ROS_DOMAIN_ID', '6')
        self.home_key: str = domain_home_map.get(domain_id, 'home_robot1')
        self.get_logger().info(f'home_key: {self.home_key} (DOMAIN_ID={domain_id})')

        self.pending_destination: str | None = None
        self.latest_amcl_pose: PoseWithCovarianceStamped | None = None
        self._pause_flag  = False
        self._resume_flag = False
        self._abort_flag  = False

        self._status_pub = self.create_publisher(String, '/robot_status', 10)
        self._speak_pub  = self.create_publisher(String, '/speak_text', 10)

        self.create_subscription(String, '/goal_destination', self._dest_cb, 10)
        self.create_subscription(Empty,  '/pause',  self._pause_cb,  10)
        self.create_subscription(Empty,  '/resume', self._resume_cb, 10)
        self.create_subscription(Empty,  '/abort',  self._abort_cb,  10)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl_cb, 1)


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

    def _abort_cb(self, _: Empty) -> None:
        self._abort_flag = True
        self.get_logger().info('abort 수신')

    def _amcl_cb(self, msg: PoseWithCovarianceStamped) -> None:
        self.latest_amcl_pose = msg

    def _dest_cb(self, msg: String) -> None:
        with self._waypoints_lock:
            if msg.data in self.waypoints:
                self.pending_destination = msg.data
            else:
                self.get_logger().warn(f'알 수 없는 목적지 키: {msg.data}')


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

    with open(f'{pkg_share}/config/waypoints.yaml') as f:
        waypoints = yaml.safe_load(f)['waypoints']

    with open(f'{pkg_share}/config/robot_config.yaml') as f:
        config = yaml.safe_load(f)
        domain_home_map = config['domain_home_map']

    node = BehaviourNode(waypoints, domain_home_map)

    navigator = BasicNavigator()
    navigator.waitUntilNav2Active()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    sm = StateMachine(outcomes=['finished'])
    sm.add_state('IDLE',      IdleState(node),                transitions={'goto_destination': 'GUIDING'})
    sm.add_state('GUIDING',   GuidingState(node, navigator),  transitions={'succeeded': 'RETURNING', 'failed': 'FAILED', 'paused': 'WAITING', 'aborted': 'RETURNING'})
    sm.add_state('FAILED',    FailedState(node),              transitions={'return_home': 'RETURNING'})
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
