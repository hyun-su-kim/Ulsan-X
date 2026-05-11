import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000


class WhisperSTT:
    def __init__(self, model_size: str = "small", device: str = "cuda",
                 compute_type: str = "int8_float16"):
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_frames: list[bytes]) -> str:
        """bytes 프레임 리스트를 float32 numpy 배열로 변환 후 Whisper 추론."""
        raw = np.frombuffer(b"".join(audio_frames), dtype=np.int16)
        audio = raw.astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(
            audio,
            language="ko",
            beam_size=1,
            initial_prompt="강의실 상담실 집중상담실 카운터 멀티룸 회의실 안내해줘",
        )
        return "".join(seg.text for seg in segments).strip()
