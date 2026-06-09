# wego_dispatcher 노드
#
# 역할: 태블릿(FastAPI)과 ROS 로봇 사이의 임무 중계
#
# 구독:
#   /limo1/robot_status (domain 5, wego_bridge가 domain 6에서 브릿징)
#   /limo2/robot_status (domain 5, wego_bridge가 domain 7에서 브릿징)
#     → 상태 변경 시 POST /robots/{id}/status → FastAPI in-memory 업데이트
#
# 발행:
#   /limo1/goal_destination (domain 5 → wego_bridge → domain 6)
#   /limo2/goal_destination (domain 5 → wego_bridge → domain 7)
#   /limo1/speak_text       (domain 5 → wego_bridge → domain 6)
#   /limo2/speak_text       (domain 5 → wego_bridge → domain 7)
#
# 폴링 (0.5초 간격):
#   GET /assign/pending → PENDING 미션 조회
#     → IDLE 로봇에 goal_destination + speak_text 발행
#     → PATCH /assign/{id}/start 호출 (PENDING → ACTIVE)
#
# 완료 감지 (1초 간격):
#   ACTIVE 미션의 배정 로봇이 IDLE로 복귀하면
#     → PATCH /assign/{id}/complete 호출 (ACTIVE → COMPLETED)

import os
import threading
import time

import requests
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from limo_msgs.msg import GuideGoal
from diagnostic_updater import Updater
from diagnostic_msgs.msg import DiagnosticStatus

# FastAPI 서버 주소 — 환경변수 FASTAPI_URL로 오버라이드 가능
# 예) export FASTAPI_URL=http://192.168.0.XXX:8000
API_BASE = os.environ.get('FASTAPI_URL', 'http://localhost:8000')

POLL_INTERVAL   = 0.5   # PENDING 미션 폴링 간격 (초)
STATUS_INTERVAL = 1.0   # 완료 감지 폴링 간격 (초)

ROBOTS = ("limo1", "limo2")


class DispatcherNode(Node):
    def __init__(self):
        super().__init__('wego_dispatcher')

        self.declare_parameter('api_base', API_BASE)
        self._api = self.get_parameter('api_base').get_parameter_value().string_value

        # 두 로봇의 현재 상태 (domain 5에서 본 상태)
        # wego_bridge가 /limo1/robot_status (domain 6→5)를 이미 브릿징하므로
        # 이 노드는 domain 5에서 /limo1/robot_status를 바로 구독한다.
        self._robot_status: dict[str, str] = {"limo1": "IDLE", "limo2": "IDLE"}

        # 현재 처리 중인 ACTIVE 미션 추적 {mission_id: robot}
        self._active_missions: dict[int, str] = {}
        # 로봇이 non-IDLE로 전환된 것이 확인된 미션 — 출발 전 IDLE을 완료로 오인하는 것을 막음
        self._departed: set[int] = set()
        # FAILED 상태를 거친 미션 — IDLE 복귀 시 /complete 대신 /fail 호출
        self._failed: set[int] = set()
        self._lock = threading.Lock()
        self._api_ok = False  # 마지막 FastAPI 폴링 성공 여부 — diagnostics 보고용

        # /diagnostics 발행 — GUI 시스템 상태 패널에서 연결 확인용
        self._diag_updater = Updater(self)
        self._diag_updater.setHardwareID('wego_dispatcher')
        self._diag_updater.add('wego_dispatcher', self._diag_check)

        # 상태 구독
        self.create_subscription(String, '/limo1/robot_status', self._status_cb('limo1'), 10)
        self.create_subscription(String, '/limo2/robot_status', self._status_cb('limo2'), 10)

        # 목적지+TTS를 한 메시지(GuideGoal)로 발행 — behaviour가 발화 후 주행하도록 동기화.
        # (출발 안내는 더 이상 voice로 직접 보내지 않음 — behaviour가 GuideGoal.tts_text로 발화)
        self._goal_pubs = {
            robot: self.create_publisher(GuideGoal, f'/{robot}/goal_destination', 10)
            for robot in ROBOTS
        }

        # 폴링 타이머
        self.create_timer(POLL_INTERVAL,   self._poll_pending)
        self.create_timer(STATUS_INTERVAL, self._check_completions)

        self.get_logger().info(f'wego_dispatcher 시작 — API: {self._api}')

    def _diag_check(self, stat: DiagnosticStatus) -> DiagnosticStatus:
        if self._api_ok:
            stat.summary(DiagnosticStatus.OK, '정상 동작 중')
        else:
            stat.summary(DiagnosticStatus.ERROR, 'FastAPI 연결 끊김')
        return stat

    def _status_cb(self, robot: str):
        """클로저로 로봇별 구독 콜백 생성."""
        def cb(msg: String) -> None:
            new_status = msg.data
            old_status = self._robot_status.get(robot)
            if old_status != new_status:
                self._robot_status[robot] = new_status
                self.get_logger().info(f'{robot} 상태: {old_status} → {new_status}')
                # 로봇이 non-IDLE로 전환 → 출발 확인으로 마킹
                # FAILED 진입 → 실패 마킹 (IDLE 복귀 시 /fail로 분기)
                if new_status != "IDLE":
                    with self._lock:
                        for mid, r in self._active_missions.items():
                            if r == robot:
                                self._departed.add(mid)
                                if new_status == "FAILED":
                                    self._failed.add(mid)
                # FastAPI in-memory 상태 동기화
                try:
                    requests.post(
                        f'{self._api}/robots/{robot}/status',
                        json={'status': new_status},
                        timeout=1.0,
                    )
                except Exception as e:
                    self.get_logger().warn(f'상태 업데이트 실패: {e}')
        return cb

    def _poll_pending(self) -> None:
        """PENDING 미션을 조회하고 IDLE 로봇에 배정한다."""
        try:
            resp = requests.get(f'{self._api}/assign/pending', timeout=1.0)
            if resp.status_code != 200:
                self._api_ok = False
                return
            missions = resp.json()
            self._api_ok = True
        except Exception:
            self._api_ok = False
            return

        for mission in missions:
            mission_id = mission['id']

            with self._lock:
                # 이미 처리 중인 미션은 스킵
                if mission_id in self._active_missions:
                    continue

                robot = self._pick_idle_robot()
                if not robot:
                    self.get_logger().warn('IDLE 로봇 없음 — 미션 대기')
                    break

                # 즉시 ACTIVE로 마킹 (중복 처리 방지)
                self._active_missions[mission_id] = robot

            self._dispatch(mission, robot)

    def _dispatch(self, mission: dict, robot: str) -> None:
        """선택된 로봇에 goal과 TTS를 발행하고 FastAPI에 ACTIVE 상태를 전달한다."""
        mission_id  = mission['id']
        destination = mission['destination']
        tts_text    = mission['tts_text']

        # GuideGoal(목적지+tts) 발행 → wego_bridge → wego_behaviour FSM
        # behaviour가 출발 시 tts를 발화-완료대기-주행 순으로 처리(발화 중 주행 방지)
        goal_msg = GuideGoal()
        goal_msg.destination = destination
        goal_msg.tts_text    = tts_text
        self._goal_pubs[robot].publish(goal_msg)

        self.get_logger().info(
            f'[{mission_id}] {robot} → {destination} | TTS: "{tts_text}"'
        )

        # FastAPI PENDING → ACTIVE
        try:
            requests.patch(
                f'{self._api}/assign/{mission_id}/start',
                params={'robot': robot},
                timeout=1.0,
            )
        except Exception as e:
            self.get_logger().warn(f'start PATCH 실패: {e}')

    def _check_completions(self) -> None:
        """ACTIVE 미션의 로봇이 IDLE로 복귀했는지 확인한다.
        출발 확인(non-IDLE 전환)이 없는 미션은 스킵 — 출발 전 IDLE 오인 방지."""
        with self._lock:
            completed = [
                mid for mid, robot in self._active_missions.items()
                if mid in self._departed and self._robot_status.get(robot) == "IDLE"
            ]

        for mission_id in completed:
            with self._lock:
                robot = self._active_missions.pop(mission_id, None)
                self._departed.discard(mission_id)
                is_failed = mission_id in self._failed
                self._failed.discard(mission_id)
            if robot is None:
                continue

            endpoint = 'fail' if is_failed else 'complete'
            self.get_logger().info(
                f'[{mission_id}] {robot} 홈 복귀 확인 → {endpoint.upper()}'
            )
            try:
                requests.patch(
                    f'{self._api}/assign/{mission_id}/{endpoint}',
                    timeout=1.0,
                )
            except Exception as e:
                self.get_logger().warn(f'{endpoint} PATCH 실패: {e}')

    def _pick_idle_robot(self) -> str | None:
        """limo1 우선으로 IDLE 로봇 반환. 호출 전 _lock 보유 필요."""
        for robot in ROBOTS:
            if self._robot_status.get(robot) == "IDLE":
                # 이미 다른 미션에 배정된 로봇은 제외
                if robot not in self._active_missions.values():
                    return robot
        return None


def main():
    rclpy.init()
    node = DispatcherNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
