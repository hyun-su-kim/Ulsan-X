import math
import time

from yasmin import State
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult


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

        while True:
            if self._node.pending_destination:
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
        super().__init__(outcomes=['succeeded', 'failed', 'paused'])
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
            if self._node._pause_flag:
                self._navigator.cancelTask()
                blackboard['return_to'] = 'GUIDING'
                return 'paused'
            time.sleep(0.1)

        result = self._navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            self._node.get_logger().info('목적지 도착')
            # [DEBUG] goal 도착 시 AMCL pose 출력
            p = self._node.latest_amcl_pose
            if p:
                pos = p.pose.pose.position
                q = p.pose.pose.orientation
                yaw = math.atan2(
                    2.0 * (q.w * q.z + q.x * q.y),
                    1.0 - 2.0 * (q.y ** 2 + q.z ** 2)
                )
                self._node.get_logger().info(
                    f'[DEBUG] AMCL pose at goal: '
                    f'x={pos.x:.3f} y={pos.y:.3f} yaw={math.degrees(yaw):.1f}°'
                )
            # [DEBUG] end
            self._node.speak_text('목적지에 도착했습니다.')
            return 'succeeded'

        self._node.get_logger().warn(f'목적지 이동 실패: {result}')
        return 'failed'


class WaitingState(State):
    """대기 상태: wego_traffic의 pause 수신 시 진입. resume 수신 시 이전 상태로 복귀."""

    def __init__(self, node):
        super().__init__(outcomes=['resume_guiding', 'resume_returning'])
        self._node = node

    def execute(self, blackboard):
        self._node._pause_flag = False  # 진입 시 리셋 (중복 pause 방지)
        self._node.publish_status('WAITING')
        self._node.get_logger().info('WAITING: 상대 로봇 통과 대기 중')

        while not self._node._resume_flag:
            time.sleep(0.1)

        self._node._resume_flag = False
        return_to = blackboard.get('return_to', 'RETURNING')
        self._node.get_logger().info(f'WAITING: resume → {return_to}')
        return 'resume_guiding' if return_to == 'GUIDING' else 'resume_returning'


class ReturningState(State):
    """복귀 상태: Nav2로 홈 이동. AMCL 보정은 aruco_pose_corrector가 passive하게 수행."""

    def __init__(self, node, navigator: BasicNavigator):
        super().__init__(outcomes=['succeeded', 'failed', 'paused'])
        self._node = node
        self._navigator = navigator

    def execute(self, blackboard):
        self._node.publish_status('RETURNING')
        home = self._node.waypoints[self._node.home_key]

        self._node.get_logger().info('RETURNING: 홈으로 이동 중')
        self._navigator.goToPose(_make_pose(home))
        while not self._navigator.isTaskComplete():
            if self._node._pause_flag:
                self._navigator.cancelTask()
                blackboard['return_to'] = 'RETURNING'
                return 'paused'
            time.sleep(0.1)

        if self._navigator.getResult() == TaskResult.SUCCEEDED:
            self._node.get_logger().info('홈 복귀 완료')
            return 'succeeded'

        self._node.get_logger().warn('홈 이동 실패')
        return 'failed'
