import queue
import pyaudio

SAMPLE_RATE = 16000
CHUNK_MS = 20  # webrtcvad 지원 단위: 10, 20, 30 ms
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)  # 320 samples


class AudioStream:
    def __init__(self):
        self._q: queue.Queue[bytes] = queue.Queue()
        self._pa = pyaudio.PyAudio()
        self._stream = None

    def start(self) -> None:
        self._stream = self._pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SAMPLES,
            stream_callback=self._cb,
        )
        self._stream.start_stream()

    def _cb(self, in_data, frame_count, time_info, status):
        self._q.put(in_data)
        return (None, pyaudio.paContinue)

    def read(self, timeout: float = 0.1) -> bytes:
        return self._q.get(timeout=timeout)

    def flush(self) -> None:
        """큐에 쌓인 오디오 프레임을 전부 버림.

        TTS 재생 중 마이크가 계속 캡처한 에코 음성을 제거하기 위해
        TTS speak() 완료 직후 호출한다.
        """
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def stop(self) -> None:
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._pa.terminate()
