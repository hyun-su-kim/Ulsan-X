import math
import time

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
from std_msgs.msg import String
from std_srvs.srv import Trigger


ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)


class ArucoLocalizer(Node):
    KP_LINEAR = 0.4
    KP_ANGULAR = 0.8
    KP_YAW = 0.5
    MAX_LINEAR = 0.15    # m/s
    MAX_ANGULAR = 0.4    # rad/s
    DIST_TOL = 0.03      # m
    LAT_TOL = 0.03       # m
    YAW_TOL = 0.05       # rad (~3°)
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
        self._cam_offset: float = float(marker_info['cam_offset'])
        self._map_x: float = float(marker_info['map_x'])
        self._map_y: float = float(marker_info['map_y'])
        self._map_yaw: float = float(marker_info['map_yaw'])
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
        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10
        )
        # [측정용] LIMO를 원하는 정차 위치에 수동으로 배치한 뒤
        # `ros2 topic echo /aruco_debug` 로 depth 값을 읽어 markers.yaml의
        # target_dist에 입력한다. target_dist 설정 완료 후에는 사용하지 않는다.
        self._debug_pub = self.create_publisher(String, '/aruco_debug', 10)
        self.create_timer(0.2, self._debug_cb)  # 5Hz — 마커 감지 시 거리 발행
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

    def _detect(self) -> tuple[np.ndarray, np.ndarray] | None:
        """target marker의 (tvec, rvec) 반환. 미감지 시 None.

        OpenCV 4.7+에서 estimatePoseSingleMarkers 제거 → solvePnP로 대체.
        obj_pts: 마커 좌표계 3D 코너 (좌상→우상→우하→좌하, DICT_4X4_50 detectMarkers 순서와 일치)
        tvec: 카메라 프레임 기준 마커 위치 [x=오른쪽, y=아래, z=전방(depth)]
        rvec: 마커 → 카메라 회전 (Rodrigues 표현)
        """
        if self._camera_matrix is None or self._latest_image is None:
            return None
        gray = cv2.cvtColor(self._latest_image, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = DETECTOR.detectMarkers(gray)
        if ids is None or self._target_id not in ids.flatten():
            return None
        idx = list(ids.flatten()).index(self._target_id)
        half = self._target_size / 2.0
        # 마커 좌표계 원점 = 마커 중심, z축 = 마커 법선 (카메라 방향)
        obj_pts = np.array([
            [-half,  half, 0.0],   # 좌상
            [ half,  half, 0.0],   # 우상
            [ half, -half, 0.0],   # 우하
            [-half, -half, 0.0],   # 좌하
        ], dtype=np.float32)
        img_pts = corners[idx][0].astype(np.float32)
        _, rvec, tvec = cv2.solvePnP(
            obj_pts, img_pts, self._camera_matrix, self._dist_coeffs
        )
        return tvec.flatten(), rvec.flatten()

    def _yaw_err(self, rvec: np.ndarray) -> float:
        """마커 법선 벡터 기반 yaw 오차 (rad). 0이면 로봇이 마커와 수직.

        마커 좌표계의 z축(법선)은 마커 평면에서 카메라 방향을 향한다.
        R의 3번째 열(R[:, 2])은 마커 z축이 카메라 프레임에서 향하는 방향.
        로봇이 마커와 완전히 수직이면 법선이 카메라 정면(z축)과 일치 → normal = [0, ?, 1].
        atan2(normal[0], normal[2]): 수평면 상의 좌우 편향각 추출.
          - 양수: 로봇이 오른쪽으로 틀어짐 → 좌회전 필요
          - 음수: 로봇이 왼쪽으로 틀어짐 → 우회전 필요
        """
        R, _ = cv2.Rodrigues(rvec)
        normal = R[:, 2]  # 카메라 프레임에서 마커 법선 벡터
        return math.atan2(normal[0], normal[2])

    def _debug_cb(self) -> None:
        """마커 감지 시 /aruco_debug 토픽으로 거리·yaw 발행 — 측정 및 모니터링용."""
        result = self._detect()
        if result is None:
            return
        tvec, rvec = result
        yaw = self._yaw_err(rvec)
        msg = String()
        msg.data = (
            f'depth={tvec[2]:.3f}m  lateral={tvec[0]:.3f}m  yaw_err={yaw:.3f}rad'
        )
        self._debug_pub.publish(msg)

    def _stop(self) -> None:
        self._cmd_pub.publish(Twist())

    def _publish_initialpose(self) -> None:
        """마커 map 좌표 + target_dist로 로봇 위치 역산 후 /initialpose 발행.

        마커는 map 상 고정 위치(map_x, map_y, map_yaw)에 부착되어 있다.
        visual servoing 완료 시 로봇(카메라)은 마커 정면 target_dist 거리에 수직으로 정차.
        카메라는 base_link 기준 cam_offset만큼 전방에 있으므로:
          total_dist = target_dist + cam_offset  (base_link 기준 마커까지 거리)
          robot_x = marker_x - total_dist * cos(marker_yaw)
          robot_y = marker_y - total_dist * sin(marker_yaw)
          robot_yaw = marker_yaw + π  (마커를 바라보는 방향)
        접근 방향에 무관하게 항상 동일한 map 좌표로 수렴 → AMCL 정확 리셋 보장.
        """
        total_dist = self._target_dist + self._cam_offset
        robot_x = self._map_x - total_dist * math.cos(self._map_yaw)
        robot_y = self._map_y - total_dist * math.sin(self._map_yaw)
        robot_yaw = self._map_yaw + math.pi

        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = robot_x
        msg.pose.pose.position.y = robot_y
        msg.pose.pose.orientation.z = math.sin(robot_yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(robot_yaw / 2.0)
        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f'AMCL 리셋: x={robot_x:.3f}, y={robot_y:.3f}, yaw={robot_yaw:.3f}'
        )

    def _correct_cb(self, _req: Trigger.Request, res: Trigger.Response):
        if self._camera_matrix is None:
            res.success = False
            res.message = 'CameraInfo 미수신'
            return res

        self.get_logger().info('visual servoing 시작')
        interval = 1.0 / self.CONTROL_RATE
        start = time.time()

        while time.time() - start < self.TIMEOUT_SEC:
            result = self._detect()

            if result is None:
                self._stop()
                self.get_logger().warn(f'마커 ID {self._target_id} 미감지 — 대기 중')
                time.sleep(interval)
                continue

            tvec, rvec = result
            # tvec[2]: depth (마커까지 전방 거리), tvec[0]: lateral (좌우 편차)
            dist_err = tvec[2] - self._target_dist
            lat_err = tvec[0]
            yaw = self._yaw_err(rvec)

            # 3축 수렴 조건: 거리·측면·법선 yaw 모두 허용 오차 이내
            if abs(dist_err) < self.DIST_TOL and abs(lat_err) < self.LAT_TOL and abs(yaw) < self.YAW_TOL:
                self._stop()
                self.get_logger().info(
                    f'정밀 정차 완료 '
                    f'(dist_err={dist_err:.3f}m, lat_err={lat_err:.3f}m, yaw_err={yaw:.3f}rad)'
                )
                self._publish_initialpose()
                res.success = True
                res.message = (
                    f'정차 완료: depth={tvec[2]:.3f}m, '
                    f'lateral={tvec[0]:.3f}m, yaw={yaw:.3f}rad'
                )
                return res

            lin = float(np.clip(self.KP_LINEAR * dist_err, -self.MAX_LINEAR, self.MAX_LINEAR))
            # angular = 측면 편차 보정(KP_ANGULAR) + 법선 yaw 오차 보정(KP_YAW)
            # 두 항을 합산해 단일 angular velocity로 제어
            ang = float(np.clip(
                -self.KP_ANGULAR * lat_err - self.KP_YAW * yaw,
                -self.MAX_ANGULAR, self.MAX_ANGULAR
            ))

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
