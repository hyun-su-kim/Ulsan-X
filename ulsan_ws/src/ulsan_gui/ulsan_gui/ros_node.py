import math
import time
import threading

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


class GuiSignals(QObject):
    sig_status_1  = pyqtSignal(str)
    sig_status_2  = pyqtSignal(str)
    sig_pose_1    = pyqtSignal(object)
    sig_pose_2    = pyqtSignal(object)
    sig_map       = pyqtSignal(object)
    sig_camera_1  = pyqtSignal(bytes, str)
    sig_camera_2  = pyqtSignal(bytes, str)
    sig_dest_1    = pyqtSignal(str)    # 현재 목적지 (limo1)
    sig_dest_2    = pyqtSignal(str)    # 현재 목적지 (limo2)
    sig_battery_1 = pyqtSignal(float)  # 배터리 전압 (limo1)
    sig_battery_2 = pyqtSignal(float)  # 배터리 전압 (limo2)


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

        self.latest_status: dict[str, str]    = {'limo1': 'UNKNOWN', 'limo2': 'UNKNOWN'}
        self.latest_pose:   dict[str, object] = {'limo1': None,      'limo2': None}
        self.latest_dest:   dict[str, str]    = {'limo1': '',        'limo2': ''}
        self.latest_map:    OccupancyGrid | None = None
        self._last_recv:    dict[str, float]  = {'limo1': 0.0,       'limo2': 0.0}

        # 구독
        self.create_subscription(String, '/limo1/robot_status',
                                 lambda m: self._status_cb('limo1', m), 10)
        self.create_subscription(String, '/limo2/robot_status',
                                 lambda m: self._status_cb('limo2', m), 10)
        self.create_subscription(PoseWithCovarianceStamped, '/limo1/amcl_pose',
                                 lambda m: self._pose_cb('limo1', m), 10)
        self.create_subscription(PoseWithCovarianceStamped, '/limo2/amcl_pose',
                                 lambda m: self._pose_cb('limo2', m), 10)
        # transient_local QoS로 맵 구독 (GUI 실행 전 발행된 맵도 수신)
        self.create_subscription(OccupancyGrid, '/map', self._map_cb, _MAP_QOS)
        self.create_subscription(CompressedImage, '/limo1/camera/image/compressed',
                                 lambda m: self._camera_cb('limo1', m), 10)
        self.create_subscription(CompressedImage, '/limo2/camera/image/compressed',
                                 lambda m: self._camera_cb('limo2', m), 10)
        # 목적지 구독 (dispatcher 및 GUI 발행 모두 수신)
        self.create_subscription(String, '/limo1/goal_destination',
                                 lambda m: self._dest_cb('limo1', m), 10)
        self.create_subscription(String, '/limo2/goal_destination',
                                 lambda m: self._dest_cb('limo2', m), 10)
        if _LIMO_MSGS_OK:
            self.create_subscription(_LimoStatus, '/limo1/limo_status',
                                     lambda m: self._battery_cb('limo1', m), 10)
            self.create_subscription(_LimoStatus, '/limo2/limo_status',
                                     lambda m: self._battery_cb('limo2', m), 10)

        # 발행
        self._cmd_vel_pubs = {
            'limo1': self.create_publisher(Twist, '/limo1/cmd_vel', 10),
            'limo2': self.create_publisher(Twist, '/limo2/cmd_vel', 10),
        }
        self._goal_pubs = {
            'limo1': self.create_publisher(String, '/limo1/goal_destination', 10),
            'limo2': self.create_publisher(String, '/limo2/goal_destination', 10),
        }
        self._pause_pubs = {
            'limo1': self.create_publisher(Empty, '/limo1/pause', 10),
            'limo2': self.create_publisher(Empty, '/limo2/pause', 10),
        }
        self._resume_pubs = {
            'limo1': self.create_publisher(Empty, '/limo1/resume', 10),
            'limo2': self.create_publisher(Empty, '/limo2/resume', 10),
        }

        self.get_logger().info('ulsan_gui ROS 노드 초기화 완료')

    # ── 구독 콜백 ────────────────────────────────────────────────────

    def _status_cb(self, robot: str, msg: String) -> None:
        self.latest_status[robot] = msg.data
        self._last_recv[robot] = time.time()
        (self.signals.sig_status_1 if robot == 'limo1' else self.signals.sig_status_2).emit(msg.data)

    def _pose_cb(self, robot: str, msg: PoseWithCovarianceStamped) -> None:
        self.latest_pose[robot] = msg
        self._last_recv[robot] = time.time()
        (self.signals.sig_pose_1 if robot == 'limo1' else self.signals.sig_pose_2).emit(msg)

    def _map_cb(self, msg: OccupancyGrid) -> None:
        self.latest_map = msg
        self.signals.sig_map.emit(msg)

    def _camera_cb(self, robot: str, msg: CompressedImage) -> None:
        sig = self.signals.sig_camera_1 if robot == 'limo1' else self.signals.sig_camera_2
        sig.emit(bytes(msg.data), msg.format)

    def _dest_cb(self, robot: str, msg: String) -> None:
        self.latest_dest[robot] = msg.data
        (self.signals.sig_dest_1 if robot == 'limo1' else self.signals.sig_dest_2).emit(msg.data)

    def _battery_cb(self, robot: str, msg) -> None:
        sig = self.signals.sig_battery_1 if robot == 'limo1' else self.signals.sig_battery_2
        sig.emit(msg.battery_voltage)

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

    # ── 유틸 ─────────────────────────────────────────────────────────

    def is_connected(self, robot: str, timeout_sec: float = 3.0) -> bool:
        return (time.time() - self._last_recv[robot]) < timeout_sec

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
