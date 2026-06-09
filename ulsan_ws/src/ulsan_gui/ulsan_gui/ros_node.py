import os
import time
import threading
from dataclasses import dataclass

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String, Empty, Bool
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from sensor_msgs.msg import CompressedImage
from nav_msgs.msg import OccupancyGrid
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
try:
    from limo_msgs.msg import LimoStatus as _LimoStatus
    _LIMO_MSGS_OK = True
except ImportError:
    _LIMO_MSGS_OK = False


from PyQt5.QtCore import QObject, pyqtSignal


# 로봇 목록 — 단일 정본. 로봇 추가 시 이 튜플만 수정하면 GUI 전체가 자동 확장
ROBOTS: tuple[str, ...] = ('limo1', 'limo2')

# FastAPI 서버 주소 — 환경변수 FASTAPI_URL로 오버라이드 가능
# 예) export FASTAPI_URL=http://192.168.0.115:8000
FASTAPI_URL: str = os.environ.get('FASTAPI_URL', 'http://localhost:8000')


def robot_label(robot: str) -> str:
    """'limo1' → 'LIMO 1'."""
    if robot.startswith('limo') and robot[4:].isdigit():
        return f'LIMO {robot[4:]}'
    return robot


@dataclass
class RobotState:
    status: str = 'UNKNOWN'
    prev_status: str = ''
    pose: object = None
    dest: str = ''


class GuiSignals(QObject):
    # 로봇별 시그널 — (robot_name, value) 형태로 통합
    sig_status   = pyqtSignal(str, str)         # (robot, status)
    sig_pose     = pyqtSignal(str, object)      # (robot, pose_msg)
    sig_camera   = pyqtSignal(str, bytes, str)  # (robot, data, fmt)
    sig_dest     = pyqtSignal(str, str)         # (robot, dest)
    sig_battery  = pyqtSignal(str, float)       # (robot, voltage)
    sig_connection = pyqtSignal(str, bool)       # (robot, connected) — is_robot_connected 단일 출처
    # 비로봇 시그널
    sig_map      = pyqtSignal(object)
    sig_gui_log  = pyqtSignal(str, str, str)    # (log_type, robot_label, message)


# /map, /amcl_pose 모두 Nav2가 TRANSIENT_LOCAL로 발행 — 구독도 맞춰야 GUI 시작 시점에 관계없이 즉시 수신
_MAP_QOS = QoSProfile(
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)
_AMCL_QOS = QoSProfile(
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)


class RosNode(Node):
    def __init__(self):
        super().__init__('ulsan_gui')

        self.signals = GuiSignals()

        # 로봇별 상태 — 단일 dict
        self.robots: dict[str, RobotState] = {r: RobotState() for r in ROBOTS}
        self.latest_map: OccupancyGrid | None = None
        # 현재 보고 있는(활성) 로봇 — 이 로봇의 카메라 프레임만 처리. None=처리 안 함.
        self._active_camera: str | None = None

        # 노드별 최근 /diagnostics 수신 시각 — is_node_ok() 판정 기준
        # 로봇(limo1/limo2): bridge를 통해 /ROBOT_NAME/diagnostics로 수신
        # domain 5 노드(wego_dispatcher/wego_traffic): /diagnostics에서 name 필드로 구분
        self._diag_recv: dict[str, float] = {r: 0.0 for r in ROBOTS}
        self._diag_recv.update({'wego_dispatcher': 0.0, 'wego_traffic': 0.0})

        # 연결/준비 판정 — 세 개념을 분리(DEC-047):
        #   ① 로봇 연결(physical liveness): /limo_status — 로봇 HW 드라이버(Orin) 발.
        #      behaviour/Nav2(데스크탑 발)와 무관하게 "물리 로봇이 살아있나"만 판정.
        #   ② behaviour 생존: hardware_id 'wego_behaviour' 진단 수신 시각 — 명령(pause/
        #      resume/abort/recover) 수신 주체.
        #   ③ Nav2 준비(navigation/localization): hardware_id 'Nav2' 진단을 status.name별
        #      (lifecycle_manager_navigation / _localization)로 (수신시각, OK) 추적 →
        #      navigation·localization을 독립 판정.
        self._behaviour_recv: dict[str, float] = {r: 0.0 for r in ROBOTS}
        self._nav2_diag: dict[str, dict[str, tuple[float, bool]]] = {r: {} for r in ROBOTS}
        self._limo_status_recv: dict[str, float] = {r: 0.0 for r in ROBOTS}
        # 로봇 측 노드 liveness — person_detect: /person_detected(10Hz) 신선도,
        #   voice: /diagnostics의 hardware_id 'wego_voice' 수신 시각
        self._person_detect_recv: dict[str, float] = {r: 0.0 for r in ROBOTS}
        self._voice_recv: dict[str, float] = {r: 0.0 for r in ROBOTS}

        # 구독 — 로봇별 루프
        for robot in ROBOTS:
            self.create_subscription(
                String, f'/{robot}/robot_status',
                lambda m, r=robot: self._status_cb(r, m), 10,
            )
            self.create_subscription(
                PoseWithCovarianceStamped, f'/{robot}/amcl_pose',
                lambda m, r=robot: self._pose_cb(r, m), _AMCL_QOS,
            )
            self.create_subscription(
                CompressedImage, f'/{robot}/camera/image/compressed',
                lambda m, r=robot: self._camera_cb(r, m), 10,
            )
            self.create_subscription(
                String, f'/{robot}/goal_destination',
                lambda m, r=robot: self._dest_cb(r, m), 10,
            )
            self.create_subscription(
                Bool, f'/{robot}/person_detected',
                lambda m, r=robot: self._person_detected_cb(r, m), 10,
            )
            if _LIMO_MSGS_OK:
                self.create_subscription(
                    _LimoStatus, f'/{robot}/limo_status',
                    lambda m, r=robot: self._battery_cb(r, m), 10,
                )

        # /map 토픽은 transient_local QoS로 구독 (GUI 실행 전 발행된 맵도 수신)
        self.create_subscription(OccupancyGrid, '/map', self._map_cb, _MAP_QOS)

        # 로봇 diagnostics: bridge가 /ROBOT_NAME/diagnostics 로 remap해서 전달
        for robot in ROBOTS:
            self.create_subscription(
                DiagnosticArray, f'/{robot}/diagnostics',
                lambda m, r=robot: self._robot_diag_cb(r, m), 10,
            )
        # domain 5 노드(dispatcher, traffic) diagnostics: 브릿징 없이 직접 수신
        self.create_subscription(DiagnosticArray, '/diagnostics', self._domain5_diag_cb, 10)

        # 발행 — 로봇별 dict
        self._cmd_vel_pubs = {
            r: self.create_publisher(Twist, f'/{r}/cmd_vel', 10) for r in ROBOTS
        }
        self._goal_pubs = {
            r: self.create_publisher(String, f'/{r}/goal_destination', 10) for r in ROBOTS
        }
        self._pause_pubs = {
            r: self.create_publisher(Empty, f'/{r}/pause', 10) for r in ROBOTS
        }
        self._resume_pubs = {
            r: self.create_publisher(Empty, f'/{r}/resume', 10) for r in ROBOTS
        }
        self._abort_pubs = {
            r: self.create_publisher(Empty, f'/{r}/abort', 10) for r in ROBOTS
        }
        self._recover_pubs = {
            r: self.create_publisher(Empty, f'/{r}/recover', 10) for r in ROBOTS
        }

        self.get_logger().info('ulsan_gui ROS 노드 초기화 완료')

    # ── 구독 콜백 ────────────────────────────────────────────────────

    _STATUS_LOG_TYPE = {
        'IDLE': 'system', 'BUSY': 'mission_start',
        'RETURNING': 'mission_complete', 'WAITING': 'waiting',
        'FAILED': 'mission_fail', 'UNKNOWN': 'system',
    }

    def _status_cb(self, robot: str, msg: String) -> None:
        st = self.robots[robot]
        st.status = msg.data
        self.signals.sig_status.emit(robot, msg.data)

        if msg.data != st.prev_status:
            label = robot_label(robot)
            if not st.prev_status:
                log_msg  = f'연결됨 ({msg.data})'
                log_type = 'system'
            else:
                log_msg  = msg.data
                log_type = self._STATUS_LOG_TYPE.get(msg.data, 'system')
            self.signals.sig_gui_log.emit(log_type, label, log_msg)
            st.prev_status = msg.data

    def _pose_cb(self, robot: str, msg: PoseWithCovarianceStamped) -> None:
        st = self.robots[robot]
        st.pose = msg
        self.signals.sig_pose.emit(robot, msg)

    def _map_cb(self, msg: OccupancyGrid) -> None:
        self.latest_map = msg
        self.signals.sig_map.emit(msg)

    def _camera_cb(self, robot: str, msg: CompressedImage) -> None:
        # 활성(현재 보고 있는) 로봇의 프레임만 emit — 나머지는 디코드/표시 전에 즉시 폐기.
        # robot_view의 압축 해제+스케일이 큰 비용이라, 안 보는 로봇/뷰에서 헛돌지 않게 한다.
        if robot != self._active_camera:
            return
        self.signals.sig_camera.emit(robot, bytes(msg.data), msg.format)

    def _dest_cb(self, robot: str, msg: String) -> None:
        self.robots[robot].dest = msg.data
        self.signals.sig_dest.emit(robot, msg.data)

    def _battery_cb(self, robot: str, msg) -> None:
        # /limo_status = 로봇 HW 드라이버 발 — 로봇 '연결' 판정의 하트비트(DEC-047)
        self._limo_status_recv[robot] = time.time()
        self.signals.sig_battery.emit(robot, msg.battery_voltage)

    def _person_detected_cb(self, robot: str, msg: Bool) -> None:
        # /person_detected는 감지 여부와 무관하게 10Hz로 발행 → 수신 자체가 노드 liveness
        self._person_detect_recv[robot] = time.time()

    def _robot_diag_cb(self, robot: str, msg: DiagnosticArray) -> None:
        # /{robot}/diagnostics 에는 behaviour와 Nav2 lifecycle_manager(navigation/
        # localization)가 같은 토픽으로 함께 실려 옴 → hardware_id로 구분해 기록
        now = time.time()
        self._diag_recv[robot] = now
        for st in msg.status:
            if st.hardware_id == 'wego_behaviour':
                self._behaviour_recv[robot] = now
            elif st.hardware_id == 'wego_voice':
                self._voice_recv[robot] = now
            elif st.hardware_id == 'Nav2':
                # status.name = 'lifecycle_manager_navigation: Nav2 Health' 등 매니저별 구분
                self._nav2_diag[robot][st.name] = (now, st.level == DiagnosticStatus.OK)

    def _domain5_diag_cb(self, msg: DiagnosticArray) -> None:
        # 여러 노드가 /diagnostics 하나에 발행 — hardware_id 필드로 노드 구분
        # (status.name은 'hardware_id: task_name' 형식이므로 hardware_id 사용)
        now = time.time()
        for status in msg.status:
            if status.hardware_id in self._diag_recv:
                self._diag_recv[status.hardware_id] = now

    # ── 발행 ─────────────────────────────────────────────────────────

    def publish_cmd_vel(self, robot: str, linear_x: float, angular_z: float) -> None:
        msg = Twist()
        msg.linear.x  = linear_x
        msg.angular.z = angular_z
        self._cmd_vel_pubs[robot].publish(msg)

    def publish_pause(self, robot: str) -> None:
        self._pause_pubs[robot].publish(Empty())

    def publish_resume(self, robot: str) -> None:
        self._resume_pubs[robot].publish(Empty())

    def publish_abort(self, robot: str) -> None:
        self._abort_pubs[robot].publish(Empty())

    def publish_recover(self, robot: str) -> None:
        # FAILED 상태 탈출 — behaviour_node가 home 좌표 /initialpose 발행(AMCL 리셋) → IDLE (DEC-044)
        self._recover_pubs[robot].publish(Empty())

    def set_active_camera(self, robot: str | None) -> None:
        # RobotView가 현재 보는 로봇(탭)을 통지 — None이면 로봇 뷰를 벗어난 것 → 카메라 처리 중단.
        # 단순 속성 대입이라 executor 스레드의 _camera_cb 읽기와 GIL 하에 안전.
        self._active_camera = robot

    # ── 유틸 ─────────────────────────────────────────────────────────

    def is_node_ok(self, key: str, timeout_sec: float = 5.0) -> bool:
        # /diagnostics 수신 시각 기준 — key: domain5 노드명(wego_dispatcher/wego_traffic)
        return (time.time() - self._diag_recv.get(key, 0.0)) < timeout_sec

    def is_robot_connected(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # 로봇 '연결'(physical liveness) = 로봇 HW 드라이버(/limo_status) 하트비트 신선도.
        # Nav2(navigation/localization)·behaviour는 데스크탑 발이라 로봇 물리 생존과 무관 →
        # 연결 판정에서 분리(DEC-047). 도킹 중 CPU 스파이크로 Nav2 진단이 굶어도, FAILED로
        # navigation이 죽어도 로봇 자체가 살아있으면 '연결'을 유지한다.
        return (time.time() - self._limo_status_recv.get(robot, 0.0)) < timeout_sec

    def is_behaviour_alive(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # 명령 수신 주체(FSM) 생존 — pause/resume/abort/recover의 필수 전제
        return (time.time() - self._behaviour_recv.get(robot, 0.0)) < timeout_sec

    def is_person_detect_alive(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # 사람 감지 노드 생존 — /person_detected(10Hz) 신선도. 죽으면 안전정지 무력화.
        return (time.time() - self._person_detect_recv.get(robot, 0.0)) < timeout_sec

    def is_voice_alive(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # 음성(TTS) 노드 생존 — wego_voice diagnostics 신선도. 죽으면 안내 발화 없음.
        return (time.time() - self._voice_recv.get(robot, 0.0)) < timeout_sec

    def _lifecycle_ready(self, robot: str, key: str, timeout_sec: float) -> bool:
        # status.name 예) 'lifecycle_manager_navigation: Nav2 Health' → key('navigation'/
        # 'localization') 부분 일치로 매니저 구분. 해당 매니저 진단이 최근 수신 + 전부 OK일 때만 준비.
        now = time.time()
        entries = [
            (recv, ok) for name, (recv, ok) in self._nav2_diag.get(robot, {}).items()
            if key in name
        ]
        if not entries:
            return False
        return all((now - recv) < timeout_sec and ok for recv, ok in entries)

    def is_navigation_ready(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # planner/controller/bt_navigator 등 주행 스택 active — pause/resume/abort에 필요
        return self._lifecycle_ready(robot, 'navigation', timeout_sec)

    def is_localization_ready(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # map_server/amcl active — recover의 /initialpose 리셋이 먹으려면 필수(navigation 무관)
        return self._lifecycle_ready(robot, 'localization', timeout_sec)


class RosSpinThread(threading.Thread):
    def __init__(self, node: RosNode):
        super().__init__(daemon=True)
        self._node     = node
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(node)

    def run(self) -> None:
        try:
            self._executor.spin()
        except Exception:
            pass

    def stop(self) -> None:
        self._executor.shutdown()
