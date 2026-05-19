from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeyEvent


class LoginView(QWidget):
    """PIN 입력 로그인 화면. 키보드(숫자키, BackSpace, Enter) 지원."""

    MAX_LEN = 4

    def __init__(self, correct_pin: str, on_success):
        super().__init__()
        self._correct_pin = correct_pin
        self._on_success  = on_success
        self._entered     = ''

        self.setStyleSheet('background:#0f172a;')
        self.setFocusPolicy(Qt.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        box = QFrame()
        box.setFixedWidth(340)
        box.setStyleSheet(
            'background:#1e293b; border:1px solid #334155;'
            'border-radius:16px;'
        )
        outer.addWidget(box, alignment=Qt.AlignCenter)

        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(36, 40, 36, 40)
        vbox.setSpacing(0)
        vbox.setAlignment(Qt.AlignCenter)

        # 로고
        logo = QLabel('🤖 wego')
        logo.setFont(QFont('Segoe UI', 22, QFont.Bold))
        logo.setStyleSheet('color:#60a5fa; border:none;')
        logo.setAlignment(Qt.AlignCenter)
        vbox.addWidget(logo)

        sub = QLabel('관제 대시보드')
        sub.setFont(QFont('Segoe UI', 11))
        sub.setStyleSheet('color:#64748b; border:none;')
        sub.setAlignment(Qt.AlignCenter)
        vbox.addWidget(sub)

        vbox.addSpacing(24)

        # PIN 점 표시
        dot_row = QHBoxLayout()
        dot_row.setAlignment(Qt.AlignCenter)
        dot_row.setSpacing(14)
        self._dots: list[QLabel] = []
        for _ in range(self.MAX_LEN):
            dot = QLabel()
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(
                'border-radius:7px; border:2px solid #475569; background:transparent;'
            )
            self._dots.append(dot)
            dot_row.addWidget(dot)
        vbox.addLayout(dot_row)

        vbox.addSpacing(24)

        # 숫자 패드
        pad_layout = QVBoxLayout()
        pad_layout.setSpacing(10)
        digits = [['1','2','3'], ['4','5','6'], ['7','8','9'], ['', '0', '⌫']]
        for row_keys in digits:
            row = QHBoxLayout()
            row.setSpacing(10)
            for k in row_keys:
                btn = QPushButton(k)
                btn.setFixedSize(76, 64)
                btn.setFont(QFont('Segoe UI', 20, QFont.Bold))
                if k == '':
                    btn.setEnabled(False)
                    btn.setStyleSheet('background:transparent; border:none;')
                elif k == '⌫':
                    btn.setStyleSheet(self._btn_style(special=True))
                    btn.clicked.connect(self._del)
                else:
                    btn.setStyleSheet(self._btn_style())
                    btn.clicked.connect(lambda _, d=k: self._input(d))
                row.addWidget(btn)
            pad_layout.addLayout(row)
        vbox.addLayout(pad_layout)

        # 오류 메시지
        self._err_label = QLabel('')
        self._err_label.setFont(QFont('Segoe UI', 11))
        self._err_label.setStyleSheet('color:#ef4444; border:none;')
        self._err_label.setAlignment(Qt.AlignCenter)
        vbox.addSpacing(8)
        vbox.addWidget(self._err_label)

    # ── 내부 ──────────────────────────────────────────────────────────

    def _input(self, digit: str) -> None:
        if len(self._entered) < self.MAX_LEN:
            self._entered += digit
            self._refresh_dots()
            if len(self._entered) == self.MAX_LEN:
                self._confirm()

    def _del(self) -> None:
        self._entered = self._entered[:-1]
        self._refresh_dots(error=False)
        self._err_label.setText('')

    def _confirm(self) -> None:
        if self._entered == self._correct_pin:
            self._on_success()
            self.reset()
        else:
            self._refresh_dots(error=True)
            self._err_label.setText('PIN이 올바르지 않습니다')
            QTimer.singleShot(700, self.reset)

    def _refresh_dots(self, error: bool = False) -> None:
        for i, dot in enumerate(self._dots):
            if error:
                dot.setStyleSheet(
                    'border-radius:7px; border:2px solid #ef4444; background:#ef4444;'
                )
            elif i < len(self._entered):
                dot.setStyleSheet(
                    'border-radius:7px; border:2px solid #3b82f6; background:#3b82f6;'
                )
            else:
                dot.setStyleSheet(
                    'border-radius:7px; border:2px solid #475569; background:transparent;'
                )

    def reset(self) -> None:
        self._entered = ''
        self._err_label.setText('')
        self._refresh_dots()

    # ── 키보드 지원 ───────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if Qt.Key_0 <= key <= Qt.Key_9:
            self._input(str(key - Qt.Key_0))
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._del()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if len(self._entered) == self.MAX_LEN:
                self._confirm()
        else:
            super().keyPressEvent(event)

    # ── 스타일 ───────────────────────────────────────────────────────

    @staticmethod
    def _btn_style(special: bool = False) -> str:
        base = 'border-radius:10px; font-size:20px; font-weight:700; border:1px solid #334155;'
        if special:
            return base + 'background:#0f172a; color:#94a3b8;'
        return base + 'background:#0f172a; color:#e2e8f0;'
