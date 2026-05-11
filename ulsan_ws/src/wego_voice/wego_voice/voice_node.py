import queue
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from .audio_stream import AudioStream, CHUNK_MS
from .vad import VAD
from .wakeword import WakeWordDetector
from .stt import WhisperSTT
from .nlu import extract_destination, load_waypoints
from .tts import TTS

POST_WAKEWORD_DISCARD_SEC = 0.1  # 웨이크워드 직후 버릴 구간 (웨이크워드 오디오 제거)
MAX_SPEECH_SEC = 10.0            # 최대 발화 수집 시간
SILENCE_SEC = 1.5                # 이 시간만큼 침묵이 지속되면 발화 종료로 판단


class VoiceNode(Node):
    def __init__(self):
        super().__init__('voice_node')

        self.declare_parameter('wakeword_model', 'hey_jarvis')
        self.declare_parameter('wakeword_threshold', 0.5)
        self.declare_parameter('vad_aggressiveness', 2)
        self.declare_parameter('whisper_model_size', 'small')
        self.declare_parameter('whisper_compute_type', 'int8_float16')
        self.declare_parameter('tts_voice', 'ko-KR-SunHiNeural')

        self._on_duty = True
        self._navigating = False
        self.create_subscription(Bool, '/on_duty', self._on_duty_cb, 10)
        self.create_subscription(String, '/speak_text', self._on_speak_text_cb, 10)
        self._goal_pub = self.create_publisher(String, '/goal_destination', 10)

        self.get_logger().info('모델 로딩 중...')
        self._audio = AudioStream()
        self._vad = VAD(self.get_parameter('vad_aggressiveness').value)
        self._wakeword = WakeWordDetector(
            self.get_parameter('wakeword_model').value,
            self.get_parameter('wakeword_threshold').value,
        )
        self._stt = WhisperSTT(
            self.get_parameter('whisper_model_size').value,
            compute_type=self.get_parameter('whisper_compute_type').value,
        )
        self._waypoints = load_waypoints()
        self.get_logger().info(f'목적지 {len(self._waypoints)}개 로드 완료')
        self._tts = TTS(voice=self.get_parameter('tts_voice').value)

        self._pipeline_thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._audio.start()
        self._pipeline_thread.start()
        self.get_logger().info('음성 파이프라인 시작')

    def _on_duty_cb(self, msg: Bool) -> None:
        self._on_duty = msg.data
        self.get_logger().info(f'on_duty → {msg.data}')

    def _on_speak_text_cb(self, msg: String) -> None:
        self._tts.speak(msg.data)
        self._audio.flush()
        self._navigating = False
        self.get_logger().info('네비게이션 완료 — 음성 파이프라인 재개')

    def _run(self) -> None:
        silence_limit = int(SILENCE_SEC * 1000 / CHUNK_MS)
        discard_chunks = int(POST_WAKEWORD_DISCARD_SEC * 1000 / CHUNK_MS)
        max_chunks = int(MAX_SPEECH_SEC * 1000 / CHUNK_MS)

        # 시작 직후 2초 워밍업 — 모델 내부 버퍼 안정화                              
        for _ in range(int(2000 / CHUNK_MS)):                                       
            try:                                                                    
                self._audio.read(timeout=0.1)                                       
            except queue.Empty:                                                   
                pass                                                                
                                                            
        while rclpy.ok():
            # ── 1. 오디오 읽기 ──────────────────────────────────────
            try:
                frame = self._audio.read(timeout=0.1)
            except queue.Empty:
                continue

            # ── 2. on_duty 게이트: 담당 아니면 차단 ─────────────────
            if not self._on_duty:
                continue

            # ── 3. 네비게이션 중: 프레임 버리고 대기 ────────────────
            if self._navigating:
                continue

            # ── 4. 웨이크워드 감지 ───────────────────────────────────
            if not self._wakeword.process(frame):
                continue

            self.get_logger().info('웨이크워드 감지 — 발화 수집 시작')

            # ── 4-1. 안내 멘트 출력 ──────────────────────────────────
            # TTS 재생 중에는 마이크가 로봇 목소리를 줍지 않도록
            # 재생이 완전히 끝난 뒤(블로킹) 발화 수집을 시작함
            self._tts.speak('어디로 안내해드릴까요?')
            self._audio.flush()  # TTS 재생 중 쌓인 에코 오디오 제거

            # ── 5. 웨이크워드 직후 구간 버림 ────────────────────────
            for _ in range(discard_chunks):
                try:
                    self._audio.read(timeout=0.05)
                except queue.Empty:
                    break

            # ── 6. 발화 구간 수집 ────────────────────────────────────
            speech_frames: list[bytes] = []
            silence_count = 0
            for _ in range(max_chunks):
                try:
                    frame = self._audio.read(timeout=0.1)
                except queue.Empty:
                    break
                speech_frames.append(frame)
                if self._vad.is_speech(frame):
                    silence_count = 0
                else:
                    silence_count += 1
                    if silence_count >= silence_limit and len(speech_frames) > silence_limit:
                        break

            if not speech_frames:
                continue

            # ── 7. STT ───────────────────────────────────────────────
            text = self._stt.transcribe(speech_frames)
            self.get_logger().info(f'STT 결과: "{text}"')

            # ── 8. NLU → /goal_destination 발행 ─────────────────────
            # self._waypoints를 전달해 키워드 매핑 실패 시 Gemini fallback 활성화
            dest = extract_destination(text, self._waypoints)
            if dest and dest in self._waypoints:
                self.get_logger().info(f'목적지 확정: {dest}')

                # waypoints.yaml의 label 필드로 자연스러운 한국어 안내
                # 예: classroom_1 → "1강의실로 안내해드릴게요."
                label = self._waypoints[dest].get('label', dest)
                self._tts.speak(f'{label}로 안내해드릴게요.')
                self._audio.flush()

                self._navigating = True
                msg = String()
                msg.data = dest
                self._goal_pub.publish(msg)
                self.get_logger().info('네비게이션 시작 — 음성 파이프라인 일시 정지')
            else:
                self.get_logger().warn(f'목적지 매핑 실패: "{text}"')
                self._tts.speak('죄송합니다, 다시 말씀해 주시겠어요?')
                self._audio.flush()

    def destroy_node(self) -> None:
        self._audio.stop()
        super().destroy_node()


def main():
    rclpy.init()
    node = VoiceNode()
    node.start()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
