"""
aruco_calibrator.py — 1회 캘리브레이션 노드

동작 방식:
  1. 카메라로 ArUco 마커를 감지하고 카메라 기준 마커 pose(T_camera_marker)를 계산한다.
  2. AMCL의 /amcl_pose로 현재 로봇의 맵 기준 pose(T_map_base)를 가져온다.
  3. TF로 base_link → camera_color_optical_frame 변환(T_base_camera)을 조회한다.
  4. 세 변환을 합성해 마커의 맵 기준 pose(T_map_marker)를 계산한다.
     T_map_marker = T_map_base × T_base_camera × T_camera_marker
  5. 터미널에서 목적지 이름을 입력하면 markers.yaml과 waypoints.yaml에 저장한다.

실행:
  ros2 run wego_aruco aruco_calibrator
"""

import threading
import os

import cv2
import numpy as np
import rclpy
import yaml
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, Image

import tf2_ros


# ──────────────────────────────────────────────
# 변환 행렬 유틸리티
# ──────────────────────────────────────────────

def pose_msg_to_matrix(pose):
    """geometry_msgs/Pose → 4×4 변환 행렬 (T_parent_child)"""
    q = [pose.orientation.x, pose.orientation.y,
         pose.orientation.z, pose.orientation.w]
    R = Rotation.from_quat(q).as_matrix()
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [pose.position.x, pose.position.y, pose.position.z]
    return T


def transform_msg_to_matrix(transform):
    """geometry_msgs/Transform → 4×4 변환 행렬 (T_parent_child)"""
    q = [transform.rotation.x, transform.rotation.y,
         transform.rotation.z, transform.rotation.w]
    R = Rotation.from_quat(q).as_matrix()
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [transform.translation.x,
                transform.translation.y,
                transform.translation.z]
    return T


def matrix_to_pose_dict(T):
    """4×4 변환 행렬 → yaml 저장용 dict (x, y, z, qx, qy, qz, qw, yaw)"""
    t = T[:3, 3]
    R = Rotation.from_matrix(T[:3, :3])
    q = R.as_quat()          # [x, y, z, w]
    yaw = R.as_euler('xyz')[2]
    return {
        'x':   float(t[0]),
        'y':   float(t[1]),
        'z':   float(t[2]),
        'qx':  float(q[0]),
        'qy':  float(q[1]),
        'qz':  float(q[2]),
        'qw':  float(q[3]),
        'yaw': float(yaw),
    }


# ──────────────────────────────────────────────
# 캘리브레이션 노드
# ──────────────────────────────────────────────

class ArucoCalibrator(Node):

    # 사용할 ArUco 딕셔너리 (마커 인쇄 시와 동일해야 함)
    ARUCO_DICT = cv2.aruco.DICT_4X4_50

    # 마커 한 변 길이 (m) — 인쇄한 실물 크기와 일치해야 함
    MARKER_SIZE = 0.10

    # 저장 경로 (패키지 설치 경로 대신 소스 config 디렉토리에 직접 저장)
    CONFIG_DIR = os.path.join(
        os.path.dirname(__file__), '..', '..', 'config'
    )

    def __init__(self):
        super().__init__('aruco_calibrator')

        # ── OpenCV ArUco 감지기 초기화 (OpenCV 4.7+ 공식 API) ──
        dictionary = cv2.aruco.getPredefinedDictionary(self.ARUCO_DICT)
        parameters = cv2.aruco.DetectorParameters()
        self._detector = cv2.aruco.ArucoDetector(dictionary, parameters)

        # ── ROS → OpenCV 이미지 변환기 ──
        self._bridge = CvBridge()

        # ── TF 조회기 ──
        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)

        # ── 구독자 ──
        self.create_subscription(
            Image, '/camera/color/image_raw',
            self._image_cb, 10)

        self.create_subscription(
            CameraInfo, '/camera/color/camera_info',
            self._camera_info_cb, 10)

        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose',
            self._amcl_cb, 10)

        # ── 내부 상태 ──
        self._camera_matrix = None   # 카메라 내부 파라미터 K (3×3)
        self._dist_coeffs = None     # 왜곡 계수 D
        self._amcl_pose = None       # 최신 로봇 맵 기준 pose

        # 현재 이미지에서 감지된 마커 목록 [(id, T_camera_marker), ...]
        self._detected: list[tuple[int, np.ndarray]] = []

        # 저장된 결과 (yaml 파일에 누적)
        self._markers_data: dict = {}    # markers.yaml 내용
        self._waypoints_data: dict = {}  # waypoints.yaml 내용

        # 기존 파일이 있으면 로드해서 이어쓰기
        self._load_existing_yaml()

        # ── 키보드 입력 스레드 (ROS spin과 분리) ──
        self._input_thread = threading.Thread(
            target=self._input_loop, daemon=True)
        self._input_thread.start()

        self.get_logger().info(
            '[캘리브레이터] 시작. 로봇을 목적지 앞에 위치시킨 뒤 터미널에서 목적지 이름을 입력하세요.')

    # ── 콜백: 카메라 내부 파라미터 ──────────────────────────────

    def _camera_info_cb(self, msg: CameraInfo):
        """camera_info를 한 번만 수신해 내부 파라미터를 저장한다."""
        if self._camera_matrix is not None:
            return  # 이미 수신했으면 무시

        # K는 row-major 1D 배열(9개)로 오는 것을 3×3으로 변환
        self._camera_matrix = np.array(msg.k).reshape(3, 3)
        self._dist_coeffs = np.array(msg.d)
        self.get_logger().info('[캘리브레이터] 카메라 내부 파라미터 수신 완료.')

    # ── 콜백: AMCL 위치 ─────────────────────────────────────────

    def _amcl_cb(self, msg: PoseWithCovarianceStamped):
        """최신 AMCL pose를 저장한다."""
        self._amcl_pose = msg

    # ── 콜백: 이미지 수신 & 마커 감지 ──────────────────────────

    def _image_cb(self, msg: Image):
        """이미지를 받을 때마다 마커를 감지하고 _detected를 갱신한다."""
        if self._camera_matrix is None:
            return  # 카메라 파라미터 아직 없음

        # ROS Image → OpenCV BGR 이미지
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── ArUco 감지 (OpenCV 4.7+ ArucoDetector API) ──
        corners, ids, _ = self._detector.detectMarkers(gray)

        self._detected = []

        if ids is None:
            return  # 마커 없음

        # 마커 코너 3D 좌표: 마커 중심이 원점, Z=0 평면에 위치
        half = self.MARKER_SIZE / 2.0
        obj_pts = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)

        for i, corner in enumerate(corners):
            marker_id = int(ids[i][0])
            img_pts = corner[0].astype(np.float32)  # shape (4, 2)

            # solvePnP: 카메라 기준 마커 pose 계산
            # rvec: Rodrigues 회전벡터, tvec: 평행이동벡터 (단위 m)
            success, rvec, tvec = cv2.solvePnP(
                obj_pts, img_pts,
                self._camera_matrix, self._dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE  # 정사각형 마커에 최적화된 방법
            )
            if not success:
                continue

            # Rodrigues → 회전행렬
            R_cm, _ = cv2.Rodrigues(rvec)

            # T_camera_marker: 카메라 프레임에서 마커 프레임으로의 변환
            T_camera_marker = np.eye(4)
            T_camera_marker[:3, :3] = R_cm
            T_camera_marker[:3, 3] = tvec.flatten()

            self._detected.append((marker_id, T_camera_marker))

        if self._detected:
            ids_str = [str(d[0]) for d in self._detected]
            self.get_logger().info(
                f'[캘리브레이터] 마커 감지됨: ID {ids_str}', throttle_duration_sec=2.0)

    # ── 키보드 입력 루프 (별도 스레드) ─────────────────────────

    def _input_loop(self):
        """
        사용자가 목적지 이름을 입력하면 현재 감지된 마커와 로봇 pose를 저장한다.
        'q' 입력 시 종료.
        """
        print('\n[캘리브레이터] 준비 완료.')
        print('  사용법: 로봇을 목적지 앞에 정위치 → 마커 감지 확인 → 목적지 이름 입력 후 엔터')
        print('  종료: q 입력\n')

        while True:
            try:
                name = input('목적지 이름 입력 (예: room_1, counseling_room): ').strip()
            except EOFError:
                break

            if name.lower() == 'q':
                print('[캘리브레이터] 종료합니다.')
                break

            if not name:
                print('  → 이름이 비어 있습니다. 다시 입력하세요.')
                continue

            self._save_current(name)

    # ── 저장 로직 ────────────────────────────────────────────────

    def _save_current(self, destination_name: str):
        """현재 감지된 마커와 AMCL pose를 yaml에 저장한다."""

        # 사전 검사
        if not self._detected:
            print('  → 마커가 감지되지 않았습니다. 카메라 시야 안에 마커를 위치시키세요.')
            return

        if self._amcl_pose is None:
            print('  → /amcl_pose를 아직 수신하지 못했습니다. AMCL이 실행 중인지 확인하세요.')
            return

        # T_base_camera: base_link → camera_color_optical_frame
        try:
            tf_stamped = self._tf_buffer.lookup_transform(
                'base_link',
                'camera_color_optical_frame',
                rclpy.time.Time()  # 가장 최신 변환 사용
            )
        except Exception as e:
            print(f'  → TF 조회 실패: {e}')
            return

        # 변환 행렬 준비
        T_map_base = pose_msg_to_matrix(self._amcl_pose.pose.pose)
        T_base_camera = transform_msg_to_matrix(tf_stamped.transform)

        # 감지된 마커 각각에 대해 T_map_marker 계산
        for marker_id, T_camera_marker in self._detected:
            # ─────────────────────────────────────────────────────────
            # 변환 합성:
            #   T_map_marker = T_map_base × T_base_camera × T_camera_marker
            #
            # 해석:
            #   카메라가 마커를 봤을 때의 상대 pose(T_camera_marker)를
            #   카메라→base_link→맵 순서로 좌표계를 올려가며 맵 기준 pose로 변환
            # ─────────────────────────────────────────────────────────
            T_map_marker = T_map_base @ T_base_camera @ T_camera_marker

            marker_dict = matrix_to_pose_dict(T_map_marker)
            marker_dict['size'] = self.MARKER_SIZE  # pose 계산 시 필요

            self._markers_data[marker_id] = marker_dict
            print(f'  → 마커 ID {marker_id} 저장: '
                  f"x={marker_dict['x']:.3f}, y={marker_dict['y']:.3f}, "
                  f"yaw={marker_dict['yaw']:.3f}")

        # waypoints: 목적지 이름 → 현재 로봇 위치
        # (나중에 wego_behaviour가 navigate_to_pose 목표로 사용)
        robot_dict = matrix_to_pose_dict(T_map_base)
        # 감지된 마커 ID 목록도 함께 기록 (보정 노드에서 연관 마커를 알 수 있음)
        robot_dict['marker_ids'] = [d[0] for d in self._detected]
        self._waypoints_data[destination_name] = robot_dict

        print(f'  → 목적지 "{destination_name}" 저장: '
              f"x={robot_dict['x']:.3f}, y={robot_dict['y']:.3f}, "
              f"yaw={robot_dict['yaw']:.3f}")

        # yaml 파일에 즉시 기록
        self._write_yaml()
        print(f'  → {self.CONFIG_DIR}/markers.yaml, waypoints.yaml 저장 완료.\n')

    def _write_yaml(self):
        """markers.yaml과 waypoints.yaml을 config 디렉토리에 덮어쓴다."""
        os.makedirs(self.CONFIG_DIR, exist_ok=True)

        markers_path = os.path.join(self.CONFIG_DIR, 'markers.yaml')
        with open(markers_path, 'w') as f:
            yaml.dump({'markers': self._markers_data}, f,
                      default_flow_style=False, allow_unicode=True)

        waypoints_path = os.path.join(self.CONFIG_DIR, 'waypoints.yaml')
        with open(waypoints_path, 'w') as f:
            yaml.dump({'waypoints': self._waypoints_data}, f,
                      default_flow_style=False, allow_unicode=True)

    def _load_existing_yaml(self):
        """기존 yaml이 있으면 로드해서 이어쓰기를 지원한다."""
        markers_path = os.path.join(self.CONFIG_DIR, 'markers.yaml')
        waypoints_path = os.path.join(self.CONFIG_DIR, 'waypoints.yaml')

        if os.path.exists(markers_path):
            with open(markers_path) as f:
                data = yaml.safe_load(f) or {}
                self._markers_data = data.get('markers', {})

        if os.path.exists(waypoints_path):
            with open(waypoints_path) as f:
                data = yaml.safe_load(f) or {}
                self._waypoints_data = data.get('waypoints', {})


def main(args=None):
    rclpy.init(args=args)
    node = ArucoCalibrator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
