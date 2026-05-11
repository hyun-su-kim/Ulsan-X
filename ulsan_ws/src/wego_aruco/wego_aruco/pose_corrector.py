"""passive ArUco AMCL corrector — wego_aruco/pose_corrector.py

마커를 감지할 때마다 full 3D transform으로 robot map pose를 역산하여
/initialpose를 발행한다. visual servoing 없이 주행 중 자동 보정.

변환 체인:
  T_map_base = T_map_marker × inv(T_cam_marker) × T_cam_base

  - T_cam_marker : solvePnP 결과 (카메라 기준 마커 위치)
  - T_cam_base   : TF lookup (camera_optical → base_link 역방향)
  - T_map_marker : markers.yaml의 map_x / map_y / map_yaw
"""

import math

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener


ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
ARUCO_PARAMS.adaptiveThreshWinSizeMin = 3
ARUCO_PARAMS.adaptiveThreshWinSizeMax = 53
ARUCO_PARAMS.adaptiveThreshWinSizeStep = 5
ARUCO_PARAMS.minMarkerPerimeterRate = 0.02
ARUCO_PARAMS.errorCorrectionRate = 0.8
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)


class ArucoPoseCorrector(Node):
    COOLDOWN_SEC = 10.0  # 보정 후 재보정 최소 간격 (s)
    MIN_CONSISTENT = 2   # 연속 감지 횟수 조건 (노이즈 제거)

    def __init__(self):
        super().__init__('aruco_pose_corrector')

        self.declare_parameter(
            'markers_file',
            str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml',
        )
        markers_file = (
            self.get_parameter('markers_file').get_parameter_value().string_value
        )

        with open(markers_file, 'r') as f:
            data = yaml.safe_load(f)

        # map 좌표가 설정된 마커만 로드 (map_x=0.0, map_y=0.0은 미측정으로 간주)
        self._markers: dict = {}
        for mid, info in data['markers'].items():
            mx = float(info.get('map_x', 0.0))
            my = float(info.get('map_y', 0.0))
            myaw = float(info.get('map_yaw', 0.0))
            if mx == 0.0 and my == 0.0:
                self.get_logger().info(f'마커 {mid}: map 좌표 미측정 — 건너뜀')
                continue
            self._markers[int(mid)] = {
                'size': float(info['size']),
                'map_x': mx,
                'map_y': my,
                'map_yaw': myaw,
            }

        self.get_logger().info(
            f'보정 마커 {len(self._markers)}개 로드: {list(self._markers.keys())}'
        )

        self._bridge = CvBridge()
        self._camera_matrix: np.ndarray | None = None
        self._dist_coeffs: np.ndarray | None = None
        self._cam_frame: str = 'camera_color_optical_frame'  # CameraInfo header로 덮어씀

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        # {marker_id: 연속 감지 횟수}
        self._counts: dict[int, int] = {mid: 0 for mid in self._markers}
        self._last_correction_ns: int = 0

        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 1
        )
        self._debug_pub = self.create_publisher(String, '/aruco_debug', 10)
        self.create_subscription(
            CameraInfo, '/camera/color/camera_info', self._info_cb, 1
        )
        self.create_subscription(
            Image, '/camera/color/image_raw', self._image_cb, 10
        )

        self.get_logger().info('passive pose corrector 시작')

    # ──────────────────────────────────────────────────────────────────
    def _info_cb(self, msg: CameraInfo) -> None:
        if self._camera_matrix is not None:
            return
        k = msg.k
        self._camera_matrix = np.array(
            [[k[0], k[1], k[2]],
             [k[3], k[4], k[5]],
             [k[6], k[7], k[8]]], dtype=np.float64
        )
        self._dist_coeffs = np.array(msg.d, dtype=np.float64)
        if msg.header.frame_id:
            self._cam_frame = msg.header.frame_id
        self.get_logger().info(f'카메라 파라미터 수신 (frame: {self._cam_frame})')

    def _image_cb(self, msg: Image) -> None:
        if self._camera_matrix is None:
            return

        now_ns = self.get_clock().now().nanoseconds
        cooldown_ns = int(self.COOLDOWN_SEC * 1e9)
        if now_ns - self._last_correction_ns < cooldown_ns:
            return

        try:
            frame = self._bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().warn(f'imgmsg_to_cv2 실패: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = DETECTOR.detectMarkers(gray)

        detected = set(ids.flatten().tolist()) if ids is not None else set()

        for mid in list(self._counts.keys()):
            if mid not in detected:
                self._counts[mid] = max(0, self._counts[mid] - 1)
                continue

            # solvePnP
            idx = list(ids.flatten()).index(mid)
            half = self._markers[mid]['size'] / 2.0
            obj_pts = np.array([
                [-half,  half, 0.0],
                [ half,  half, 0.0],
                [ half, -half, 0.0],
                [-half, -half, 0.0],
            ], dtype=np.float32)
            img_pts = corners[idx][0].astype(np.float32)
            ret, rvec, tvec = cv2.solvePnP(
                obj_pts, img_pts,
                self._camera_matrix, self._dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE,
            )
            if not ret:
                self._counts[mid] = max(0, self._counts[mid] - 1)
                continue

            self._counts[mid] += 1
            self.get_logger().debug(
                f'마커 {mid} 감지 ({self._counts[mid]}/{self.MIN_CONSISTENT}) '
                f'depth={tvec[2][0]:.2f}m'
            )
            debug_msg = String()
            debug_msg.data = (
                f'id={mid}  depth={tvec[2][0]:.3f}m  '
                f'lateral={tvec[0][0]:.3f}m  '
                f'count={self._counts[mid]}/{self.MIN_CONSISTENT}'
            )
            self._debug_pub.publish(debug_msg)

            if self._counts[mid] >= self.MIN_CONSISTENT:
                self._counts[mid] = 0
                self._last_correction_ns = now_ns
                self._publish_correction(mid, rvec, tvec)
                break  # 프레임 당 최대 1회 보정

    # ──────────────────────────────────────────────────────────────────
    def _publish_correction(
        self, marker_id: int, rvec: np.ndarray, tvec: np.ndarray
    ) -> None:
        """마커 pose → robot map pose 역산 → /initialpose 발행."""
        info = self._markers[marker_id]

        # T_cam_marker : solvePnP 결과 (카메라 기준 마커 위치)
        R_cm, _ = cv2.Rodrigues(rvec)
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = R_cm
        T_cam_marker[:3, 3] = tvec.flatten()

        # T_marker_cam = inv(T_cam_marker)
        T_marker_cam = np.linalg.inv(T_cam_marker)

        # T_cam_base : camera_optical → base_link (lookup_transform은 source→target)
        # lookup_transform(target='base_link', source=cam_frame) 는
        # cam_frame 좌표를 base_link 좌표로 변환 — 즉 T_base_cam.
        # 우리가 필요한 것은 T_cam_base = inv(T_base_cam) 이다.
        try:
            tf = self._tf_buffer.lookup_transform(
                'base_link', self._cam_frame, rclpy.time.Time()
            )
        except Exception as e:
            self.get_logger().warn(f'TF lookup 실패 (base_link←{self._cam_frame}): {e}')
            return

        t = tf.transform.translation
        q = tf.transform.rotation
        T_base_cam = self._tf_to_matrix(t.x, t.y, t.z, q.x, q.y, q.z, q.w)
        T_cam_base = np.linalg.inv(T_base_cam)

        # T_map_marker : markers.yaml map pose
        T_map_marker = self._yaw_to_matrix(info['map_x'], info['map_y'], info['map_yaw'])

        # T_map_base = T_map_marker × T_marker_cam × T_cam_base
        T_map_base = T_map_marker @ T_marker_cam @ T_cam_base

        robot_x = T_map_base[0, 3]
        robot_y = T_map_base[1, 3]
        robot_yaw = math.atan2(T_map_base[1, 0], T_map_base[0, 0])

        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = robot_x
        msg.pose.pose.position.y = robot_y
        msg.pose.pose.orientation.z = math.sin(robot_yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(robot_yaw / 2.0)
        # 위치 0.1m², yaw 0.1rad² — AMCL 파티클 초기화 범위
        msg.pose.covariance[0]  = 0.10
        msg.pose.covariance[7]  = 0.10
        msg.pose.covariance[35] = 0.10

        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f'[마커 {marker_id}] AMCL 보정 → '
            f'x={robot_x:.3f} y={robot_y:.3f} yaw={math.degrees(robot_yaw):.1f}°'
        )

    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _tf_to_matrix(tx, ty, tz, qx, qy, qz, qw) -> np.ndarray:
        """quaternion + translation → 4×4 homogeneous matrix."""
        R = np.array([
            [1 - 2*(qy**2 + qz**2),  2*(qx*qy - qz*qw),  2*(qx*qz + qy*qw)],
            [2*(qx*qy + qz*qw),  1 - 2*(qx**2 + qz**2),  2*(qy*qz - qx*qw)],
            [2*(qx*qz - qy*qw),  2*(qy*qz + qx*qw),  1 - 2*(qx**2 + qy**2)],
        ])
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [tx, ty, tz]
        return T

    @staticmethod
    def _yaw_to_matrix(x: float, y: float, yaw: float) -> np.ndarray:
        """2D pose → 4×4 homogeneous matrix (z=0 평면)."""
        T = np.eye(4)
        c, s = math.cos(yaw), math.sin(yaw)
        T[0, 0], T[0, 1] = c, -s
        T[1, 0], T[1, 1] = s,  c
        T[0, 3], T[1, 3] = x,  y
        return T


def main(args=None):
    rclpy.init(args=args)
    node = ArucoPoseCorrector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
