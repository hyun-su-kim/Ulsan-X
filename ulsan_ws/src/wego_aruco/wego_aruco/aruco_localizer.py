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

# OpenCV ArUco 기본값으로 복원 (2026-05-04)
# Phase 1에서 2m → 30cm 전진 접근하므로 원거리 특화 파라미터 불필요.
# 기본값으로도 2m 거리의 20cm 마커 충분히 검출 가능.
ARUCO_PARAMS.adaptiveThreshWinSizeMin = 3
ARUCO_PARAMS.adaptiveThreshWinSizeMax = 23   # 기본값
ARUCO_PARAMS.adaptiveThreshWinSizeStep = 10  # 기본값
ARUCO_PARAMS.minMarkerPerimeterRate = 0.03   # 기본값
ARUCO_PARAMS.errorCorrectionRate = 0.6       # 기본값

DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)


class ArucoLocalizer(Node):
    # ── 제어 게인 ──────────────────────────────────────────────────
    # KP_LINEAR  : 거리 오차 → 선속도 변환 게인
    # KP_ANGULAR : lateral 오차 → 각속도 변환 게인 (클수록 좌우 보정 강함)
    # KP_YAW     : yaw 오차 → 각속도 변환 게인 (현재 미사용)
    KP_LINEAR = 0.3
    KP_ANGULAR = 1.2   # 0.8 → 1.2: lateral 보정 강도 상향
    KP_YAW = 0.5

    # ── 속도 제한 ──────────────────────────────────────────────────
    # MAX_LINEAR 낮출수록 이동 중 보정 반응 시간 확보 → 정밀도 향상
    # MAX_ANGULAR 낮출수록 과보정(oscillation) 방지
    MAX_LINEAR = 0.08   # m/s  0.15 → 0.08: 저속으로 정밀도 향상
    MAX_ANGULAR = 0.3   # rad/s  0.4 → 0.3: 과보정 방지

    # ── 수렴 허용 오차 ─────────────────────────────────────────────
    DIST_TOL = 0.03     # m   — 거리 오차 허용 범위
    LAT_TOL = 0.03      # m   — lateral(좌우) 오차 허용 범위
    YAW_TOL = 0.05      # rad — yaw 오차 허용 범위 (~3°, 현재 미사용)

    # ── 기타 ───────────────────────────────────────────────────────
    CONTROL_RATE = 10        # Hz — 제어 루프 주기
    TIMEOUT_SEC = 60.0       # s  — Phase1 + Phase2 합산 타임아웃
    SEARCH_ANGULAR = 0.10    # rad/s — Phase1 미감지 시 저속 전진 대체 (미사용)
    INTERMEDIATE_DIST = 0.30 # m  — Phase1 목표 거리 (30cm 근접 정렬)

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
        # OpenCV 카메라 좌표계에서 마커가 카메라를 정면으로 바라볼 때
        # 마커 z축(법선)은 카메라 -z 방향을 가리킴 → normal[2] ≈ -1
        # atan2(0, -1) = ±π 가 되어 정면에서 0이 나와야 하는 조건이 깨짐.
        # -normal[2]로 부호 반전하면 정면 시 atan2(0, 1) = 0 으로 수렴.
        # 수정 전: math.atan2(normal[0], normal[2])
        return math.atan2(normal[0], -normal[2])

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

        interval = 1.0 / self.CONTROL_RATE
        start = time.time()
        last_search_dir = 1

        # ══════════════════════════════════════════════════════════════
        # Phase 1 — INTERMEDIATE_DIST(30cm)까지 전진 + lateral 보정
        # ══════════════════════════════════════════════════════════════
        # [설계 원칙] 제자리 회전을 하지 않는다.
        #   - 제자리 yaw 보정(회전)을 하면 마커가 FOV를 벗어나 미감지 발생.
        #   - 전진하면서 lateral(좌우 편차)만 보정하면:
        #       ① 마커가 항상 카메라 시야 안에 유지됨
        #       ② 마커에 가까워질수록 픽셀 해상도 증가 → 정밀도 향상
        #       ③ lateral 보정(이미지 중앙 맞춤)은 yaw도 기하학적으로 수렴시킴
        #          (2m 거리에서 마커를 중앙으로 맞추면 로봇이 마커 정면을 향하게 됨)
        # [수렴 조건] 30cm 도달 + lateral 허용 오차 이내
        self.get_logger().info(
            f'Phase 1 시작: {self.INTERMEDIATE_DIST}m 전진 접근 + lateral 보정'
        )
        phase1_done = False

        while time.time() - start < self.TIMEOUT_SEC:
            result = self._detect()

            if result is None:
                # 미감지 시 저속 전진 유지 — 정지하면 마커를 다시 찾기 어려움
                # 전진하면 마커가 점점 커져 재감지 확률이 높아짐
                slow_twist = Twist()
                slow_twist.linear.x = 0.05  # 저속 전진
                self._cmd_pub.publish(slow_twist)
                self.get_logger().warn(
                    f'마커 ID {self._target_id} 미감지 — 저속 전진으로 재감지 시도'
                )
                time.sleep(interval)
                continue

            tvec, rvec = result
            dist_err = tvec[2] - self.INTERMEDIATE_DIST
            lat_err  = tvec[0]
            # yaw_err: 마커 법선과 카메라 정면 사이의 각도.
            #   0이면 마커가 카메라에서 직사각형으로 보임 (수직 접근).
            #   값이 크면 사다리꼴로 보임 (비스듬히 접근).
            yaw_err  = self._yaw_err(rvec)

            # 수렴 조건: 거리 + lateral + yaw 세 축 모두 허용 오차 이내여야 Phase 1 완료.
            # yaw 조건을 생략하면 마커가 이미지 중앙에 있어도 비스듬히 접근한 채로
            # Phase 2로 넘어가 최종 정차 각도가 틀어질 수 있다.
            if (abs(dist_err) < self.DIST_TOL
                    and abs(lat_err) < self.LAT_TOL
                    and abs(yaw_err) < self.YAW_TOL):
                self._stop()
                self.get_logger().info(
                    f'Phase 1 완료 '
                    f'(dist_err={dist_err:.3f}m, lat={lat_err:.3f}m, yaw={yaw_err:.3f}rad)'
                )
                phase1_done = True
                break

            lin = float(np.clip(self.KP_LINEAR * dist_err, -self.MAX_LINEAR, self.MAX_LINEAR))
            # lateral + yaw 동시 보정.
            # KP_ANGULAR: 좌우 편차(lateral) 보정 — 마커를 이미지 중앙으로 정렬.
            # KP_YAW    : 수직 편차(yaw) 보정   — 마커가 직사각형으로 보이도록 정렬.
            # 둘 다 전진(linear.x > 0) 중에 각속도로만 수정하므로 제자리 회전이 아님.
            ang = float(np.clip(
                -self.KP_ANGULAR * lat_err - self.KP_YAW * yaw_err,
                -self.MAX_ANGULAR, self.MAX_ANGULAR
            ))
            twist = Twist()
            twist.linear.x = lin
            twist.angular.z = ang
            self._cmd_pub.publish(twist)
            time.sleep(interval)

        if not phase1_done:
            self._stop()
            res.success = False
            res.message = f'Phase 1 타임아웃 ({self.TIMEOUT_SEC}s) — 접근/정렬 실패'
            self.get_logger().warn(res.message)
            return res

        # ══════════════════════════════════════════════════════════════
        # Phase 2 — target_dist까지 후진 + lateral 보정 유지
        # ══════════════════════════════════════════════════════════════
        # [설계 원칙] 후진 중에도 lateral만 보정한다.
        #   - Phase 1에서 yaw가 수렴된 상태(마커가 직사각형으로 보임)로 진입.
        #   - 후진 거리(~1.7m)에 비례해 잔류 yaw 오차로 lateral이 누적될 수 있으므로
        #     실시간으로 lateral을 보정하며 후진한다.
        #   - yaw 보정은 추가하지 않음: Phase 1에서 이미 수직 정렬 완료.
        #     후진 중 추가 yaw 보정은 오히려 궤적을 틀어뜨릴 수 있음.
        self.get_logger().info(
            f'Phase 2 시작: {self._target_dist}m까지 후진 + lateral 보정 유지'
        )
        phase2_done = False

        while time.time() - start < self.TIMEOUT_SEC:
            result = self._detect()

            if result is None:
                # 후진 중 일시적 미감지 — 정지 후 재감지 대기
                self._stop()
                time.sleep(interval)
                continue

            tvec, _ = result
            dist_err = tvec[2] - self._target_dist  # 음수 → 후진
            lat_err  = tvec[0]

            if abs(dist_err) < self.DIST_TOL:
                self._stop()
                self.get_logger().info(
                    f'Phase 2 완료 — 정밀 주차 '
                    f'(dist_err={dist_err:.3f}m, lat={lat_err:.3f}m)'
                )
                phase2_done = True
                break

            lin = float(np.clip(self.KP_LINEAR * dist_err, -self.MAX_LINEAR, self.MAX_LINEAR))
            # lateral만 보정 — yaw 보정 제외 (후진 중 제자리 회전 방지)
            ang = float(np.clip(
                -self.KP_ANGULAR * lat_err,
                -self.MAX_ANGULAR, self.MAX_ANGULAR
            ))
            twist = Twist()
            twist.linear.x = lin
            twist.angular.z = ang
            self._cmd_pub.publish(twist)
            time.sleep(interval)

        if not phase2_done:
            self._stop()
            res.success = False
            res.message = f'Phase 2 타임아웃 ({self.TIMEOUT_SEC}s) — 후진 실패'
            self.get_logger().warn(res.message)
            return res

        # self._publish_initialpose()  # 주차 위치 확정 후 활성화
        res.success = True
        res.message = f'정밀 주차 완료: target_dist={self._target_dist}m'
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
