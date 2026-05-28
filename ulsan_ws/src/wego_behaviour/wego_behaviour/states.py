import math
import time

from yasmin import State
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult


_GLASS_ROUTE_DESTINATIONS = {
    'counseling_1', 'counseling_2', 'counter',
    'intensive_counseling_1', 'intensive_counseling_2',
    'multi', 'vice_principal',
}


def _needs_glass_via(dest_key: str) -> bool:
    return dest_key in _GLASS_ROUTE_DESTINATIONS


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

        _tick = 0
        while True:
            if self._node.pending_destination:
                dest_key = self._node.pending_destination
                self._node.pending_destination = None
                blackboard['destination'] = self._node.waypoints[dest_key]
                blackboard['destination_key'] = dest_key
                # 홈 출발임을 표시 — GuidingState에서 Spin 선실행 트리거
                blackboard['from_home'] = True
                self._node.get_logger().info(
                    f'목적지 확정: {blackboard["destination"]["label"]}'
                )
                return 'goto_destination'
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:  # 1초마다 재발행 — GUI 늦게 켜져도 연결 감지
                self._node.publish_status('IDLE')


class FailedState(State):
    """임무 실패 상태: 실패 로깅 후 홈 복귀."""

    def __init__(self, node):
        super().__init__(outcomes=['return_home'])
        self._node = node

    def execute(self, blackboard):
        self._node.publish_status('FAILED')
        self._node.get_logger().warn('임무 실패 — 10초 대기 후 홈 복귀')
        self._node.speak_text(
            '오류가 발생하여 안내에 실패했습니다. 현재 위치에서 관리자를 기다려 주세요.'
        )
        for _ in range(10):
            time.sleep(1.0)
            self._node.publish_status('FAILED')
        return 'return_home'


class GuidingState(State):
    """안내 상태: 목적지까지 navigate_to_pose 실행."""

    def __init__(self, node, navigator: BasicNavigator):
        super().__init__(outcomes=['succeeded', 'failed', 'paused', 'aborted'])
        self._node = node
        self._navigator = navigator

    def execute(self, blackboard):
        self._node.publish_status('BUSY')
        destination = blackboard['destination']
        self._node.get_logger().info(
            f'GUIDING: {destination["label"]} 로 이동 중'
        )

        # 홈 출발 시 180° Spin 선실행
        # 목적: (1) AMCL 파티클 수렴 — 제자리 회전으로 다양한 각도 스캔 수집
        #        (2) Nav2 출발 직후 180° 회전 부담 제거 — SimpleProgressChecker 실패 방지
        # WAITING resume 재진입 시에는 from_home=False이므로 이중 Spin 없음
        if blackboard.get('from_home'):
            blackboard['from_home'] = False  # 재진입 시 이중 Spin 방지 — 즉시 초기화
            self._node.get_logger().info('홈 출발 — 180° Spin 시작 (AMCL 수렴)')
            self._navigator.spin(spin_dist=math.pi)  # 180° 회전

            _spin_tick = 0
            while not self._navigator.isTaskComplete():
                if self._node._abort_flag:
                    # abort 수신 — Spin 취소 후 즉시 RETURNING
                    self._navigator.cancelTask()
                    self._node._abort_flag = False
                    self._node.get_logger().info('Spin 중 abort 수신 → RETURNING')
                    return 'aborted'
                if self._node._pause_flag:
                    # pause 수신 — Spin 취소 후 WAITING
                    # 재개 시 from_home=False이므로 재Spin 없이 바로 주행 진입
                    self._navigator.cancelTask()
                    blackboard['return_to'] = 'GUIDING'
                    return 'paused'
                time.sleep(0.1)
                _spin_tick += 1
                if _spin_tick % 10 == 0:
                    self._node.publish_status('BUSY')

            if self._navigator.getResult() == TaskResult.SUCCEEDED:
                self._node.get_logger().info('180° Spin 완료 — 주행 시작')
            else:
                # Spin 실패해도 주행 계속 (graceful degradation)
                self._node.get_logger().warn('Spin 실패 — 주행 계속')

        try:
            dest_key = blackboard['destination_key']
        except KeyError:
            dest_key = ''
        if _needs_glass_via(dest_key):
            glass_entry = _make_pose(self._node.waypoints['glass_entry'])
            glass_exit = _make_pose(self._node.waypoints['glass_exit'])
            self._navigator.goThroughPoses([glass_entry, glass_exit, _make_pose(destination)])
        else:
            self._navigator.goToPose(_make_pose(destination))

        _tick = 0
        while not self._navigator.isTaskComplete():
            if self._node._abort_flag:
                self._navigator.cancelTask()
                self._node._abort_flag = False
                self._node.get_logger().info('GUIDING: abort → RETURNING')
                return 'aborted'
            if self._node._pause_flag:
                self._navigator.cancelTask()
                blackboard['return_to'] = 'GUIDING'
                return 'paused'
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:
                self._node.publish_status('BUSY')

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

        _tick = 0
        while not self._node._resume_flag:
            if self._node._abort_flag:
                self._node._abort_flag = False
                if blackboard.get('return_to') == 'GUIDING':
                    blackboard['return_to'] = 'RETURNING'
                    self._node.get_logger().info('WAITING: abort → return_to 변경 (GUIDING→RETURNING)')
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:
                self._node.publish_status('WAITING')

        self._node._resume_flag = False
        try:
            return_to = blackboard['return_to']
        except KeyError:
            return_to = 'RETURNING'
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
        home_key    = self._node.home_key
        staging_key = home_key + '_staging'
        waypoints   = self._node.waypoints

        # staging이 있으면 staging까지 Nav2 이동 후 IBVS, 없으면 home으로 직접
        nav_target = waypoints[staging_key] if staging_key in waypoints else waypoints[home_key]
        nav_label  = 'staging' if staging_key in waypoints else '홈(직접)'

        self._node.get_logger().info(f'RETURNING: {nav_label}으로 이동 중')
        try:
            dest_key = blackboard['destination_key']
        except KeyError:
            dest_key = ''
        if _needs_glass_via(dest_key):
            glass_entry = _make_pose(waypoints['glass_entry'])
            glass_exit  = _make_pose(waypoints['glass_exit'])
            self._navigator.goThroughPoses([glass_exit, glass_entry, _make_pose(nav_target)])
        else:
            self._navigator.goToPose(_make_pose(nav_target))

        _tick = 0
        while not self._navigator.isTaskComplete():
            if self._node._pause_flag:
                self._navigator.cancelTask()
                blackboard['return_to'] = 'RETURNING'
                return 'paused'
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:
                self._node.publish_status('RETURNING')

        if self._navigator.getResult() == TaskResult.SUCCEEDED:
            self._node.get_logger().info(f'{nav_label} 도착 — IBVS 도킹 시작')
            self._node.call_home_dock()
            return 'succeeded'

        self._node.get_logger().warn('홈 이동 실패')
        return 'failed'
