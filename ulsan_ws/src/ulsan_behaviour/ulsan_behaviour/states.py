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


# 상담 계열 목적지 라벨 — 도착 멘트 개인화용(예약/현장방문 공통, destination_key로만 분기).
# FastAPI ROOM_LABELS와 같은 문구이나, 도착 멘트는 목적지로만 결정되므로 behaviour가 직접 만든다.
_COUNSELING_LABELS = {
    'counseling_1':           '상담실 1',
    'counseling_2':           '상담실 2',
    'intensive_counseling_1': '집중상담실 1',
    'intensive_counseling_2': '집중상담실 2',
}


def _arrival_tts(dest_key: str) -> str:
    """도착 안내 멘트. 상담 계열은 라벨+대기 안내, 그 외(강의실 등)는 일반 문구."""
    label = _COUNSELING_LABELS.get(dest_key)
    if label:
        return (f'{label}에 도착했습니다. '
                f'상담실에서 기다리고 계시면 상담을 도와드리겠습니다.')
    return '목적지에 도착했습니다.'


def _bb_get(bb, key, default=None):
    """yasmin Blackboard.get()은 기본값 인자가 없고 키가 없으면 예외를 던진다.
    (dict.get(key, default)처럼 쓰면 TypeError) — 안전하게 기본값을 제공한다."""
    try:
        return bb[key]
    except Exception:
        return default


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
        # 잔류 pause 정리 + BT 정지 신호 해제(다음 출발이 묶이지 않도록)
        self._node.reset_pause()
        self._node.publish_motion_hold(False)
        self._node.publish_status('IDLE')
        self._node.get_logger().info('IDLE: 방문자 대기 중')

        _tick = 0
        while True:
            if self._node.pending_destination:
                dest_key = self._node.pending_destination
                self._node.pending_destination = None
                blackboard['destination'] = self._node.waypoints[dest_key]
                blackboard['destination_key'] = dest_key
                # 출발 안내 멘트 — GuidingState가 발화-완료대기-주행으로 처리
                blackboard['departure_tts'] = self._node.pending_tts
                self._node.pending_tts = ''
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
    """임무 실패 상태: (안내 중 실패만) TTS 발화 후 관리자 복구(/recover) 대기.

    Nav2 주행 실패(GUIDING/RETURNING)·PBVS 도킹 실패(DOCKING)는 모두 '주행 능력이
    깨진' 상태이므로 자동 재주행을 하지 않는다(고장난 기능으로 자가복구 시도하는
    모순 + 무한루프 방지). 관리자가 로봇을 물리적으로 home에 가져다 놓고 관제 UI에서
    복구 신호(/recover)를 보내면, home 좌표로 AMCL 리셋 후 IDLE로 복귀한다.

    TTS는 **안내(GUIDING) 중 실패에서만** 발화한다 — 그때만 방문자가 곁에 있어 상황을
    음성으로 인지시킬 필요가 있다. 복귀·도킹 실패는 방문자가 없고 관제 GUI가 표시하므로
    TTS 불필요 (2026-06-09).
    """

    _FAIL_TTS_GUIDING = '안내 주행 중 문제가 발생했습니다. 관리자를 기다려주세요.'

    def __init__(self, node):
        super().__init__(outcomes=['recovered'])
        self._node = node

    def execute(self, blackboard):
        self._node.publish_status('FAILED')
        failed_from = _bb_get(blackboard, 'failed_from', 'GUIDING')
        self._node.get_logger().error(f'임무 실패 ({failed_from}) — 관리자 복구 대기')
        if failed_from == 'GUIDING':
            self._node.speak_text(self._FAIL_TTS_GUIDING)

        # 관리자가 로봇을 home에 가져다 놓고 관제 UI에서 [복구완료] → /recover 발행 대기
        self._node._recover_flag = False
        _tick = 0
        while not self._node._recover_flag:
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:
                self._node.publish_status('FAILED')
        self._node._recover_flag = False

        # 로봇은 이제 물리적으로 home에 있음 → home 좌표로 AMCL 리셋
        self._node.publish_initial_pose_home()
        self._node.get_logger().info('복구 완료 — IDLE 복귀')
        return 'recovered'


class GuidingState(State):
    """안내 상태: 목적지까지 navigate_to_pose 실행."""

    def __init__(self, node, navigator: BasicNavigator):
        super().__init__(outcomes=['succeeded', 'failed', 'paused', 'aborted'])
        self._node = node
        self._navigator = navigator

    def execute(self, blackboard):
        self._node.publish_status('BUSY')
        destination = blackboard['destination']
        try:
            dest_key = blackboard['destination_key']
        except KeyError:
            dest_key = ''

        # ── 일회성 출발 행위 (출발TTS + 180°Spin + 목표 발행) ──────────────
        # WAITING 재개(resuming=True) 시에는 전부 스킵 — 목표를 cancel하지 않았으므로
        # 살아있는 주행 목표를 그대로 이어받아 감시 루프부터 재진입한다.
        if not _bb_get(blackboard, 'resuming'):
            self._node.get_logger().info(
                f'GUIDING: {destination["label"]} 로 이동 중'
            )

            # 홈 출발 시 출발 안내 발화(완료 대기) + 180° Spin 선실행
            #  Spin 목적: (1) AMCL 파티클 수렴 (2) 출발 직후 180° 회전 부담 제거(progress 실패 방지)
            #  Spin 구간은 pause 미검사(abort만): Spin은 FollowPath가 아닌 별도 액션이라
            #  /motion_hold로 halt되지 않고, 중간 취소 시 살아있는 nav 목표가 없어 resume이
            #  깨진다. 홈 제자리 회전은 이동이 없어 위험 낮음 → 짧게 마치고 본 주행부터 pause 적용.
            if _bb_get(blackboard, 'from_home'):
                blackboard['from_home'] = False
                tts = _bb_get(blackboard, 'departure_tts', '')
                if tts:
                    self._node.get_logger().info('출발 안내 발화 — 완료까지 대기')
                    self._node.speak_and_wait(tts)
                self._node.get_logger().info('홈 출발 — 180° Spin 시작 (AMCL 수렴)')
                self._navigator.spin(spin_dist=math.pi)  # 180° 회전

                _spin_tick = 0
                while not self._navigator.isTaskComplete():
                    if self._node._abort_flag:
                        self._navigator.cancelTask()
                        self._node._abort_flag = False
                        self._node.get_logger().info('Spin 중 abort 수신 → RETURNING')
                        return 'aborted'
                    time.sleep(0.1)
                    _spin_tick += 1
                    if _spin_tick % 10 == 0:
                        self._node.publish_status('BUSY')

                if self._navigator.getResult() == TaskResult.SUCCEEDED:
                    self._node.get_logger().info('180° Spin 완료 — 주행 시작')
                else:
                    self._node.get_logger().warn('Spin 실패 — 주행 계속')

            if _needs_glass_via(dest_key):
                glass_entry = _make_pose(self._node.waypoints['glass_entry'])
                glass_exit = _make_pose(self._node.waypoints['glass_exit'])
                self._navigator.goThroughPoses([glass_entry, glass_exit, _make_pose(destination)])
            else:
                self._navigator.goToPose(_make_pose(destination))
        else:
            blackboard['resuming'] = False  # 소비 — 목표 재발행 없이 감시 루프로
            self._node.get_logger().info('GUIDING 재개 — 기존 목표 계속')

        # ── 주행 감시 루프 (신규/재개 공통) ──────────────────────────────
        _tick = 0
        while not self._navigator.isTaskComplete():
            if self._node._abort_flag:
                self._navigator.cancelTask()
                self._node._abort_flag = False
                self._node.get_logger().info('GUIDING: abort → RETURNING')
                return 'aborted'
            if self._node.motion_blocked():
                # pause/사람/접근 — 취소 없이 WAITING(목표 살림). 재개 시 그대로 이어받음
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
            # 도착 안내: 발화 완료까지 대기한 뒤 복귀 시작(발화 중 복귀 방지).
            # 출발(speak_and_wait)과 동일하게 동기화. 멘트는 destination_key로 분기.
            self._node.get_logger().info('도착 안내 발화 — 완료까지 대기')
            self._node.speak_and_wait(_arrival_tts(dest_key))
            return 'succeeded'

        self._node.get_logger().warn(f'목적지 이동 실패: {result}')
        blackboard['failed_from'] = 'GUIDING'
        return 'failed'


class WaitingState(State):
    """정지 대기 상태: pause(관제·traffic)/사람 감지 게이트로 진입.

    진입 시 /motion_hold=true 발행 → Nav2 BT의 MotionHoldCondition이 FollowPath를
    halt(주행 목표는 cancel하지 않고 살림). 게이트(motion_blocked)가 풀리면
    /motion_hold=false 발행 → 같은 목표를 이어서 주행(resuming=True).

    abort(임무중단)가 안내 중(return_to=='GUIDING') 들어오면 살아있는 안내 목표를
    cancel하고 RETURNING으로 방향만 바꾼다(resuming=False) — 게이트가 풀린 뒤 집으로
    새 목표로 출발. abort가 와도 게이트가 켜져 있는 동안은 움직이지 않는다(안전 우선).
    """

    def __init__(self, node, navigator: BasicNavigator):
        super().__init__(outcomes=['resume_guiding', 'resume_returning'])
        self._node = node
        self._navigator = navigator

    def execute(self, blackboard):
        self._node.publish_status('WAITING')
        self._node.publish_motion_hold(True)   # BT FollowPath halt
        self._node.get_logger().info('WAITING: 정지 (pause/사람/접근)')

        aborted = False
        _tick = 0
        while self._node.motion_blocked():
            if self._node._abort_flag:
                self._node._abort_flag = False
                if _bb_get(blackboard, 'return_to') == 'GUIDING':
                    # 안내 중 멈춤 상태에서 임무중단 — 살아있는 안내 목표 취소 후 집으로
                    self._navigator.cancelTask()
                    blackboard['return_to'] = 'RETURNING'
                    aborted = True
                    self._node.get_logger().info('WAITING: abort → RETURNING (안내 목표 취소)')
                # return_to가 이미 RETURNING이면 abort 무시(이미 복귀 중)
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:
                self._node.publish_status('WAITING')
                self._node.publish_motion_hold(True)   # keepalive

        # 게이트 해제 → BT 재개 신호
        self._node.publish_motion_hold(False)
        # abort면 새 home 목표 발행 필요(resuming=False), 정상 재개면 살아있는 목표 이어받음
        blackboard['resuming'] = not aborted
        try:
            return_to = blackboard['return_to']
        except KeyError:
            return_to = 'RETURNING'
        self._node.get_logger().info(
            f'WAITING: 해제 → {return_to} (resuming={not aborted})')
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

        # staging이 있으면 staging까지 Nav2 이동 후 PBVS, 없으면 home으로 직접
        nav_target = waypoints[staging_key] if staging_key in waypoints else waypoints[home_key]
        nav_label  = 'staging' if staging_key in waypoints else '홈(직접)'

        try:
            dest_key = blackboard['destination_key']
        except KeyError:
            dest_key = ''

        # 목표 발행은 일회성 — WAITING 재개(resuming) 시 스킵하고 살아있는 목표 이어받음
        if not _bb_get(blackboard, 'resuming'):
            self._node.get_logger().info(f'RETURNING: {nav_label}으로 이동 중')
            if _needs_glass_via(dest_key):
                glass_entry = _make_pose(waypoints['glass_entry'])
                glass_exit  = _make_pose(waypoints['glass_exit'])
                self._navigator.goThroughPoses([glass_exit, glass_entry, _make_pose(nav_target)])
            else:
                self._navigator.goToPose(_make_pose(nav_target))
        else:
            blackboard['resuming'] = False  # 소비
            self._node.get_logger().info('RETURNING 재개 — 기존 목표 계속')

        _tick = 0
        while not self._navigator.isTaskComplete():
            if self._node.motion_blocked():
                # pause/사람/접근 — 취소 없이 WAITING(목표 살림)
                blackboard['return_to'] = 'RETURNING'
                return 'paused'
            time.sleep(0.1)
            _tick += 1
            if _tick % 10 == 0:
                self._node.publish_status('RETURNING')

        if self._navigator.getResult() == TaskResult.SUCCEEDED:
            self._node.get_logger().info(f'{nav_label} 도착 — PBVS 도킹 시작')
            if self._node.call_home_dock():
                return 'succeeded'
            # Nav2는 staging 도착(위치추정 정상)했으나 PBVS 정밀 도킹 실패 →
            # AMCL 리셋 누락 상태. 자동 진행하지 않고 FAILED로 표면화.
            self._node.get_logger().error('PBVS 홈 도킹 실패')
            blackboard['failed_from'] = 'DOCKING'
            return 'failed'

        self._node.get_logger().warn('홈 이동 실패')
        blackboard['failed_from'] = 'RETURNING'
        return 'failed'
