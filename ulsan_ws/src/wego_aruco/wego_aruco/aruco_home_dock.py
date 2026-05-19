"""aruco_home_dock.py — 홈 정밀 정차 IBVS 서비스 노드 (DEC-029)

/aruco_home_dock (std_srvs/Trigger) 서비스 제공.
Nav2가 staging pose에 정지한 뒤 호출 → IBVS로 마커 정면 정밀 정차.

제어 법칙:
  linear.x  =  Kp_v × (depth - target_dist)   [전진: depth > target 이면 양수]
  angular.z = -Kp_w × lateral                  [카메라 x축 오프셋, 오른쪽 양수]
두 축 동시 발행 → 호(arc) 경로로 마커 정면 수렴
"""

import time
import threading

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_srvs.srv import Trigger


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
        self.declare_parameter('max_linear',            0.15)
        self.declare_parameter('max_angular',           0.5)
        self.declare_parameter('depth_tol',             0.03)
        self.declare_parameter('lateral_tol',           0.02)
        self.declare_parameter('timeout_sec',           30.0)
        self.declare_parameter('no_marker_timeout_sec', 5.0)

        home_key           = self.get_parameter('home_key').get_parameter_value().string_value
        self._target_dist  = self.get_parameter('target_dist').get_parameter_value().double_value
        self._kp_v         = self.get_parameter('kp_v').get_parameter_value().double_value
        self._kp_w         = self.get_parameter('kp_w').get_parameter_value().double_value
        self._max_linear   = self.get_parameter('max_linear').get_parameter_value().double_value
        self._max_angular  = self.get_parameter('max_angular').get_parameter_value().double_value
        self._depth_tol    = self.get_parameter('depth_tol').get_parameter_value().double_value
        self._lateral_tol  = self.get_parameter('lateral_tol').get_parameter_value().double_value
        self._timeout      = self.get_parameter('timeout_sec').get_parameter_value().double_value
        self._no_marker_to = self.get_parameter('no_marker_timeout_sec').get_parameter_value().double_value

        markers_file = str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml'
        with open(markers_file) as f:
            data = yaml.safe_load(f)

        home_marker_map   = data.get('home_marker', {})
        self._marker_id   = int(home_marker_map.get(home_key, 0))
        marker_info       = data['markers'].get(str(self._marker_id), {})
        self._marker_size = float(marker_info.get('size', 0.20))

        self.get_logger().info(
            f'home_key={home_key} → marker_id={self._marker_id}, '
            f'size={self._marker_size}m, target_dist={self._target_dist}m'
        )

        self._bridge        = CvBridge()
        self._camera_matrix = None
        self._dist_coeffs   = None
        self._latest_tvec   = None
        self._tvec_lock     = threading.Lock()
        self._docking       = False

        cb = ReentrantCallbackGroup()
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
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
        self.get_logger().info('카메라 파라미터 수신')

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
            return

        idx  = ids.flatten().tolist().index(self._marker_id)
        half = self._marker_size / 2.0
        obj_pts = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)
        ret, _, tvec = cv2.solvePnP(
            obj_pts, corners[idx][0].astype(np.float32),
            self._camera_matrix, self._dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )
        with self._tvec_lock:
            self._latest_tvec = tvec.flatten() if ret else None

    # ── IBVS 서비스 ─────────────────────────────────────────────────────

    def _dock_cb(self, _request, response):
        if self._camera_matrix is None:
            response.success = False
            response.message = '카메라 파라미터 미수신'
            return response

        self._docking = True
        self.get_logger().info(
            f'IBVS 도킹 시작 — marker={self._marker_id}, target={self._target_dist}m'
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

                if tvec is None:
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

                if abs(depth - self._target_dist) < self._depth_tol \
                        and abs(lateral) < self._lateral_tol:
                    self.get_logger().info(
                        f'도킹 완료 — depth={depth:.3f}m lateral={lateral:.3f}m'
                    )
                    response.success = True
                    response.message = f'docked depth={depth:.3f} lateral={lateral:.3f}'
                    return response

                linear_x  = float(np.clip(
                    self._kp_v * (depth - self._target_dist),
                    -self._max_linear, self._max_linear,
                ))
                angular_z = float(np.clip(
                    -self._kp_w * lateral,
                    -self._max_angular, self._max_angular,
                ))

                twist = Twist()
                twist.linear.x  = linear_x
                twist.angular.z = angular_z
                self._cmd_pub.publish(twist)

                self.get_logger().info(
                    f'depth={depth:.3f} lat={lateral:.3f} '
                    f'→ v={linear_x:.3f} w={angular_z:.3f}',
                    throttle_duration_sec=0.5,
                )
                time.sleep(0.05)

        finally:
            self._docking = False
            self._cmd_pub.publish(Twist())


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
