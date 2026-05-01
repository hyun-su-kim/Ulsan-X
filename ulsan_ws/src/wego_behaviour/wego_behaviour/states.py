import math
import time

from yasmin import State
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from std_srvs.srv import Trigger


def _make_pose(wp: dict) -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.pose.position.x = float(wp['x'])
    pose.pose.position.y = float(wp['y'])
    pose.pose.orientation.z = math.sin(float(wp['yaw']) / 2.0)
    pose.pose.orientation.w = math.cos(float(wp['yaw']) / 2.0)
    return pose


class IdleState(State):
    """대기 상태: on_duty=True + /goal_destination 수신 시 GUIDING 전환."""

    def __init__(self, node):
        super().__init__(outcomes=['goto_destination'])
        self._node = node

    def execute(self, blackboard):
        self._node.publish_status('IDLE')
        self._node.get_logger().info('IDLE: 방문자 대기 중')

        # on_duty이면서 목적지가 설정될 때까지 대기
        # (wego_voice → /goal_destination 토픽으로 목적지 키 수신)
        while True:
            if self._node.on_duty and self._node.pending_destination:
                dest_key = self._node.pending_destination
                self._node.pending_destination = None
                blackboard['destination'] = self._node.waypoints[dest_key]
                self._node.get_logger().info(
                    f'목적지 확정: {blackboard["destination"]["label"]}'
                )
                return 'goto_destination'
            time.sleep(0.1)


class GuidingState(State):
    """안내 상태: 목적지까지 navigate_to_pose 실행."""

    def __init__(self, node, navigator: BasicNavigator):
        super().__init__(outcomes=['succeeded', 'failed'])
        self._node = node
        self._navigator = navigator

    def execute(self, blackboard):
        self._node.publish_status('BUSY')
        destination = blackboard['destination']
        self._node.get_logger().info(
            f'GUIDING: {destination["label"]} 로 이동 중'
        )

        self._navigator.goToPose(_make_pose(destination))

        while not self._navigator.isTaskComplete():
            time.sleep(0.1)

        result = self._navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self._node.get_logger().info('목적지 도착')
            return 'succeeded'

        self._node.get_logger().warn(f'목적지 이동 실패: {result}')
        return 'failed'


class ReturningState(State):
    """복귀 상태: Nav2 홈 이동 → ArUco visual servoing 정밀 정차 → AMCL 리셋."""

    def __init__(self, node, navigator: BasicNavigator):
        super().__init__(outcomes=['succeeded', 'failed'])
        self._node = node
        self._navigator = navigator
        self._aruco_client = node.create_client(Trigger, '/aruco_correct')

    def _nav_to(self, home: dict) -> bool:
        self._navigator.goToPose(_make_pose(home))
        while not self._navigator.isTaskComplete():
            time.sleep(0.1)
        return self._navigator.getResult() == TaskResult.SUCCEEDED

    def execute(self, blackboard):
        self._node.publish_status('RETURNING')
        home = self._node.waypoints[self._node.home_key]

        # Step 1: Nav2로 홈 근처 이동
        self._node.get_logger().info('RETURNING: 홈으로 이동 중')
        if not self._nav_to(home):
            self._node.get_logger().warn('홈 이동 실패')
            return 'failed'

        # Step 2: ArUco visual servoing → 정밀 정차
        if not self._aruco_client.wait_for_service(timeout_sec=2.0):
            self._node.get_logger().warn('aruco_localizer 없음 — 정밀 정차 생략')
            return 'succeeded'

        future = self._aruco_client.call_async(Trigger.Request())
        while not future.done():
            time.sleep(0.05)
        resp = future.result()

        if not resp.success:
            self._node.get_logger().warn(f'ArUco 정밀 정차 실패: {resp.message}')
            return 'succeeded'

        # /initialpose는 aruco_localizer가 정차 완료 시 직접 발행
        self._node.get_logger().info(f'정밀 정차 완료: {resp.message}')
        return 'succeeded'
