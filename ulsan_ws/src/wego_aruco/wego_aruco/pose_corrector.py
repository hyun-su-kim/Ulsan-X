"""passive ArUco AMCL corrector — wego_aruco/pose_corrector.py

Normal mode (기본):
  마커 감지 시 full 3D transform으로 robot map pose를 역산하여 /initialpose 발행.
  변환 체인: T_map_base = T_map_marker × inv(T_cam_marker) × inv(T_base_cam)

Calibration mode (calibration_mode:=true):
  로봇이 알려진 map 위치에 정지한 상태에서 마커의 map pose를 측정한다.
  변환 체인: T_map_marker = T_map_base × T_base_cam × T_cam_marker
  calib_samples 프레임 평균 후 markers.yaml 입력값을 출력.
  마커 pose는 xyz + quaternion (6DOF) 으로 저장 — 2D 투영 손실 없음.

  실행 예:
    ros2 run wego_aruco aruco_pose_corrector --ros-args \\
      -p calibration_mode:=true \\
      -p calib_marker_id:=0 \\
      -p calib_x:=0.0 -p calib_y:=0.95 -p calib_yaw:=-1.5708
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
ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
ARUCO_PARAMS.adaptiveThreshWinSizeMin = 3
ARUCO_PARAMS.adaptiveThreshWinSizeMax = 53
ARUCO_PARAMS.adaptiveThreshWinSizeStep = 5
ARUCO_PARAMS.minMarkerPerimeterRate = 0.02
ARUCO_PARAMS.errorCorrectionRate = 0.8


class ArucoPoseCorrector(Node):
    COOLDOWN_SEC = 10.0
    MIN_CONSISTENT = 2

    def __init__(self):
        super().__init__('aruco_pose_corrector')

        self.declare_parameter(
            'markers_file',
            str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml',
        )
        self.declare_parameter('calibration_mode', False)
        self.declare_parameter('calib_marker_id', 0)
        self.declare_parameter('calib_x',      0.0)
        self.declare_parameter('calib_y',      0.0)
        self.declare_parameter('calib_yaw',    0.0)
        self.declare_parameter('calib_samples', 30)

        markers_file      = self.get_parameter('markers_file').get_parameter_value().string_value
        self._calib_mode  = self.get_parameter('calibration_mode').get_parameter_value().bool_value
        self._calib_mid   = self.get_parameter('calib_marker_id').get_parameter_value().integer_value
        self._calib_x     = self.get_parameter('calib_x').get_parameter_value().double_value
        self._calib_y     = self.get_parameter('calib_y').get_parameter_value().double_value
        self._calib_yaw   = self.get_parameter('calib_yaw').get_parameter_value().double_value
        self._calib_n     = self.get_parameter('calib_samples').get_parameter_value().integer_value

        with open(markers_file, 'r') as f:
            data = yaml.safe_load(f)

        self._markers: dict = {}
        for mid, info in data['markers'].items():
            mid_int = int(mid)
            if self._calib_mode:
                if mid_int == self._calib_mid:
                    self._markers[mid_int] = {'size': float(info['size'])}
            else:
                if not info.get('calibrated', False):
                    self.get_logger().info(f'마커 {mid}: calibrated=false — 건너뜀')
                    continue
                self._markers[mid_int] = {
                    'size':   float(info['size']),
                    'map_x':  float(info['map_x']),
                    'map_y':  float(info['map_y']),
                    'map_z':  float(info['map_z']),
                    'map_qx': float(info['map_qx']),
                    'map_qy': float(info['map_qy']),
                    'map_qz': float(info['map_qz']),
                    'map_qw': float(info['map_qw']),
                }

        if self._calib_mode:
            self.get_logger().info(
                f'\n=== 캘리브레이션 모드 ===\n'
                f'  대상 마커 : ID={self._calib_mid}\n'
                f'  로봇 위치 : x={self._calib_x:.4f}  y={self._calib_y:.4f}'
                f'  yaw={math.degrees(self._calib_yaw):.1f}°\n'
                f'  목표 샘플 : {self._calib_n}프레임\n'
                f'========================='
            )
            self._calib_results: list = []
            self._calib_done = False
        else:
            self.get_logger().info(
                f'[보정 모드] 마커 {len(self._markers)}개 로드: {list(self._markers.keys())}'
            )

        self._bridge = CvBridge()
        self._camera_matrix: np.ndarray | None = None
        self._dist_coeffs: np.ndarray | None = None
        self._cam_frame: str = 'camera_color_optical_frame'

        self._tf_buffer   = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._counts: dict[int, int] = {mid: 0 for mid in self._markers}
        self._last_correction_ns: int = 0

        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 1
        )
        self._debug_pub = self.create_publisher(String, '/aruco_debug', 10)
        self.create_subscription(CameraInfo, '/camera/color/camera_info', self._info_cb, 1)
        self.create_subscription(Image,      '/camera/color/image_raw',   self._image_cb, 10)

        self.get_logger().info('aruco_pose_corrector 시작')

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
        if self._calib_mode and self._calib_done:
            return

        if not self._calib_mode:
            now_ns = self.get_clock().now().nanoseconds
            if now_ns - self._last_correction_ns < int(self.COOLDOWN_SEC * 1e9):
                return

        try:
            frame = self._bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().warn(f'imgmsg_to_cv2 실패: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(gray, ARUCO_DICT, parameters=ARUCO_PARAMS)
        detected = set(ids.flatten().tolist()) if ids is not None else set()

        for mid in list(self._counts.keys()):
            if mid not in detected:
                if not self._calib_mode:
                    self._counts[mid] = max(0, self._counts[mid] - 1)
                continue

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
                if not self._calib_mode:
                    self._counts[mid] = max(0, self._counts[mid] - 1)
                continue

            if self._calib_mode:
                self._accumulate_calibration(rvec, tvec)
                break
            else:
                self._counts[mid] += 1
                debug_msg = String()
                debug_msg.data = (
                    f'id={mid}  depth={tvec[2][0]:.3f}m  '
                    f'lateral={tvec[0][0]:.3f}m  '
                    f'count={self._counts[mid]}/{self.MIN_CONSISTENT}'
                )
                self._debug_pub.publish(debug_msg)
                if self._counts[mid] >= self.MIN_CONSISTENT:
                    self._counts[mid] = 0
                    self._last_correction_ns = self.get_clock().now().nanoseconds
                    self._publish_correction(mid, rvec, tvec)
                    break

    # ──────────────────────────────────────────────────────────────────
    def _accumulate_calibration(self, rvec: np.ndarray, tvec: np.ndarray) -> None:
        """캘리브레이션: T_map_marker = T_map_base × T_base_cam × T_cam_marker (full 3D)"""
        try:
            tf = self._tf_buffer.lookup_transform(
                'base_link', self._cam_frame, rclpy.time.Time()
            )
        except Exception as e:
            self.get_logger().warn(f'TF lookup 실패: {e}')
            return

        t, q = tf.transform.translation, tf.transform.rotation
        T_base_cam = self._tf_to_matrix(t.x, t.y, t.z, q.x, q.y, q.z, q.w)

        R_cm, _ = cv2.Rodrigues(rvec)
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = R_cm
        T_cam_marker[:3, 3]  = tvec.flatten()

        T_map_base   = self._yaw_to_matrix(self._calib_x, self._calib_y, self._calib_yaw)
        T_map_marker = T_map_base @ T_base_cam @ T_cam_marker

        mx = T_map_marker[0, 3]
        my = T_map_marker[1, 3]
        mz = T_map_marker[2, 3]
        qw, qx, qy, qz = self._rotation_to_quaternion(T_map_marker[:3, :3])
        myaw = math.atan2(T_map_marker[1, 0], T_map_marker[0, 0])

        self._calib_results.append((mx, my, mz, qx, qy, qz, qw))
        n = len(self._calib_results)
        self.get_logger().info(
            f'샘플 {n}/{self._calib_n}  x={mx:.4f}  y={my:.4f}  z={mz:.4f}'
            f'  yaw={math.degrees(myaw):.2f}°'
        )

        if n >= self._calib_n:
            self._calib_done = True
            self._print_calibration_result()

    def _print_calibration_result(self) -> None:
        xs, ys, zs, qxs, qys, qzs, qws = zip(*self._calib_results)

        mean_x  = sum(xs) / len(xs)
        mean_y  = sum(ys) / len(ys)
        mean_z  = sum(zs) / len(zs)
        std_x   = (sum((x - mean_x) ** 2 for x in xs) / len(xs)) ** 0.5
        std_y   = (sum((y - mean_y) ** 2 for y in ys) / len(ys)) ** 0.5

        # quaternion 평균 후 정규화
        mean_qx = sum(qxs) / len(qxs)
        mean_qy = sum(qys) / len(qys)
        mean_qz = sum(qzs) / len(qzs)
        mean_qw = sum(qws) / len(qws)
        norm = math.sqrt(mean_qx**2 + mean_qy**2 + mean_qz**2 + mean_qw**2)
        mean_qx /= norm; mean_qy /= norm; mean_qz /= norm; mean_qw /= norm

        myaw = math.atan2(
            2.0 * (mean_qw * mean_qz + mean_qx * mean_qy),
            1.0 - 2.0 * (mean_qy**2 + mean_qz**2),
        )

        size = self._markers[self._calib_mid]['size']
        self.get_logger().info(
            f'\n'
            f'======== 캘리브레이션 결과 (ID={self._calib_mid}) ========\n'
            f'  map_x  : {mean_x:.4f}  (std {std_x:.4f})\n'
            f'  map_y  : {mean_y:.4f}  (std {std_y:.4f})\n'
            f'  map_z  : {mean_z:.4f}\n'
            f'  map_qx : {mean_qx:.4f}\n'
            f'  map_qy : {mean_qy:.4f}\n'
            f'  map_qz : {mean_qz:.4f}\n'
            f'  map_qw : {mean_qw:.4f}\n'
            f'  (yaw   : {math.degrees(myaw):.2f}°)\n'
            f'\n'
            f'markers.yaml 에 아래 내용을 입력하세요:\n'
            f'  {self._calib_mid}:\n'
            f'    size: {size:.2f}\n'
            f'    calibrated: true\n'
            f'    map_x:  {mean_x:.4f}\n'
            f'    map_y:  {mean_y:.4f}\n'
            f'    map_z:  {mean_z:.4f}\n'
            f'    map_qx: {mean_qx:.4f}\n'
            f'    map_qy: {mean_qy:.4f}\n'
            f'    map_qz: {mean_qz:.4f}\n'
            f'    map_qw: {mean_qw:.4f}\n'
            f'========================================================='
        )

    # ──────────────────────────────────────────────────────────────────
    def _publish_correction(
        self, marker_id: int, rvec: np.ndarray, tvec: np.ndarray
    ) -> None:
        info = self._markers[marker_id]

        R_cm, _ = cv2.Rodrigues(rvec)
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = R_cm
        T_cam_marker[:3, 3]  = tvec.flatten()

        try:
            tf = self._tf_buffer.lookup_transform(
                'base_link', self._cam_frame, rclpy.time.Time()
            )
        except Exception as e:
            self.get_logger().warn(f'TF lookup 실패 (base_link←{self._cam_frame}): {e}')
            return

        t, q = tf.transform.translation, tf.transform.rotation
        T_base_cam = self._tf_to_matrix(t.x, t.y, t.z, q.x, q.y, q.z, q.w)

        T_map_marker = self._tf_to_matrix(
            info['map_x'], info['map_y'], info['map_z'],
            info['map_qx'], info['map_qy'], info['map_qz'], info['map_qw'],
        )
        T_map_base = T_map_marker @ np.linalg.inv(T_cam_marker) @ np.linalg.inv(T_base_cam)

        robot_x   = T_map_base[0, 3]
        robot_y   = T_map_base[1, 3]
        robot_yaw = math.atan2(T_map_base[1, 0], T_map_base[0, 0])

        msg = PoseWithCovarianceStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x    = robot_x
        msg.pose.pose.position.y    = robot_y
        msg.pose.pose.orientation.z = math.sin(robot_yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(robot_yaw / 2.0)
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
    def _rotation_to_quaternion(R: np.ndarray):
        trace = R[0, 0] + R[1, 1] + R[2, 2]
        if trace > 0:
            s = 2.0 * math.sqrt(trace + 1.0)
            qw = 0.25 * s
            qx = (R[2, 1] - R[1, 2]) / s
            qy = (R[0, 2] - R[2, 0]) / s
            qz = (R[1, 0] - R[0, 1]) / s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            qw = (R[2, 1] - R[1, 2]) / s
            qx = 0.25 * s
            qy = (R[0, 1] + R[1, 0]) / s
            qz = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            qw = (R[0, 2] - R[2, 0]) / s
            qx = (R[0, 1] + R[1, 0]) / s
            qy = 0.25 * s
            qz = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            qw = (R[1, 0] - R[0, 1]) / s
            qx = (R[0, 2] + R[2, 0]) / s
            qy = (R[1, 2] + R[2, 1]) / s
            qz = 0.25 * s
        return qw, qx, qy, qz

    @staticmethod
    def _tf_to_matrix(tx, ty, tz, qx, qy, qz, qw) -> np.ndarray:
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
