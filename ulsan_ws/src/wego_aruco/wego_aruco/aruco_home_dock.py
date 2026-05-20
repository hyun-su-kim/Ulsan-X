"""aruco_home_dock.py — 홈 정밀 정차 IBVS 서비스 노드 (3DOF)

3DOF 제어:
  depth   → target_dist  : linear.x   = Kp_v × (depth - target_dist)
  lateral → 0            : angular.z  = -Kp_w × lateral
  yaw     → 0            : angular.z += -Kp_yaw × yaw_error

yaw_error 추출:
  R_cm = cv2.Rodrigues(rvec)
  마커 법선(마커 z축)을 카메라 좌표계로 변환: n_cam = R_cm[:, 2]
  yaw_error = atan2(n_cam[0], -n_cam[2])
  → 0이면 로봇이 마커에 수직 정렬

안전장치:
  - 후진(depth < target_dist) 시 angular_z = 0 (FOV 이탈 방지)
  - 마커 미감지 즉시 정지

정차 후:
  - 마커 절대 좌표로 T_map_base 역산 → /initialpose 발행 (AMCL 리셋)
  - 변환 체인: T_map_base = T_map_marker × inv(T_cam_marker) × inv(T_base_cam)
"""

import math
import time
import threading

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener


ARUCO_DICT   = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
ARUCO_PARAMS.adaptiveThreshWinSizeMin    = 3
ARUCO_PARAMS.adaptiveThreshWinSizeMax    = 53
ARUCO_PARAMS.adaptiveThreshWinSizeStep   = 5
ARUCO_PARAMS.minMarkerPerimeterRate      = 0.02
ARUCO_PARAMS.errorCorrectionRate         = 0.8


class ArucoHomeDock(Node):

    def __init__(self):
        super().__init__('aruco_home_dock')

        self.declare_parameter('home_key',              'home_robot1')
        self.declare_parameter('target_dist',           0.5)
        self.declare_parameter('kp_v',                  0.3)
        self.declare_parameter('kp_w',                  0.5)
        self.declare_parameter('kp_yaw',                0.5)
        self.declare_parameter('max_linear',            0.15)
        self.declare_parameter('max_angular',           0.3)
        self.declare_parameter('depth_tol',             0.03)
        self.declare_parameter('lateral_tol',           0.01)
        self.declare_parameter('yaw_tol',               0.05)
        self.declare_parameter('timeout_sec',           30.0)
        self.declare_parameter('no_marker_timeout_sec', 5.0)

        home_key           = self.get_parameter('home_key').get_parameter_value().string_value
        self._target_dist  = self.get_parameter('target_dist').get_parameter_value().double_value
        self._kp_v         = self.get_parameter('kp_v').get_parameter_value().double_value
        self._kp_w         = self.get_parameter('kp_w').get_parameter_value().double_value
        self._kp_yaw       = self.get_parameter('kp_yaw').get_parameter_value().double_value
        self._max_linear   = self.get_parameter('max_linear').get_parameter_value().double_value
        self._max_angular  = self.get_parameter('max_angular').get_parameter_value().double_value
        self._depth_tol    = self.get_parameter('depth_tol').get_parameter_value().double_value
        self._lateral_tol  = self.get_parameter('lateral_tol').get_parameter_value().double_value
        self._yaw_tol      = self.get_parameter('yaw_tol').get_parameter_value().double_value
        self._timeout      = self.get_parameter('timeout_sec').get_parameter_value().double_value
        self._no_marker_to = self.get_parameter('no_marker_timeout_sec').get_parameter_value().double_value

        markers_file = str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml'
        with open(markers_file) as f:
            data = yaml.safe_load(f)

        home_marker_map   = data.get('home_marker', {})
        self._marker_id   = int(home_marker_map.get(home_key, 0))
        marker_info       = data['markers'].get(str(self._marker_id), {})
        self._marker_size = float(marker_info.get('size', 0.20))
        self._marker_map_pose = {
            'map_x':  float(marker_info.get('map_x',  0.0)),
            'map_y':  float(marker_info.get('map_y',  0.0)),
            'map_z':  float(marker_info.get('map_z',  0.0)),
            'map_qx': float(marker_info.get('map_qx', 0.0)),
            'map_qy': float(marker_info.get('map_qy', 0.0)),
            'map_qz': float(marker_info.get('map_qz', 0.0)),
            'map_qw': float(marker_info.get('map_qw', 1.0)),
        }

        self.get_logger().info(
            f'home_key={home_key} → marker_id={self._marker_id}, '
            f'size={self._marker_size}m, target_dist={self._target_dist}m'
        )

        self._bridge        = CvBridge()
        self._camera_matrix = None
        self._dist_coeffs   = None
        self._cam_frame     = 'camera_color_optical_frame'
        self._latest_tvec   = None
        self._latest_rvec   = None
        self._tvec_lock     = threading.Lock()
        self._docking       = False

        self._tf_buffer   = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        cb = ReentrantCallbackGroup()
        self._cmd_pub          = self.create_publisher(Twist, '/cmd_vel', 10)
        self._initialpose_pub  = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 1)
        self.create_subscription(
            CameraInfo, '/camera/color/camera_info', self._info_cb, 1,
            callback_group=cb,
        )
        self.create_subscription(
            Image, '/camera/color/image_raw', self._image_cb, 10,
            callback_group=cb,
        )
        self.create_service(
            Trigger, '/aruco_home_dock', self._dock_cb,
            callback_group=cb,
        )
        self.get_logger().info('/aruco_home_dock 서비스 준비 완료')

    # ── 카메라 ──────────────────────────────────────────────────────────

    def _info_cb(self, msg: CameraInfo) -> None:
        if self._camera_matrix is not None:
            return
        k = msg.k
        self._camera_matrix = np.array(
            [[k[0], k[1], k[2]],
             [k[3], k[4], k[5]],
             [k[6], k[7], k[8]]], dtype=np.float64,
        )
        self._dist_coeffs = np.array(msg.d, dtype=np.float64)
        if msg.header.frame_id:
            self._cam_frame = msg.header.frame_id
        self.get_logger().info(f'카메라 파라미터 수신 (frame: {self._cam_frame})')

    def _image_cb(self, msg: Image) -> None:
        if self._camera_matrix is None or not self._docking:
            return
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(gray, ARUCO_DICT, parameters=ARUCO_PARAMS)

        if ids is None or self._marker_id not in ids.flatten().tolist():
            with self._tvec_lock:
                self._latest_tvec = None
                self._latest_rvec = None
            return

        idx  = ids.flatten().tolist().index(self._marker_id)
        half = self._marker_size / 2.0
        obj_pts = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)
        ret, rvec, tvec = cv2.solvePnP(
            obj_pts, corners[idx][0].astype(np.float32),
            self._camera_matrix, self._dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )
        with self._tvec_lock:
            if ret:
                self._latest_tvec = tvec.flatten()
                self._latest_rvec = rvec.flatten()
            else:
                self._latest_tvec = None
                self._latest_rvec = None

    # ── IBVS 서비스 ─────────────────────────────────────────────────────

    def _dock_cb(self, _request, response):
        if self._camera_matrix is None:
            response.success = False
            response.message = '카메라 파라미터 미수신'
            return response

        self._docking = True
        self.get_logger().info(
            f'IBVS 도킹 시작 (3DOF) — marker={self._marker_id}, target={self._target_dist}m'
        )

        start         = time.time()
        last_detected = time.time()

        try:
            while True:
                if time.time() - start > self._timeout:
                    self.get_logger().warn('도킹 타임아웃')
                    response.success = False
                    response.message = 'timeout'
                    return response

                with self._tvec_lock:
                    tvec = self._latest_tvec
                    rvec = self._latest_rvec

                if tvec is None or rvec is None:
                    self._cmd_pub.publish(Twist())  # 마커 미감지 즉시 정지
                    if time.time() - last_detected > self._no_marker_to:
                        self.get_logger().warn('마커 미감지 타임아웃')
                        response.success = False
                        response.message = 'marker not detected'
                        return response
                    time.sleep(0.05)
                    continue

                last_detected = time.time()
                lateral = float(tvec[0])
                depth   = float(tvec[2])

                R_cm, _ = cv2.Rodrigues(rvec)
                yaw_error = math.atan2(R_cm[0][2], -R_cm[2][2])

                if abs(depth - self._target_dist) < self._depth_tol \
                        and abs(lateral) < self._lateral_tol \
                        and abs(yaw_error) < self._yaw_tol:
                    self._cmd_pub.publish(Twist())   # 정차
                    time.sleep(0.1)                  # 완전 정지 대기
                    self._publish_initialpose(rvec, tvec)  # 정차 후 AMCL 보정
                    self.get_logger().info(
                        f'도킹 완료 — depth={depth:.3f}m '
                        f'lateral={lateral:.3f}m yaw={math.degrees(yaw_error):.1f}°'
                    )
                    response.success = True
                    response.message = (
                        f'docked depth={depth:.3f} '
                        f'lateral={lateral:.3f} yaw={math.degrees(yaw_error):.1f}deg'
                    )
                    return response

                linear_x = float(np.clip(
                    self._kp_v * (depth - self._target_dist),
                    -self._max_linear, self._max_linear,
                ))

                # 후진 시 angular 차단 (FOV 이탈 방지)
                if linear_x < 0:
                    angular_z = 0.0
                else:
                    angular_z = float(np.clip(
                        -self._kp_w * lateral - self._kp_yaw * yaw_error,
                        -self._max_angular, self._max_angular,
                    ))

                twist = Twist()
                twist.linear.x  = linear_x
                twist.angular.z = angular_z
                self._cmd_pub.publish(twist)

                self.get_logger().info(
                    f'depth={depth:.3f} lat={lateral:.3f} yaw={math.degrees(yaw_error):.1f}° '
                    f'→ v={linear_x:.3f} w={angular_z:.3f}',
                    throttle_duration_sec=0.5,
                )
                time.sleep(0.05)

        finally:
            self._docking = False
            self._cmd_pub.publish(Twist())

    # ── AMCL 리셋 ───────────────────────────────────────────────────────

    def _publish_initialpose(self, rvec: np.ndarray, tvec: np.ndarray) -> None:
        """정차 완료 위치에서 마커 절대 좌표로 AMCL 리셋."""
        R_cm, _ = cv2.Rodrigues(rvec)
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = R_cm
        T_cam_marker[:3, 3]  = tvec.flatten()

        try:
            tf = self._tf_buffer.lookup_transform(
                'base_link', self._cam_frame, rclpy.time.Time()
            )
        except Exception as e:
            self.get_logger().warn(f'TF lookup 실패 — /initialpose 발행 건너뜀: {e}')
            return

        t, q = tf.transform.translation, tf.transform.rotation
        T_base_cam   = self._tf_to_matrix(t.x, t.y, t.z, q.x, q.y, q.z, q.w)
        T_map_marker = self._tf_to_matrix(
            self._marker_map_pose['map_x'], self._marker_map_pose['map_y'],
            self._marker_map_pose['map_z'], self._marker_map_pose['map_qx'],
            self._marker_map_pose['map_qy'], self._marker_map_pose['map_qz'],
            self._marker_map_pose['map_qw'],
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
        msg.pose.covariance[0]  = 0.05
        msg.pose.covariance[7]  = 0.05
        msg.pose.covariance[35] = 0.05

        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f'[AMCL 리셋] x={robot_x:.3f} y={robot_y:.3f} yaw={math.degrees(robot_yaw):.1f}°'
        )

    # ── 유틸 ────────────────────────────────────────────────────────────

    @staticmethod
    def _tf_to_matrix(tx, ty, tz, qx, qy, qz, qw) -> np.ndarray:
        R = np.array([
            [1 - 2*(qy**2 + qz**2),  2*(qx*qy - qz*qw),  2*(qx*qz + qy*qw)],
            [2*(qx*qy + qz*qw),  1 - 2*(qx**2 + qz**2),  2*(qy*qz - qx*qw)],
            [2*(qx*qz - qy*qw),  2*(qy*qz + qx*qw),  1 - 2*(qx**2 + qy**2)],
        ])
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3]  = [tx, ty, tz]
        return T


def main(args=None):
    rclpy.init(args=args)
    node = ArucoHomeDock()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
