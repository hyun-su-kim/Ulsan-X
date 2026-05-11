import asyncio
import os
import subprocess
import tempfile

import edge_tts

# ko-KR-SunHiNeural: Microsoft Neural TTS 한국어 여성 음성
# 인터넷 연결 필요 — edge-tts가 Microsoft 서버에서 오디오 스트림을 받아옴
DEFAULT_VOICE = 'ko-KR-SunHiNeural'


class TTS:
    """edge-tts 기반 한국어 음성 출력 클래스.

    speak() 호출 시 텍스트를 MP3로 변환한 뒤 mpg123으로 재생.
    재생이 완전히 끝날 때까지 블로킹 → pipeline 스레드가 TTS 중 다음 단계로 넘어가지 않음.

    사전 조건:
        - pip install edge-tts (wego_venv)
        - sudo apt install mpg123
    """

    def __init__(self, voice: str = DEFAULT_VOICE):
        self._voice = voice

    def speak(self, text: str) -> None:
        """텍스트를 음성으로 출력. 재생 완료까지 블로킹.

        asyncio.run()으로 비동기 루틴을 동기 컨텍스트(pipeline 스레드)에서 실행.
        예외 발생 시 조용히 무시 — TTS 실패가 파이프라인 전체를 중단시키지 않도록.
        """
        try:
            asyncio.run(self._async_speak(text))
        except Exception:
            # 네트워크 단절, mpg123 미설치 등 — 로봇 안내는 계속 진행
            pass

    async def _async_speak(self, text: str) -> None:
        """edge-tts로 MP3 생성 → mpg123으로 재생 → 임시 파일 삭제."""
        tmp_path = None
        try:
            # 임시 MP3 파일 경로 확보 (delete=False: 직접 관리)
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                tmp_path = f.name

            # Microsoft Neural TTS 서버에서 오디오 수신 후 파일로 저장
            communicate = edge_tts.Communicate(text, self._voice)
            await communicate.save(tmp_path)

            # -q: quiet 모드 (mpg123 출력 억제)
            subprocess.run(['mpg123', '-q', tmp_path], check=True)

        finally:
            # 재생 성공/실패 무관하게 임시 파일 정리
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
