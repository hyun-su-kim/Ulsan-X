import asyncio
import os
import subprocess
import tempfile

import edge_tts

# ko-KR-SunHiNeural: Microsoft Neural TTS 한국어 여성 음성
# 인터넷 연결 필요 — edge-tts가 Microsoft 서버에서 오디오 스트림을 받아옴
DEFAULT_VOICE = 'ko-KR-SunHiNeural'
# PulseAudio 싱크 이름. mpg123 -o pulse + PULSE_SINK로 이 싱크에 직접 출력한다.
# 로봇 빌트인 디스플레이의 HDMI 오디오 싱크(Jetson Orin NX). `pactl list short sinks`로 확인.
# (구: ALSA 직접 'plughw:1,3' → PulseAudio가 장치를 점유한 그래픽 세션에서 무음 → pulse 경유로 전환)
DEFAULT_PULSE_SINK = 'alsa_output.platform-3510000.hda.hdmi-stereo'


class TTS:
    """edge-tts 기반 한국어 음성 출력 클래스.

    speak() 호출 시 텍스트를 MP3로 변환한 뒤 mpg123으로 재생.
    재생이 완전히 끝날 때까지 블로킹 → pipeline 스레드가 TTS 중 다음 단계로 넘어가지 않음.

    사전 조건:
        - pip install edge-tts (wego_venv)
        - sudo apt install mpg123
    """

    def __init__(self, voice: str = DEFAULT_VOICE, pulse_sink: str = DEFAULT_PULSE_SINK):
        self._voice = voice
        self._pulse_sink = pulse_sink

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

            # -o pulse: PulseAudio 경유 출력(-q: quiet). ALSA 직접(-a)은 pulse가 장치를
            # 점유한 그래픽 세션에서 무음이 됨. PULSE_SINK로 특정 싱크를 고정해 기본 싱크
            # 변경/재부팅에 영향받지 않게 한다(실행 전 pactl set-default-sink 불요).
            env = os.environ.copy()
            if self._pulse_sink:
                env['PULSE_SINK'] = self._pulse_sink
            subprocess.run(['mpg123', '-q', '-o', 'pulse', tmp_path], check=True, env=env)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
