import asyncio
import os
import subprocess
import tempfile

import edge_tts

# ko-KR-SunHiNeural: Microsoft Neural TTS 한국어 여성 음성
# 인터넷 연결 필요 — edge-tts가 Microsoft 서버에서 오디오 스트림을 받아옴
DEFAULT_VOICE = 'ko-KR-SunHiNeural'
DEFAULT_AUDIO_DEVICE = 'plughw:1,3'  # HDMI 0 (Jetson Orin NX HDA, card 1, device 3)


class TTS:
    """edge-tts 기반 한국어 음성 출력 클래스.

    speak() 호출 시 텍스트를 MP3로 변환한 뒤 mpg123으로 재생.
    재생이 완전히 끝날 때까지 블로킹 → pipeline 스레드가 TTS 중 다음 단계로 넘어가지 않음.

    사전 조건:
        - pip install edge-tts (wego_venv)
        - sudo apt install mpg123
    """

    def __init__(self, voice: str = DEFAULT_VOICE, audio_device: str = DEFAULT_AUDIO_DEVICE):
        self._voice = voice
        self._audio_device = audio_device

    def speak(self, text: str) -> None:
        """텍스트를 음성으로 출력. 재생 완료까지 블로킹.

        실패(네트워크 단절·mpg123 에러 등)는 **예외로 전파**한다 — 호출자(voice_node)가
        ROS 로거로 표면화하기 위함. (과거: 파이썬 logging으로 삼켜 ROS 콘솔에 안 보였음)
        """
        asyncio.run(self._async_speak(text))

    async def _async_speak(self, text: str) -> None:
        """edge-tts로 MP3 생성 → mpg123으로 재생 → 임시 파일 삭제."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                tmp_path = f.name

            communicate = edge_tts.Communicate(text, self._voice)
            await communicate.save(tmp_path)

            # -a: ALSA 출력 장치 지정, -q: quiet 모드
            subprocess.run(['mpg123', '-q', '-a', self._audio_device, tmp_path], check=True)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
