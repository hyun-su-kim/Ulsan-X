import requests
from PyQt5.QtCore import QThread, pyqtSignal


class HttpGetThread(QThread):
    """공통 HTTP GET 백그라운드 스레드.

    성공: requests.Response 객체 emit
    실패(네트워크 오류 / non-2xx): None emit
    """
    done = pyqtSignal(object)

    def __init__(self, url: str, timeout: float = 3.0):
        super().__init__()
        self._url = url
        self._timeout = timeout

    def run(self) -> None:
        try:
            r = requests.get(self._url, timeout=self._timeout)
            self.done.emit(r if r.ok else None)
        except Exception:
            self.done.emit(None)
