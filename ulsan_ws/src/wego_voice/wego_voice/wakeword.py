import numpy as np
from openwakeword.model import Model

SAMPLE_RATE = 16000


class WakeWordDetector:
    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.7):
        self._model = Model(wakeword_models=[model_name])
        self._threshold = threshold

    def process(self, frame: bytes) -> bool:
        """20ms 프레임을 바로 openWakeWord에 전달. 모델이 내부적으로 컨텍스트 관리."""
        chunk = np.frombuffer(frame, dtype=np.int16)
        prediction = self._model.predict(chunk)
        score = float(max(prediction.values(), default=0.0))
        return score >= self._threshold
