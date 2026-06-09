# TTS 전용 음성 노드 — wakeword/VAD/STT/NLU 파이프라인 제거 (DEC-024)
#
# 역할: /speak_text 구독 → edge-tts + mpg123으로 음성 출력
# 목적지 입력은 태블릿 방문자 UI → FastAPI → wego_dispatcher가 담당하므로
# 이 노드는 발화 출력만 책임진다.

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from std_msgs.msg import String
from limo_msgs.srv import Speak
from diagnostic_updater import Updater
from diagnostic_msgs.msg import DiagnosticStatus

from .tts import TTS


class VoiceNode(Node):
    def __init__(self):
        super().__init__('voice_node')

        self.declare_parameter('tts_voice', 'ko-KR-SunHiNeural')
        self.declare_parameter('pulse_sink', 'alsa_output.platform-3510000.hda.hdmi-stereo')

        self._pulse_sink = self.get_parameter('pulse_sink').value
        self._tts = TTS(
            voice=self.get_parameter('tts_voice').value,
            pulse_sink=self._pulse_sink,
        )

        # 발화 콜백(블로킹)은 전용 MutuallyExclusive 그룹에 둔다 →
        #   ① 두 발화 입구(/speak_text·/speak)가 동시에 오디오 장치를 잡는 충돌 방지(직렬화)
        #   ② 진단 타이머(기본 그룹)와는 분리 → MultiThreadedExecutor가 발화 블로킹 중에도
        #      하트비트(/diagnostics)를 다른 스레드에서 계속 발행 → '음성(TTS)' 행 깜빡임 제거
        self._speak_group = MutuallyExclusiveCallbackGroup()

        # /speak_text: 비동기 발화(도착·실패 등 — 호출자가 완료를 기다리지 않음)
        self.create_subscription(String, '/speak_text', self._speak_cb, 10,
                                 callback_group=self._speak_group)
        # /speak 서비스: 발화 완료 후 응답 — behaviour가 '발화 후 출발' 동기화에 사용
        self.create_service(Speak, '/speak', self._speak_srv_cb,
                            callback_group=self._speak_group)

        # /diagnostics 발행 — GUI 시스템 상태 패널 '음성(TTS)' liveness 판정용(1Hz)
        # 브릿지가 /diagnostics → /ROBOT_NAME/diagnostics로 도메인 6/7→5 전달
        # (기본 콜백 그룹 → 발화 그룹과 별개 스레드에서 동작)
        self._diag = Updater(self)
        self._diag.setHardwareID('wego_voice')
        self._diag.add('wego_voice', self._diag_check)

        self.get_logger().info(
            f'TTS 노드 준비 완료 — pulse_sink={self._pulse_sink}, /speak_text 대기 중')

    def _diag_check(self, stat: DiagnosticStatus) -> DiagnosticStatus:
        stat.summary(DiagnosticStatus.OK, 'TTS 준비')
        return stat

    def _speak_cb(self, msg: String) -> None:
        self.get_logger().info(f'TTS 발화: "{msg.data}"')
        # speak()는 블로킹 — 재생 완료까지 다음 메시지를 처리하지 않음
        # 실패(edge-tts 네트워크/mpg123 pulse 싱크 등)를 ROS 로거로 표면화 → 원인 진단.
        # 발화 실패가 안내 진행을 막지 않도록 콜백은 정상 반환.
        try:
            self._tts.speak(msg.data)
        except Exception as e:
            self.get_logger().error(f'TTS 재생 실패: {e}')

    def _speak_srv_cb(self, request: Speak.Request, response: Speak.Response) -> Speak.Response:
        # 발화가 끝난 뒤 응답 → 호출자(behaviour)가 완료를 동기적으로 기다린다.
        self.get_logger().info(f'TTS 발화(서비스): "{request.text}"')
        try:
            self._tts.speak(request.text)
            response.success = True
        except Exception as e:
            self.get_logger().error(f'TTS 재생 실패: {e}')
            response.success = False
        return response


def main():
    rclpy.init()
    node = VoiceNode()
    # MultiThreadedExecutor — 발화 콜백이 블로킹해도 진단 타이머가 다른 스레드에서 계속 발행
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
