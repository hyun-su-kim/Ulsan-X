import math
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
from limo_msgs.msg import GuideGoal
from limo_msgs.srv import Speak
from geometry_msgs.msg import PoseWithCovarianceStamped
from yasmin import StateMachine, Blackboard
from diagnostic_updater import Updater
from diagnostic_msgs.msg import DiagnosticStatus

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
        self.pending_tts: str = ''   # 출발 안내 멘트 — GuideGoal로 목적지와 함께 도착
        self.latest_amcl_pose: PoseWithCovarianceStamped | None = None
        self._pause_flag   = False
        self._resume_flag  = False
        self._abort_flag   = False
        self._recover_flag = False
        self._fsm_status   = 'UNKNOWN'

        # /diagnostics 발행 — GUI 시스템 상태 패널에서 연결 확인용
        self._diag_updater = Updater(self)
        self._diag_updater.setHardwareID('wego_behaviour')
        self._diag_updater.add('wego_behaviour', self._diag_check)

        self._status_pub      = self.create_publisher(String, '/robot_status', 10)
        self._speak_pub       = self.create_publisher(String, '/speak_text', 10)
        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 1)

        self.create_subscription(GuideGoal, '/goal_destination', self._dest_cb, 10)
        self.create_subscription(Empty,  '/pause',   self._pause_cb,   10)
        self.create_subscription(Empty,  '/resume',  self._resume_cb,  10)
        self.create_subscription(Empty,  '/abort',   self._abort_cb,   10)
        self.create_subscription(Empty,  '/recover', self._recover_cb, 10)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl_cb, 1)


        self._home_dock_cli = self.create_client(Trigger, '/aruco_home_dock')
        self._speak_cli     = self.create_client(Speak, '/speak')

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

    def _recover_cb(self, _: Empty) -> None:
        self._recover_flag = True
        self.get_logger().info('recover 수신 (관리자 복구완료)')

    def _amcl_cb(self, msg: PoseWithCovarianceStamped) -> None:
        self.latest_amcl_pose = msg

    def _dest_cb(self, msg: GuideGoal) -> None:
        with self._waypoints_lock:
            if msg.destination in self.waypoints:
                self.pending_destination = msg.destination
                self.pending_tts = msg.tts_text   # 출발 발화 문구 (목적지와 원자적으로 도착)
            else:
                self.get_logger().warn(f'알 수 없는 목적지 키: {msg.destination}')


    # ── diagnostics ──────────────────────────────────────────────────

    def _diag_check(self, stat: DiagnosticStatus) -> DiagnosticStatus:
        if self._fsm_status == 'UNKNOWN':
            stat.summary(DiagnosticStatus.ERROR, self._fsm_status)
        elif self._fsm_status == 'FAILED':
            stat.summary(DiagnosticStatus.WARN, self._fsm_status)
        else:
            stat.summary(DiagnosticStatus.OK, self._fsm_status)
        return stat

    # ── 발행 헬퍼 ────────────────────────────────────────────────────

    def publish_status(self, status: str) -> None:
        self._fsm_status = status
        msg = String()
        msg.data = status
        self._status_pub.publish(msg)

    def speak_text(self, text: str) -> None:
        msg = String()
        msg.data = text
        self._speak_pub.publish(msg)

    def publish_initial_pose_home(self) -> None:
        """관리자 복구 시 home 좌표를 /initialpose로 발행해 AMCL을 리셋.

        FAILED는 주행/도킹이 깨진 상태라 PBVS 도킹(aruco_home_dock)의 AMCL 리셋을
        거치지 못한다. 관리자가 로봇을 물리적으로 home에 가져다 놓았다는 전제로,
        behaviour_node(AMCL과 동일 도메인)가 직접 home 좌표를 발행한다.
        """
        wp = self.waypoints[self.home_key]
        yaw = float(wp['yaw'])
        msg = PoseWithCovarianceStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x    = float(wp['x'])
        msg.pose.pose.position.y    = float(wp['y'])
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance[0]  = 0.05
        msg.pose.covariance[7]  = 0.05
        msg.pose.covariance[35] = 0.05
        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f'[복구 AMCL 리셋] {self.home_key} x={wp["x"]} y={wp["y"]} '
            f'yaw={math.degrees(yaw):.1f}°'
        )

    def speak_and_wait(self, text: str) -> bool:
        """발화 서비스(/speak)를 동기 호출 — 재생이 끝난 뒤 반환.

        출발 안내를 '발화 완료 후 주행'으로 동기화하기 위함. 서비스가 없거나 실패해도
        주행은 진행한다(발화는 부가 기능). 빈 문구면 즉시 통과.
        """
        if not text:
            return True
        if not self._speak_cli.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn('/speak 서비스 없음 — 발화 생략하고 진행')
            return False
        req = Speak.Request()
        req.text = text
        future = self._speak_cli.call_async(req)
        while not future.done():
            time.sleep(0.05)
        result = future.result()
        return bool(result and result.success)

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
    sm.add_state('FAILED',    FailedState(node),              transitions={'recovered': 'IDLE'})
    sm.add_state('RETURNING', ReturningState(node, navigator), transitions={'succeeded': 'IDLE',      'failed': 'FAILED', 'paused': 'WAITING'})
    sm.add_state('WAITING',   WaitingState(node),             transitions={'resume_guiding': 'GUIDING', 'resume_returning': 'RETURNING'})

    try:
        bb = Blackboard()
        bb['from_home'] = False
        sm(bb)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
