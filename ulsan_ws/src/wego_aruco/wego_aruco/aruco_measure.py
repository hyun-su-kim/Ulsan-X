"""aruco_measure.py — 마커 상대 포즈 실시간 측정 도구

용도:
  카메라에 마커가 보이는 동안, 마커의 *상대* 포즈를 매 프레임 콘솔에 출력한다.
  마커(또는 로봇)를 움직일 때마다 거리·각도가 실시간으로 갱신되므로,
  마커 위치를 옮겨가며 거리를 뽑아보는 용도에 쓴다. 별도 토픽 echo 불필요.

  현행 PBVS 홈 도킹(aruco_home_dock)은 마커의 맵 좌표가 전혀 필요 없고
  마커의 카메라 기준 상대 포즈만 사용한다(DEC-041/043). 이 노드는 그 상대
  포즈(depth/lateral/height·yaw·distance)를 측정·검증하기 위한 단순 도구다.

측정값 (카메라 optical 기준, aruco_home_dock과 동일한 정의):
  - depth   : 마커 전방 거리(m)   = tvec_z   → target_dist 비교 기준
  - lateral : 좌우 오프셋(m)       = tvec_x   (우+, 0에 가까울수록 정면)
  - height  : 상하 오프셋(m)       = tvec_y   (하+)
  - dist    : 직선 거리(m)         = |tvec|
  - yaw     : 마커 정면 대비 각(°) = atan2(R[0][2], -R[2][2])

실행:
  ros2 run wego_aruco aruco_measure
  ros2 run wego_aruco aruco_measure --ros-args -p marker_id:=1 -p marker_size:=0.20
"""

import math
from collections import deque

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
ARUCO_PARAMS.adaptiveThreshWinSizeMin = 3
ARUCO_PARAMS.adaptiveThreshWinSizeMax = 53
ARUCO_PARAMS.adaptiveThreshWinSizeStep = 5
ARUCO_PARAMS.minMarkerPerimeterRate = 0.02
ARUCO_PARAMS.errorCorrectionRate = 0.8


class ArucoMeasure(Node):
    """home 정지 상태에서 마커 상대 포즈를 측정·출력하는 도구 노드."""

    def __init__(self):
        super().__init__('aruco_measure')

        self.declare_parameter('marker_id', 0)
        self.declare_parameter('marker_size', 0.20)
        self.declare_parameter('avg_window', 30)        # 평균 요약을 낼 프레임 수
        self.declare_parameter('image_topic', '/camera/color/image_raw')
        self.declare_parameter('camera_info_topic', '/camera/color/camera_info')

        self._marker_id   = self.get_parameter('marker_id').get_parameter_value().integer_value
        self._marker_size = self.get_parameter('marker_size').get_parameter_value().double_value
        self._avg_window  = self.get_parameter('avg_window').get_parameter_value().integer_value
        image_topic       = self.get_parameter('image_topic').get_parameter_value().string_value
        info_topic        = self.get_parameter('camera_info_topic').get_parameter_value().string_value

        self._bridge = CvBridge()
        self._camera_matrix = None
        self._dist_coeffs = None

        # 평균 요약용 버퍼
        self._buf = deque(maxlen=self._avg_window)

        self.create_subscription(CameraInfo, info_topic, self._info_cb, 1)
        self.create_subscription(Image, image_topic, self._image_cb, 10)

        self.get_logger().info(
            f'aruco_measure 시작 — marker_id={self._marker_id} '
            f'size={self._marker_size}m, 평균 윈도우={self._avg_window}프레임'
        )

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
        self.get_logger().info(f'카메라 파라미터 수신 (frame: {msg.header.frame_id})')

    def _image_cb(self, msg: Image) -> None:
        if self._camera_matrix is None:
            return
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().warn(f'imgmsg_to_cv2 실패: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(gray, ARUCO_DICT, parameters=ARUCO_PARAMS)

        if ids is None or self._marker_id not in ids.flatten().tolist():
            self.get_logger().info('마커 미감지', throttle_duration_sec=1.0)
            return

        idx = ids.flatten().tolist().index(self._marker_id)
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
        if not ret:
            return

        t = tvec.flatten()
        depth, lateral, height = float(t[2]), float(t[0]), float(t[1])
        dist = float(np.linalg.norm(t))
        R_cm, _ = cv2.Rodrigues(rvec)
        yaw = math.degrees(math.atan2(R_cm[0][2], -R_cm[2][2]))

        # 매 프레임(0.5s throttle) 순간값 출력
        self.get_logger().info(
            f'id={self._marker_id}  depth={depth:.3f}m  lateral={lateral:+.3f}m  '
            f'height={height:+.3f}m  dist={dist:.3f}m  yaw={yaw:+.1f}°',
            throttle_duration_sec=0.5,
        )

        # 평균 요약
        self._buf.append((depth, lateral, height, dist, yaw))
        if len(self._buf) == self._avg_window:
            self._print_average()
            self._buf.clear()

    def _print_average(self) -> None:
        arr = np.array(self._buf, dtype=np.float64)
        mean = arr.mean(axis=0)
        std = arr.std(axis=0)
        self.get_logger().info(
            f'=== 평균({self._avg_window}프레임) ===  '
            f'depth={mean[0]:.3f}±{std[0]:.3f}  '
            f'lateral={mean[1]:+.3f}±{std[1]:.3f}  '
            f'height={mean[2]:+.3f}±{std[2]:.3f}  '
            f'dist={mean[3]:.3f}±{std[3]:.3f}  '
            f'yaw={mean[4]:+.1f}±{std[4]:.1f}°  ==='
        )


def main(args=None):
    rclpy.init(args=args)
    node = ArucoMeasure()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
