import math
import time
import threading
from dataclasses import dataclass

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String, Empty
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from sensor_msgs.msg import CompressedImage
from nav_msgs.msg import OccupancyGrid
try:
    from limo_msgs.msg import LimoStatus as _LimoStatus
    _LIMO_MSGS_OK = True
except ImportError:
    _LIMO_MSGS_OK = False


from PyQt5.QtCore import QObject, pyqtSignal


# 로봇 목록 — 단일 정본. 로봇 추가 시 이 튜플만 수정하면 GUI 전체가 자동 확장
ROBOTS: tuple[str, ...] = ('limo1', 'limo2')


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
    last_recv: float = 0.0
    last_status_recv: float = 0.0  # robot_status 수신 시각 — 연결 판정 전용


class GuiSignals(QObject):
    # 로봇별 시그널 — (robot_name, value) 형태로 통합
    sig_status   = pyqtSignal(str, str)         # (robot, status)
    sig_pose     = pyqtSignal(str, object)      # (robot, pose_msg)
    sig_camera   = pyqtSignal(str, bytes, str)  # (robot, data, fmt)
    sig_dest     = pyqtSignal(str, str)         # (robot, dest)
    sig_battery  = pyqtSignal(str, float)       # (robot, voltage)
    # 비로봇 시그널
    sig_map      = pyqtSignal(object)
    sig_gui_log  = pyqtSignal(str, str, str)    # (log_type, robot_label, message)


# /map 토픽은 transient_local (latched)로 발행되므로 구독도 맞춰야 함
_MAP_QOS = QoSProfile(
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

        # 구독 — 로봇별 루프
        for robot in ROBOTS:
            self.create_subscription(
                String, f'/{robot}/robot_status',
                lambda m, r=robot: self._status_cb(r, m), 10,
            )
            self.create_subscription(
                PoseWithCovarianceStamped, f'/{robot}/amcl_pose',
                lambda m, r=robot: self._pose_cb(r, m), 10,
            )
            self.create_subscription(
                CompressedImage, f'/{robot}/camera/image/compressed',
                lambda m, r=robot: self._camera_cb(r, m), 10,
            )
            self.create_subscription(
                String, f'/{robot}/goal_destination',
                lambda m, r=robot: self._dest_cb(r, m), 10,
            )
            if _LIMO_MSGS_OK:
                self.create_subscription(
                    _LimoStatus, f'/{robot}/limo_status',
                    lambda m, r=robot: self._battery_cb(r, m), 10,
                )

        # /map 토픽은 transient_local QoS로 구독 (GUI 실행 전 발행된 맵도 수신)
        self.create_subscription(OccupancyGrid, '/map', self._map_cb, _MAP_QOS)

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
        now = time.time()
        st.last_recv = now
        st.last_status_recv = now
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
        st.last_recv = time.time()
        self.signals.sig_pose.emit(robot, msg)

    def _map_cb(self, msg: OccupancyGrid) -> None:
        self.latest_map = msg
        self.signals.sig_map.emit(msg)

    def _camera_cb(self, robot: str, msg: CompressedImage) -> None:
        self.signals.sig_camera.emit(robot, bytes(msg.data), msg.format)

    def _dest_cb(self, robot: str, msg: String) -> None:
        self.robots[robot].dest = msg.data
        self.signals.sig_dest.emit(robot, msg.data)

    def _battery_cb(self, robot: str, msg) -> None:
        self.signals.sig_battery.emit(robot, msg.battery_voltage)

    # ── 발행 ─────────────────────────────────────────────────────────

    def publish_cmd_vel(self, robot: str, linear_x: float, angular_z: float) -> None:
        msg = Twist()
        msg.linear.x  = linear_x
        msg.angular.z = angular_z
        self._cmd_vel_pubs[robot].publish(msg)

    def publish_goal(self, robot: str, destination_key: str) -> None:
        msg = String()
        msg.data = destination_key
        self._goal_pubs[robot].publish(msg)

    def publish_pause(self, robot: str) -> None:
        self._pause_pubs[robot].publish(Empty())

    def publish_resume(self, robot: str) -> None:
        self._resume_pubs[robot].publish(Empty())

    def publish_abort(self, robot: str) -> None:
        self._abort_pubs[robot].publish(Empty())

    # ── 유틸 ─────────────────────────────────────────────────────────

    def is_connected(self, robot: str, timeout_sec: float = 5.0) -> bool:
        # amcl_pose가 아닌 robot_status 기준으로 판정 — AMCL은 정지 중 퍼블리시 중단하므로 제외
        return (time.time() - self.robots[robot].last_status_recv) < timeout_sec

    @staticmethod
    def pose_to_xyyaw(pose_msg: PoseWithCovarianceStamped) -> tuple[float, float, float]:
        p = pose_msg.pose.pose
        q = p.orientation
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y ** 2 + q.z ** 2)
        )
        return p.position.x, p.position.y, yaw


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
