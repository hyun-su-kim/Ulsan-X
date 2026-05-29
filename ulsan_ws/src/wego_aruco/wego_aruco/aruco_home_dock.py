"""aruco_home_dock.py — 홈 정밀 정차 도킹 서비스 노드 (차동구동 자세 제어)

문제 정의:
  차동구동(비홀로노믹) 로봇은 제어 입력이 (v, ω) 2개뿐인데, 도킹은
  depth·lateral·yaw 3개를 맞춰야 함 → 과소구동(underactuated) 자세 정밀화 문제.

폐기된 초기 방식 (단순 합산 P제어):
  angular.z = -Kp_w·lateral - Kp_yaw·yaw_error  ← lateral·yaw 보정이 ω 하나를
  공유하며 서로 상쇄(fight) → 목표 근처에서 교착, 수렴 실패. (DEC-038 참고)

현재 방식 — 도킹 목표점의 로봇 기준 기하 (ρ, α, θ_g)로 통합:
  _compute_geometry(): 마커 법선 위 target_dist 지점을 도킹 목표점으로 잡고
    ρ   = 로봇→목표점 거리
    α   = 로봇 heading 대비 목표점 방향 (조준 오차)
    θ_g = 목표점에서 마커를 정면으로 보는 최종 heading 오차
  두 제어기를 dock_mode 파라미터로 선택 (실기기 A/B 비교 결과 staged 채택):
    A) _ctrl_polar  : Lyapunov 안정 극좌표 제어. 부드러우나 노이즈 심한 마커
                      법선을 고게인 추종 → ω 포화·사행 발생 (실기기에서 확인)
    B) _ctrl_staged : turn→drive→turn 3단계. 위치(안정적인 lateral)는 직진으로,
                      자세는 단계 회전으로 분리. 노이즈 영향 적어 채택.

staged 핵심 보정:
  - 목표 근처(ρ < steer_freeze)에선 α = atan2(Ty,Tx)가 분모·분자 모두 0에
    수렴해 노이즈로 폭발 → 마지막 순간 급조향(머리 틀림) 발생.
    해당 구간은 조향을 끄고 직진만 수행 (lateral 잔차는 수용).

한계 (단일 평면 마커):
  - 정면 근처에서 마커 법선(out-of-plane 회전) 관측성이 낮음 → θ_g 신뢰 제한.
    staged는 안정적인 lateral 위주로 제어해 이 한계를 우회. 더 높은 정밀도가
    필요하면 마커 2개로 자세 삼각측량 권장.

정차 후:
  - waypoints.yaml의 home_key 좌표를 /initialpose 로 직접 발행 (AMCL 리셋)
  - 단일 평면 마커 역산 방식은 yaw 관측성이 낮아 140° 오차 발생 확인 → 폐기
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


ARUCO_DICT   = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()
ARUCO_PARAMS.adaptiveThreshWinSizeMin    = 3
ARUCO_PARAMS.adaptiveThreshWinSizeMax    = 53
ARUCO_PARAMS.adaptiveThreshWinSizeStep   = 5
ARUCO_PARAMS.minMarkerPerimeterRate      = 0.02
ARUCO_PARAMS.errorCorrectionRate         = 0.8


def _norm(a: float) -> float:
    """각도를 [-π, π]로 정규화."""
    return math.atan2(math.sin(a), math.cos(a))


class ArucoHomeDock(Node):

    def __init__(self):
        super().__init__('aruco_home_dock')

        self.declare_parameter('home_key',              'home_robot1')
        self.declare_parameter('target_dist',           0.5)
        self.declare_parameter('max_linear',            0.15)
        self.declare_parameter('max_angular',           0.3)
        self.declare_parameter('yaw_tol',               0.05)   # 최종 자세(θ_g) 허용오차
        self.declare_parameter('timeout_sec',           30.0)
        self.declare_parameter('no_marker_timeout_sec', 5.0)

        # 제어 모드: 'polar'(A 극좌표 자세제어) | 'staged'(B 단계 분리)
        self.declare_parameter('dock_mode',             'polar')
        self.declare_parameter('rho_tol',               0.03)   # 목표점 위치 허용오차
        # A) 극좌표 제어기 게인 (Lyapunov 안정 조건: k_rho>0, k_beta<0, k_alpha+5/3·k_beta-2/π·k_rho>0)
        self.declare_parameter('k_rho',                 0.8)
        self.declare_parameter('k_alpha',               2.0)
        self.declare_parameter('k_beta',               -0.6)
        # B) 단계 제어 게인 + 1단계 정렬 허용오차
        self.declare_parameter('kp_turn',               0.8)    # 제자리 회전 게인
        self.declare_parameter('kp_drive',              0.4)    # 직진 게인
        self.declare_parameter('kp_steer',              0.6)    # 직진 중 조향 게인
        self.declare_parameter('alpha_tol',             0.05)   # 목표 조준 완료 각
        self.declare_parameter('steer_freeze',          0.15)   # 이 거리 이내면 α 조향 정지(목표 근처 α 폭발 방지)

        home_key           = self.get_parameter('home_key').get_parameter_value().string_value
        self._target_dist  = self.get_parameter('target_dist').get_parameter_value().double_value
        self._max_linear   = self.get_parameter('max_linear').get_parameter_value().double_value
        self._max_angular  = self.get_parameter('max_angular').get_parameter_value().double_value
        self._yaw_tol      = self.get_parameter('yaw_tol').get_parameter_value().double_value
        self._timeout      = self.get_parameter('timeout_sec').get_parameter_value().double_value
        self._no_marker_to = self.get_parameter('no_marker_timeout_sec').get_parameter_value().double_value

        self._dock_mode = self.get_parameter('dock_mode').get_parameter_value().string_value
        self._rho_tol   = self.get_parameter('rho_tol').get_parameter_value().double_value
        self._k_rho     = self.get_parameter('k_rho').get_parameter_value().double_value
        self._k_alpha   = self.get_parameter('k_alpha').get_parameter_value().double_value
        self._k_beta    = self.get_parameter('k_beta').get_parameter_value().double_value
        self._kp_turn   = self.get_parameter('kp_turn').get_parameter_value().double_value
        self._kp_drive  = self.get_parameter('kp_drive').get_parameter_value().double_value
        self._kp_steer  = self.get_parameter('kp_steer').get_parameter_value().double_value
        self._alpha_tol    = self.get_parameter('alpha_tol').get_parameter_value().double_value
        self._steer_freeze = self.get_parameter('steer_freeze').get_parameter_value().double_value
        self._phase        = 0   # 단계 제어 상태 (staged 전용)

        markers_file = str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml'
        with open(markers_file) as f:
            data = yaml.safe_load(f)

        home_marker_map   = data.get('home_marker', {})
        self._marker_id   = int(home_marker_map.get(home_key, 0))
        marker_info       = data['markers'].get(str(self._marker_id), {})
        self._marker_size = float(marker_info.get('size', 0.20))

        # AMCL 리셋용 home 좌표 — waypoints.yaml 정본에서 직접 로드
        waypoints_file = str(get_package_share_directory('wego_behaviour')) + '/config/waypoints.yaml'
        with open(waypoints_file) as f:
            waypoints = yaml.safe_load(f)['waypoints']
        home = waypoints[home_key]
        self._home_x   = float(home['x'])
        self._home_y   = float(home['y'])
        self._home_yaw = float(home['yaw'])

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

        # 이전 도킹의 마지막(수렴) 측정값이 남아있으면 첫 루프가 그걸 읽고
        # 즉시 수렴 오판(도킹 안 하고 완료 + stale pose로 AMCL 리셋) → 반드시 비움
        with self._tvec_lock:
            self._latest_tvec = None
            self._latest_rvec = None
        self._docking = True
        self._phase   = 0
        self.get_logger().info(
            f'IBVS 도킹 시작 [{self._dock_mode}] — marker={self._marker_id}, target={self._target_dist}m'
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

                # 도킹 목표점(마커 법선 위 target_dist 지점)의 로봇 기준 기하
                rho, alpha, theta_g = self._compute_geometry(tvec, R_cm)

                # 수렴 판정: 목표점 위치(ρ) + 최종 자세(θ_g) — 모드 공통
                if rho < self._rho_tol and abs(theta_g) < self._yaw_tol:
                    self._cmd_pub.publish(Twist())   # 정차
                    time.sleep(0.1)                  # 완전 정지 대기
                    self._publish_initialpose()      # 정차 후 AMCL 보정
                    self.get_logger().info(
                        f'도킹 완료 [{self._dock_mode}] — depth={depth:.3f}m '
                        f'lateral={lateral:.3f}m yaw={math.degrees(yaw_error):.1f}° '
                        f'(ρ={rho:.3f} θg={math.degrees(theta_g):.1f}°)'
                    )
                    response.success = True
                    response.message = (
                        f'docked depth={depth:.3f} '
                        f'lateral={lateral:.3f} yaw={math.degrees(yaw_error):.1f}deg'
                    )
                    return response

                if self._dock_mode == 'staged':
                    v, w = self._ctrl_staged(rho, alpha, theta_g)
                else:
                    v, w = self._ctrl_polar(rho, alpha, theta_g)

                # 전진만 허용 (후진 시 마커 FOV 이탈 방지)
                v = float(np.clip(v, 0.0, self._max_linear))
                w = float(np.clip(w, -self._max_angular, self._max_angular))

                twist = Twist()
                twist.linear.x  = v
                twist.angular.z = w
                self._cmd_pub.publish(twist)

                self.get_logger().info(
                    f'[{self._dock_mode}] ρ={rho:.3f} α={math.degrees(alpha):.1f}° '
                    f'θg={math.degrees(theta_g):.1f}° (d={depth:.3f} lat={lateral:.3f}) '
                    f'→ v={v:.3f} w={w:.3f}',
                    throttle_duration_sec=0.5,
                )
                time.sleep(0.05)

        finally:
            self._docking = False
            self._cmd_pub.publish(Twist())

    # ── 기하 계산 (모드 공통) ────────────────────────────────────────────

    def _compute_geometry(self, tvec, R_cm):
        """마커 측정 → 도킹 목표점의 로봇 기준 (ρ, α, θ_g).

        도킹 목표점: 마커 법선 위, 마커로부터 target_dist 떨어진(로봇 쪽) 지점.
        - ρ      : 로봇 → 목표점 거리
        - α      : 로봇 heading 대비 목표점 방향 각 (조준 오차)
        - θ_g    : 목표점에서 마커를 정면으로 바라보는 최종 heading 오차
        좌표 변환: 카메라 optical(x=우, y=하, z=전) → 로봇 2D(x=전, y=좌)
        """
        depth   = float(tvec[2])
        lateral = float(tvec[0])
        m_x = depth        # 마커 전방 거리 (로봇 x)
        m_y = -lateral     # 마커 좌우 (로봇 y, 좌+)

        # 마커 법선(마커 z축)을 로봇 2D로: robot_x = cam_z, robot_y = -cam_x
        n_x = R_cm[2][2]
        n_y = -R_cm[0][2]
        n_norm = math.hypot(n_x, n_y) or 1.0
        n_x /= n_norm
        n_y /= n_norm

        # 목표점 = 마커 + target_dist · (로봇 쪽 법선)
        tx = m_x + self._target_dist * n_x
        ty = m_y + self._target_dist * n_y

        rho     = math.hypot(tx, ty)
        alpha   = _norm(math.atan2(ty, tx))     # 목표점 방향 (로봇 기준)
        theta_g = _norm(math.atan2(-n_y, -n_x)) # 목표점에서 마커 향하는 최종 heading
        return rho, alpha, theta_g

    # ── A) 극좌표 자세 제어기 ────────────────────────────────────────────

    def _ctrl_polar(self, rho, alpha, theta_g):
        """Lyapunov 안정 극좌표 제어 (Siegwart 3.6.2.4).

        목표(goal) 프레임 기준 로봇 자세 (x_r, y_r, θ_r)로 변환 후 표준 법칙 적용.
        v = k_ρ·ρ,  ω = k_α·α + k_β·β
        """
        # 목표점의 로봇 기준 좌표
        tx = rho * math.cos(alpha)
        ty = rho * math.sin(alpha)
        cg, sg = math.cos(theta_g), math.sin(theta_g)

        # 로봇 자세를 goal 프레임으로 (goal: 목표점 원점, 마커 향하는 방향이 +x)
        x_r = -( tx * cg + ty * sg)
        y_r = -(-tx * sg + ty * cg)
        theta_r = -theta_g

        rr = math.hypot(x_r, y_r)
        if rr < 1e-3:
            a = _norm(-theta_r)                       # 목표 위 — 자세만 정렬
        else:
            a = _norm(-theta_r + math.atan2(-y_r, -x_r))
        b = _norm(-theta_r - a)

        v = self._k_rho * rr
        w = self._k_alpha * a + self._k_beta * b
        return v, w

    # ── B) 단계 분리 제어 (turn → drive → turn) ─────────────────────────

    def _ctrl_staged(self, rho, alpha, theta_g):
        """LIMO 제자리 회전 활용 3단계: 목표 조준 → 직진 → 마커 정면 정렬."""
        if self._phase == 0:                          # 목표점 조준 (제자리 회전)
            if abs(alpha) < self._alpha_tol:
                self._phase = 1
                return 0.0, 0.0
            return 0.0, self._kp_turn * alpha
        if self._phase == 1:                          # 목표점까지 직진 (+ 조향 유지)
            if rho < self._rho_tol:
                self._phase = 2
                return 0.0, 0.0
            # 목표 근처(ρ<steer_freeze)에선 α가 노이즈로 폭발 → 조향 끄고 직진
            steer = 0.0 if rho < self._steer_freeze else self._kp_steer * alpha
            return self._kp_drive * rho, steer
        # phase 2 — 마커 정면 정렬 (제자리 회전)
        if rho > self._rho_tol * 2.0:                 # 정렬 중 위치 이탈 시 직진 복귀
            self._phase = 1
            return 0.0, 0.0
        return 0.0, self._kp_turn * theta_g

    # ── AMCL 리셋 ───────────────────────────────────────────────────────

    def _publish_initialpose(self) -> None:
        """도킹 완료 후 waypoints.yaml의 home 좌표를 /initialpose 로 직접 발행.

        단일 평면 마커 역산 방식은 yaw 관측성 한계로 140° 오차 발생 확인(실기기).
        IBVS 도킹이 성공했으면 로봇은 반드시 home 위치에 있으므로 직접 발행이 정확.
        """
        msg = PoseWithCovarianceStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x    = self._home_x
        msg.pose.pose.position.y    = self._home_y
        msg.pose.pose.orientation.z = math.sin(self._home_yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(self._home_yaw / 2.0)
        msg.pose.covariance[0]  = 0.05
        msg.pose.covariance[7]  = 0.05
        msg.pose.covariance[35] = 0.05

        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f'[AMCL 리셋] x={self._home_x:.3f} y={self._home_y:.3f} '
            f'yaw={math.degrees(self._home_yaw):.1f}°'
        )


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
