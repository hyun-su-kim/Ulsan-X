import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import Empty, String

# wego_behaviour가 발행하는 상태값 중 주행 중인 상태
ACTIVE_STATES = {'BUSY', 'RETURNING', 'WAITING'}


class TrafficNode(Node):
    STALE_SEC = 2.0  # amcl_pose 수신 없으면 데이터 무효 처리

    def __init__(self):
        super().__init__('wego_traffic')

        self.declare_parameter('pause_dist',  0.7)
        self.declare_parameter('resume_dist', 1.0)
        self._pause_dist  = self.get_parameter('pause_dist').get_parameter_value().double_value
        self._resume_dist = self.get_parameter('resume_dist').get_parameter_value().double_value

        self._pose:           dict[str, PoseWithCovarianceStamped | None] = {'limo1': None, 'limo2': None}
        self._status:         dict[str, str]   = {'limo1': 'IDLE', 'limo2': 'IDLE'}
        self._last_pose_time: dict[str, float] = {'limo1': 0.0,    'limo2': 0.0}
        self._paused_robot:   str | None = None

        self.create_subscription(PoseWithCovarianceStamped, '/limo1/amcl_pose',
                                 lambda m: self._pose_cb('limo1', m), 1)
        self.create_subscription(PoseWithCovarianceStamped, '/limo2/amcl_pose',
                                 lambda m: self._pose_cb('limo2', m), 1)
        self.create_subscription(String, '/limo1/robot_status',
                                 lambda m: self._status_cb('limo1', m), 10)
        self.create_subscription(String, '/limo2/robot_status',
                                 lambda m: self._status_cb('limo2', m), 10)

        self._pause_pub  = {r: self.create_publisher(Empty, f'/{r}/pause',  10) for r in ('limo1', 'limo2')}
        self._resume_pub = {r: self.create_publisher(Empty, f'/{r}/resume', 10) for r in ('limo1', 'limo2')}

        self.create_timer(0.2, self._tick)  # 5 Hz
        self.get_logger().info(
            f'wego_traffic 시작  pause={self._pause_dist}m  resume={self._resume_dist}m'
        )

    def _pose_cb(self, robot: str, msg: PoseWithCovarianceStamped) -> None:
        self._pose[robot] = msg
        self._last_pose_time[robot] = self.get_clock().now().nanoseconds * 1e-9

    def _status_cb(self, robot: str, msg: String) -> None:
        prev = self._status[robot]
        self._status[robot] = msg.data
        if prev != msg.data:
            self.get_logger().info(f'{robot} 상태: {prev} → {msg.data}')

    # ──────────────────────────────────────────────────────────────────
    def _tick(self) -> None:
        now = self.get_clock().now().nanoseconds * 1e-9

        for r in ('limo1', 'limo2'):
            if self._pose[r] is None:
                return
            if now - self._last_pose_time[r] > self.STALE_SEC:
                self.get_logger().warn(f'{r} amcl_pose 오래됨 — 스킵', throttle_duration_sec=5.0)
                return

        s1, s2 = self._status['limo1'], self._status['limo2']

        # 둘 중 하나라도 IDLE이면 개입 안 함
        if s1 not in ACTIVE_STATES or s2 not in ACTIVE_STATES:
            if self._paused_robot is not None:
                self._do_resume(self._paused_robot)
            return

        dist = self._distance()

        if self._paused_robot is None:
            if dist < self._pause_dist:
                self._do_pause(self._lower_priority(s1, s2))
        else:
            if dist > self._resume_dist:
                self._do_resume(self._paused_robot)

    def _distance(self) -> float:
        p1 = self._pose['limo1'].pose.pose.position
        p2 = self._pose['limo2'].pose.pose.position
        return math.hypot(p1.x - p2.x, p1.y - p2.y)

    def _lower_priority(self, s1: str, s2: str) -> str:
        """pause 대상 로봇 반환. BUSY(GUIDING) > RETURNING > WAITING. 동순위면 limo2."""
        priority = {'BUSY': 2, 'RETURNING': 1, 'WAITING': 0}
        if priority.get(s1, 0) > priority.get(s2, 0):
            return 'limo2'
        if priority.get(s2, 0) > priority.get(s1, 0):
            return 'limo1'
        return 'limo2'  # 동순위: limo1 우선

    def _do_pause(self, robot: str) -> None:
        self._pause_pub[robot].publish(Empty())
        self._paused_robot = robot
        other = 'limo2' if robot == 'limo1' else 'limo1'
        self.get_logger().info(
            f'[PAUSE] {robot} 정지 '
            f'(거리={self._distance():.2f}m, {other}={self._status[other]})'
        )

    def _do_resume(self, robot: str) -> None:
        self._resume_pub[robot].publish(Empty())
        self._paused_robot = None
        self.get_logger().info(f'[RESUME] {robot} 재개 (거리={self._distance():.2f}m)')


def main(args=None):
    rclpy.init(args=args)
    node = TrafficNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
