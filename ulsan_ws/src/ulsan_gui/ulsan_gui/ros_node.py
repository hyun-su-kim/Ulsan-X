import json
import math
import time
import threading

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from sensor_msgs.msg import CompressedImage
from nav_msgs.msg import OccupancyGrid

from PyQt5.QtCore import QObject, pyqtSignal

from wego_msgs.srv import WaypointCRUD


class GuiSignals(QObject):
    """Qt 시그널 전용 객체 — Node와 분리하여 MRO 충돌 방지."""
    sig_status_1 = pyqtSignal(str)
    sig_status_2 = pyqtSignal(str)
    sig_pose_1   = pyqtSignal(object)
    sig_pose_2   = pyqtSignal(object)
    sig_map      = pyqtSignal(object)
    sig_camera_1 = pyqtSignal(bytes, str)
    sig_camera_2 = pyqtSignal(bytes, str)


class RosNode(Node):
    def __init__(self):
        super().__init__('ulsan_gui')

        self.signals = GuiSignals()

        # 최신값 캐시
        self.latest_status: dict[str, str]    = {'limo1': 'UNKNOWN', 'limo2': 'UNKNOWN'}
        self.latest_pose:   dict[str, object] = {'limo1': None,      'limo2': None}
        self.latest_map:    OccupancyGrid | None = None
        self._last_recv:    dict[str, float]  = {'limo1': 0.0,       'limo2': 0.0}

        # 구독
        self.create_subscription(String, '/limo1/robot_status', lambda m: self._status_cb('limo1', m), 10)
        self.create_subscription(String, '/limo2/robot_status', lambda m: self._status_cb('limo2', m), 10)
        self.create_subscription(PoseWithCovarianceStamped, '/limo1/amcl_pose', lambda m: self._pose_cb('limo1', m), 10)
        self.create_subscription(PoseWithCovarianceStamped, '/limo2/amcl_pose', lambda m: self._pose_cb('limo2', m), 10)
        self.create_subscription(OccupancyGrid, '/map', self._map_cb, 1)
        self.create_subscription(CompressedImage, '/limo1/camera/image/compressed', lambda m: self._camera_cb('limo1', m), 10)
        self.create_subscription(CompressedImage, '/limo2/camera/image/compressed', lambda m: self._camera_cb('limo2', m), 10)

        # 발행
        self._cmd_vel_pubs = {
            'limo1': self.create_publisher(Twist, '/limo1/cmd_vel', 10),
            'limo2': self.create_publisher(Twist, '/limo2/cmd_vel', 10),
        }
        self._goal_pubs = {
            'limo1': self.create_publisher(String, '/limo1/goal_destination', 10),
            'limo2': self.create_publisher(String, '/limo2/goal_destination', 10),
        }

        # Waypoint CRUD 서비스 클라이언트
        self._wp_clients = {
            'limo1': self.create_client(WaypointCRUD, '/waypoint_crud'),
            'limo2': self.create_client(WaypointCRUD, '/waypoint_crud'),
        }

        self.get_logger().info('ulsan_gui ROS 노드 초기화 완료')

    # ── 구독 콜백 ────────────────────────────────────────────────────

    def _status_cb(self, robot: str, msg: String) -> None:
        self.latest_status[robot] = msg.data
        self._last_recv[robot] = time.time()
        if robot == 'limo1':
            self.signals.sig_status_1.emit(msg.data)
        else:
            self.signals.sig_status_2.emit(msg.data)

    def _pose_cb(self, robot: str, msg: PoseWithCovarianceStamped) -> None:
        self.latest_pose[robot] = msg
        self._last_recv[robot] = time.time()
        if robot == 'limo1':
            self.signals.sig_pose_1.emit(msg)
        else:
            self.signals.sig_pose_2.emit(msg)

    def _map_cb(self, msg: OccupancyGrid) -> None:
        self.latest_map = msg
        self.signals.sig_map.emit(msg)

    def _camera_cb(self, robot: str, msg: CompressedImage) -> None:
        if robot == 'limo1':
            self.signals.sig_camera_1.emit(bytes(msg.data), msg.format)
        else:
            self.signals.sig_camera_2.emit(bytes(msg.data), msg.format)

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

    # ── Waypoint CRUD ────────────────────────────────────────────────

    def call_waypoint_crud(self, action: str, key: str = '', label: str = '',
                           x: float = 0.0, y: float = 0.0, yaw: float = 0.0,
                           robot: str = 'limo1') -> dict:
        client = self._wp_clients[robot]
        if not client.wait_for_service(timeout_sec=0.3):
            return {'success': False, 'message': '서비스 미연결', 'waypoints_json': '{}'}

        req = WaypointCRUD.Request()
        req.action = action
        req.key    = key
        req.label  = label
        req.x      = x
        req.y      = y
        req.yaw    = yaw

        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=3.0)

        if future.result() is None:
            return {'success': False, 'message': '서비스 응답 없음', 'waypoints_json': '{}'}

        res = future.result()
        return {
            'success':        res.success,
            'message':        res.message,
            'waypoints_json': res.waypoints_json,
        }

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
