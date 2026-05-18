# TTS 전용 음성 노드 — wakeword/VAD/STT/NLU 파이프라인 제거 (DEC-024)
#
# 역할: /speak_text 구독 → edge-tts + mpg123으로 음성 출력
# 목적지 입력은 태블릿 방문자 UI → FastAPI → wego_dispatcher가 담당하므로
# 이 노드는 발화 출력만 책임진다.

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .tts import TTS


class VoiceNode(Node):
    def __init__(self):
        super().__init__('voice_node')

        self.declare_parameter('tts_voice', 'ko-KR-SunHiNeural')
        self.declare_parameter('audio_device', 'plughw:1,3')

        self._tts = TTS(
            voice=self.get_parameter('tts_voice').value,
            audio_device=self.get_parameter('audio_device').value,
        )

        self.create_subscription(String, '/speak_text', self._speak_cb, 10)

        self.get_logger().info('TTS 노드 준비 완료 — /speak_text 대기 중')

    def _speak_cb(self, msg: String) -> None:
        self.get_logger().info(f'TTS 발화: "{msg.data}"')
        # speak()는 블로킹 — 재생 완료까지 다음 메시지를 처리하지 않음
        self._tts.speak(msg.data)


def main():
    rclpy.init()
    node = VoiceNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
