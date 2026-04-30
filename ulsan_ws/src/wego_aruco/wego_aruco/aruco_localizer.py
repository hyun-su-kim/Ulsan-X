"""
aruco_localizer.py — 운용 중 AMCL 보정 노드

동작 방식:
  1. 카메라로 ArUco 마커를 감지하고 카메라 기준 마커 pose(T_camera_marker)를 계산한다.
  2. markers.yaml에서 해당 마커의 맵 기준 pose(T_map_marker)를 조회한다.
  3. 역변환으로 현재 로봇의 맵 기준 pose(T_map_base)를 계산한다.
     T_map_base = T_map_marker × inv(T_camera_marker) × inv(T_base_camera)
  4. /initialpose를 발행해 AMCL 파티클을 재수렴시킨다.

마커가 감지될 때마다 보정하면 AMCL이 불안정해질 수 있으므로,
correction_interval(기본 2.0초) 간격으로만 발행한다.

실행:
  ros2 run wego_aruco aruco_localizer
  또는
  ros2 launch wego_aruco localizer_launch.py
"""

import os
import time

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, Image

import tf2_ros


# ──────────────────────────────────────────────
# 변환 행렬 유틸리티 (aruco_calibrator와 동일)
# ──────────────────────────────────────────────

def transform_msg_to_matrix(transform):
    """geometry_msgs/Transform → 4×4 변환 행렬"""
    q = [transform.rotation.x, transform.rotation.y,
         transform.rotation.z, transform.rotation.w]
    R = Rotation.from_quat(q).as_matrix()
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [transform.translation.x,
                transform.translation.y,
                transform.translation.z]
    return T


def yaml_dict_to_matrix(d: dict) -> np.ndarray:
    """markers.yaml의 마커 dict → 4×4 변환 행렬"""
    q = [d['qx'], d['qy'], d['qz'], d['qw']]
    R = Rotation.from_quat(q).as_matrix()
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [d['x'], d['y'], d['z']]
    return T


# ──────────────────────────────────────────────
# 보정 노드
# ──────────────────────────────────────────────

class ArucoLocalizer(Node):

    ARUCO_DICT  = cv2.aruco.DICT_4X4_50
    MARKER_SIZE = 0.10  # 마커 한 변 길이 (m) — 캘리브레이터와 동일해야 함

    # markers.yaml 경로: install/wego_aruco/share/wego_aruco/config/
    CONFIG_DIR = os.path.join(
        get_package_share_directory('wego_aruco'), 'config'
    )

    def __init__(self):
        super().__init__('aruco_localizer')

        # ── 파라미터 선언 ──
        # 보정 발행 최소 간격(초): 너무 짧으면 AMCL이 불안정해짐
        self.declare_parameter('correction_interval', 2.0)
        # 마커까지 거리 상한(m): 너무 먼 마커는 pose 오차가 커서 무시
        self.declare_parameter('max_marker_distance', 2.0)

        self._correction_interval = self.get_parameter(
            'correction_interval').value
        self._max_distance = self.get_parameter(
            'max_marker_distance').value

        # ── markers.yaml 로드 ──
        self._marker_map: dict[int, np.ndarray] = {}  # id → T_map_marker
        self._load_markers()

        # ── OpenCV ArUco 감지기 ──
        dictionary = cv2.aruco.getPredefinedDictionary(self.ARUCO_DICT)
        parameters = cv2.aruco.DetectorParameters()
        self._detector = cv2.aruco.ArucoDetector(dictionary, parameters)

        self._bridge = CvBridge()

        # ── TF 조회기 ──
        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)

        # ── 발행자: AMCL 위치 초기화 ──
        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)

        # ── 구독자 ──
        self.create_subscription(
            Image, '/camera/color/image_raw',
            self._image_cb, 10)

        self.create_subscription(
            CameraInfo, '/camera/color/camera_info',
            self._camera_info_cb, 10)

        # ── 내부 상태 ──
        self._camera_matrix = None
        self._dist_coeffs   = None
        self._last_correction_time = 0.0  # 마지막 보정 발행 시각 (UNIX time)

        self.get_logger().info(
            f'[보정 노드] 시작. 등록된 마커: {list(self._marker_map.keys())}')
        self.get_logger().info(
            f'[보정 노드] 보정 간격: {self._correction_interval}s, '
            f'최대 감지 거리: {self._max_distance}m')

    # ── 마커 데이터 로드 ─────────────────────────────────────────

    def _load_markers(self):
        """markers.yaml에서 등록된 마커들의 맵 기준 pose를 로드한다."""
        markers_path = os.path.join(self.CONFIG_DIR, 'markers.yaml')

        if not os.path.exists(markers_path):
            self.get_logger().error(
                f'[보정 노드] markers.yaml을 찾을 수 없습니다: {markers_path}')
            self.get_logger().error(
                '[보정 노드] aruco_calibrator를 먼저 실행해 마커를 등록하세요.')
            return

        with open(markers_path) as f:
            data = yaml.safe_load(f) or {}

        for marker_id, pose_dict in data.get('markers', {}).items():
            self._marker_map[int(marker_id)] = yaml_dict_to_matrix(pose_dict)

        self.get_logger().info(
            f'[보정 노드] {len(self._marker_map)}개 마커 로드 완료.')

    # ── 콜백: 카메라 내부 파라미터 ──────────────────────────────

    def _camera_info_cb(self, msg: CameraInfo):
        if self._camera_matrix is not None:
            return
        self._camera_matrix = np.array(msg.k).reshape(3, 3)
        self._dist_coeffs   = np.array(msg.d)
        self.get_logger().info('[보정 노드] 카메라 내부 파라미터 수신 완료.')

    # ── 콜백: 이미지 수신 & 보정 ────────────────────────────────

    def _image_cb(self, msg: Image):
        """이미지를 받을 때마다 마커를 감지하고 조건을 만족하면 보정을 발행한다."""
        if self._camera_matrix is None:
            return

        # 보정 간격 체크 (AMCL 과부하 방지)
        now = time.monotonic()
        if now - self._last_correction_time < self._correction_interval:
            return

        # ROS Image → OpenCV 그레이스케일
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = self._detector.detectMarkers(gray)

        if ids is None:
            return

        # 마커 코너 3D 좌표 (마커 중심 원점)
        half = self.MARKER_SIZE / 2.0
        obj_pts = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)

        # T_base_camera: base_link → camera_color_optical_frame
        # 매 프레임 조회하지 않고 캐시해도 되지만, 정확성을 위해 최신값 사용
        try:
            tf_stamped = self._tf_buffer.lookup_transform(
                'base_link', 'camera_color_optical_frame', rclpy.time.Time())
            T_base_camera = transform_msg_to_matrix(tf_stamped.transform)
        except Exception as e:
            self.get_logger().warn(f'[보정 노드] TF 조회 실패: {e}',
                                   throttle_duration_sec=5.0)
            return

        for i, corner in enumerate(corners):
            marker_id = int(ids[i][0])

            # 등록되지 않은 마커는 무시
            if marker_id not in self._marker_map:
                continue

            img_pts = corner[0].astype(np.float32)

            success, rvec, tvec = cv2.solvePnP(
                obj_pts, img_pts,
                self._camera_matrix, self._dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            if not success:
                continue

            # 마커까지 거리 필터링: tvec의 크기가 거리
            distance = float(np.linalg.norm(tvec))
            if distance > self._max_distance:
                self.get_logger().debug(
                    f'[보정 노드] 마커 {marker_id} 거리 {distance:.2f}m > '
                    f'임계값 {self._max_distance}m, 무시.')
                continue

            R_cm, _ = cv2.Rodrigues(rvec)

            # T_camera_marker: 카메라 기준 마커 pose
            T_camera_marker = np.eye(4)
            T_camera_marker[:3, :3] = R_cm
            T_camera_marker[:3, 3]  = tvec.flatten()

            # T_map_marker: markers.yaml에서 로드한 맵 기준 마커 pose
            T_map_marker = self._marker_map[marker_id]

            # ─────────────────────────────────────────────────────────────
            # 역변환으로 로봇의 맵 기준 pose 계산:
            #
            #   캘리브레이션 시: T_map_marker = T_map_base × T_base_camera × T_camera_marker
            #   역산:            T_map_base   = T_map_marker × inv(T_camera_marker) × inv(T_base_camera)
            #
            # inv(T_camera_marker): 마커에서 카메라 방향으로 역변환
            # inv(T_base_camera)  : 카메라에서 base_link 방향으로 역변환
            # ─────────────────────────────────────────────────────────────
            T_map_base = (T_map_marker
                          @ np.linalg.inv(T_camera_marker)
                          @ np.linalg.inv(T_base_camera))

            self._publish_initialpose(T_map_base)
            self._last_correction_time = now

            self.get_logger().info(
                f'[보정 노드] 마커 {marker_id} 기준 AMCL 보정 발행. '
                f'거리: {distance:.2f}m')

            # 한 프레임에서 마커 여러 개가 보여도 첫 번째 하나만 사용
            # (여러 마커로 평균내는 방식은 향후 개선 가능)
            break

    # ── /initialpose 발행 ────────────────────────────────────────

    def _publish_initialpose(self, T_map_base: np.ndarray):
        """계산된 T_map_base를 /initialpose로 발행해 AMCL 파티클을 재수렴시킨다."""
        msg = PoseWithCovarianceStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'

        t = T_map_base[:3, 3]
        R = T_map_base[:3, :3]
        q = Rotation.from_matrix(R).as_quat()  # [x, y, z, w]

        msg.pose.pose.position.x = float(t[0])
        msg.pose.pose.position.y = float(t[1])
        msg.pose.pose.position.z = 0.0  # 2D 주행이므로 z=0 고정

        msg.pose.pose.orientation.x = float(q[0])
        msg.pose.pose.orientation.y = float(q[1])
        msg.pose.pose.orientation.z = float(q[2])
        msg.pose.pose.orientation.w = float(q[3])

        # 공분산 행렬 (6×6 row-major, x y z roll pitch yaw 순서)
        # ArUco 측정 오차를 반영한 값. 대각선만 설정하고 나머지는 0.
        cov = [0.0] * 36
        cov[0]  = 0.05   # x 분산 (m²)
        cov[7]  = 0.05   # y 분산 (m²)
        cov[35] = 0.05   # yaw 분산 (rad²)
        msg.pose.covariance = cov

        self._initialpose_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ArucoLocalizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
