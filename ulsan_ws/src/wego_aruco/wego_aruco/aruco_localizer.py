import math
import time

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


ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)


class ArucoLocalizer(Node):
    KP_LINEAR = 0.4
    KP_ANGULAR = 0.8
    MAX_LINEAR = 0.15    # m/s
    MAX_ANGULAR = 0.4    # rad/s
    DIST_TOL = 0.03      # m
    LAT_TOL = 0.03       # m
    CONTROL_RATE = 10    # Hz
    TIMEOUT_SEC = 30.0

    def __init__(self):
        super().__init__('aruco_localizer')

        cb = ReentrantCallbackGroup()

        self.declare_parameter('home_key', 'home_robot1')
        self.declare_parameter(
            'markers_file',
            str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml',
        )

        home_key = self.get_parameter('home_key').get_parameter_value().string_value
        markers_file = self.get_parameter('markers_file').get_parameter_value().string_value

        with open(markers_file, 'r') as f:
            data = yaml.safe_load(f)

        self._target_id: int = data['home_marker'][home_key]
        marker_info = data['markers'][self._target_id]
        self._target_size: float = float(marker_info['size'])
        self._target_dist: float = float(marker_info['target_dist'])
        self.get_logger().info(
            f'홈 키: {home_key} → 마커 ID {self._target_id}, '
            f'목표 거리: {self._target_dist}m'
        )

        self._bridge = CvBridge()
        self._camera_matrix: np.ndarray | None = None
        self._dist_coeffs: np.ndarray | None = None
        self._latest_image: np.ndarray | None = None

        self.create_subscription(
            CameraInfo, '/camera/color/camera_info', self._info_cb, 1, callback_group=cb
        )
        self.create_subscription(
            Image, '/camera/color/image_raw', self._image_cb, 1, callback_group=cb
        )
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_service(Trigger, '/aruco_correct', self._correct_cb, callback_group=cb)

        self.get_logger().info('/aruco_correct 서비스 대기 중')

    def _info_cb(self, msg: CameraInfo) -> None:
        if self._camera_matrix is not None:
            return
        k = msg.k
        self._camera_matrix = np.array(
            [[k[0], k[1], k[2]],
             [k[3], k[4], k[5]],
             [k[6], k[7], k[8]]], dtype=float
        )
        self._dist_coeffs = np.array(msg.d, dtype=float)
        self.get_logger().info('카메라 파라미터 수신 완료')

    def _image_cb(self, msg: Image) -> None:
        self._latest_image = self._bridge.imgmsg_to_cv2(msg, 'bgr8')

    def _detect(self) -> np.ndarray | None:
        """target marker의 tvec [x, y, z] 반환. 미감지 시 None."""
        if self._camera_matrix is None or self._latest_image is None:
            return None
        gray = cv2.cvtColor(self._latest_image, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = DETECTOR.detectMarkers(gray)
        if ids is None or self._target_id not in ids.flatten():
            return None
        idx = list(ids.flatten()).index(self._target_id)
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            [corners[idx]], self._target_size, self._camera_matrix, self._dist_coeffs
        )
        return tvecs[0][0]

    def _stop(self) -> None:
        self._cmd_pub.publish(Twist())

    def _correct_cb(self, _req: Trigger.Request, res: Trigger.Response):
        if self._camera_matrix is None:
            res.success = False
            res.message = 'CameraInfo 미수신'
            return res

        self.get_logger().info('visual servoing 시작')
        interval = 1.0 / self.CONTROL_RATE
        start = time.time()

        while time.time() - start < self.TIMEOUT_SEC:
            tvec = self._detect()

            if tvec is None:
                self._stop()
                self.get_logger().warn(f'마커 ID {self._target_id} 미감지 — 대기 중')
                time.sleep(interval)
                continue

            # 카메라 프레임: z=전방(depth), x=오른쪽(lateral)
            dist_err = tvec[2] - self._target_dist
            lat_err = tvec[0]

            if abs(dist_err) < self.DIST_TOL and abs(lat_err) < self.LAT_TOL:
                self._stop()
                self.get_logger().info(
                    f'정밀 정차 완료 (dist_err={dist_err:.3f}m, lat_err={lat_err:.3f}m)'
                )
                res.success = True
                res.message = f'정차 완료: depth={tvec[2]:.3f}m, lateral={tvec[0]:.3f}m'
                return res

            lin = float(np.clip(self.KP_LINEAR * dist_err, -self.MAX_LINEAR, self.MAX_LINEAR))
            ang = float(np.clip(-self.KP_ANGULAR * lat_err, -self.MAX_ANGULAR, self.MAX_ANGULAR))

            twist = Twist()
            twist.linear.x = lin
            twist.angular.z = ang
            self._cmd_pub.publish(twist)
            time.sleep(interval)

        self._stop()
        res.success = False
        res.message = f'타임아웃 ({self.TIMEOUT_SEC}s) — 마커 미감지 또는 수렴 실패'
        self.get_logger().warn(res.message)
        return res


def main():
    rclpy.init()
    node = ArucoLocalizer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
