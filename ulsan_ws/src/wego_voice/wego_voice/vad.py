import webrtcvad

SAMPLE_RATE = 16000


class VAD:
    def __init__(self, aggressiveness: int = 2):
        # aggressiveness: 0(관대) ~ 3(엄격). 높을수록 소음에 민감하게 차단.
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes) -> bool:
        return self._vad.is_speech(frame, SAMPLE_RATE)
