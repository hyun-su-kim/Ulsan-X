from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeyEvent, QPainter, QLinearGradient, QColor

# 패드 레이아웃: (표시 숫자/문자, 알파벳 서브레이블)
PAD_LAYOUT = [
    [('1', ''),     ('2', 'ABC'),  ('3', 'DEF')],
    [('4', 'GHI'),  ('5', 'JKL'),  ('6', 'MNO')],
    [('7', 'PQRS'), ('8', 'TUV'),  ('9', 'WXYZ')],
    [('⌫', ''),    ('0', ''),     ('확인', '')],
]

_STYLE_NORMAL  = ('background:#0f172a; border:1px solid #334155; border-radius:10px;'
                   'color:#e2e8f0;')
_STYLE_CONFIRM = ('background:#1e40af; border:1px solid #3b82f6; border-radius:10px;'
                   'color:#e2e8f0;')
_STYLE_HOVER   = ('background:#1e40af; border:1px solid #3b82f6; border-radius:10px;'
                   'color:#fff;')
_STYLE_PRESSED = ('background:#1d4ed8; border:1px solid #3b82f6; border-radius:10px;'
                   'color:#fff;')


class PinButton(QFrame):
    """포커스를 가져가지 않는 PIN 패드 버튼 (QFrame 기반)."""

    def __init__(self, digit: str, sub_label: str = '', parent=None):
        super().__init__(parent)
        self._digit     = digit
        self._callback  = None
        self._is_confirm = (digit == '확인')

        self.setFixedSize(76, 76)   # aspect-ratio:1 — 정사각형
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)   # 키보드 포커스 빼앗지 않음

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 10, 0, 10)
        vbox.setSpacing(2)
        vbox.setAlignment(Qt.AlignCenter)

        size = 14 if self._is_confirm else 20
        main_lbl = QLabel(digit)
        main_lbl.setAlignment(Qt.AlignCenter)
        main_lbl.setFont(QFont('Segoe UI', size, QFont.Bold))
        main_lbl.setStyleSheet('background:transparent; border:none;')
        main_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        vbox.addWidget(main_lbl)

        if sub_label:
            sub_lbl = QLabel(sub_label)
            sub_lbl.setAlignment(Qt.AlignCenter)
            sub_lbl.setFont(QFont('Segoe UI', 7))
            sub_lbl.setStyleSheet('color:#64748b; background:transparent; border:none;'
                                  'letter-spacing:1px;')
            sub_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            vbox.addWidget(sub_lbl)

        self.setStyleSheet(_STYLE_CONFIRM if self._is_confirm else _STYLE_NORMAL)

    def set_callback(self, fn) -> None:
        self._callback = fn

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.setStyleSheet(_STYLE_PRESSED)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            style = _STYLE_CONFIRM if self._is_confirm else _STYLE_NORMAL
            self.setStyleSheet(style)
            if self.rect().contains(e.pos()) and self._callback:
                self._callback()

    def enterEvent(self, e) -> None:
        self.setStyleSheet(_STYLE_HOVER)

    def leaveEvent(self, e) -> None:
        self.setStyleSheet(_STYLE_CONFIRM if self._is_confirm else _STYLE_NORMAL)


class LoginView(QWidget):
    MAX_LEN = 4

    def __init__(self, correct_pin: str, on_success):
        super().__init__()
        self._correct_pin = correct_pin
        self._on_success  = on_success
        self._entered     = ''

        self.setFocusPolicy(Qt.StrongFocus)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        box = QFrame()
        box.setFixedWidth(340)
        box.setStyleSheet(
            'background:#1e293b; border:1px solid #334155; border-radius:16px;'
        )
        outer.addWidget(box, alignment=Qt.AlignCenter)

        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(36, 40, 36, 40)
        vbox.setSpacing(0)
        vbox.setAlignment(Qt.AlignCenter)

        # ── 로고 ──
        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)
        logo_row.setSpacing(10)

        icon_box = QLabel('U')
        icon_box.setFixedSize(38, 38)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setFont(QFont('Segoe UI', 16, QFont.Bold))
        icon_box.setStyleSheet(
            'background:#1e40af; color:white; border-radius:10px; border:none;'
        )
        logo_row.addWidget(icon_box)

        logo_text = QLabel('Ulsan-X')
        logo_text.setFont(QFont('Segoe UI', 22, QFont.Bold))
        logo_text.setStyleSheet('color:#60a5fa; border:none;')
        logo_row.addWidget(logo_text)
        vbox.addLayout(logo_row)

        sub = QLabel('관제 시스템 — PIN 인증')
        sub.setFont(QFont('Segoe UI', 12))
        sub.setStyleSheet('color:#64748b; border:none;')
        sub.setAlignment(Qt.AlignCenter)
        vbox.addWidget(sub)

        vbox.addSpacing(28)

        # ── PIN 점 ──
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

        vbox.addSpacing(28)

        # ── 숫자 패드 ──
        pad_vbox = QVBoxLayout()
        pad_vbox.setSpacing(10)
        for row_keys in PAD_LAYOUT:
            row = QHBoxLayout()
            row.setSpacing(10)
            for digit, sub_label in row_keys:
                btn = PinButton(digit, sub_label)
                if digit == '⌫':
                    btn.set_callback(self._del)
                elif digit == '확인':
                    btn.set_callback(self._confirm)
                else:
                    btn.set_callback(lambda d=digit: self._input(d))
                row.addWidget(btn)
            pad_vbox.addLayout(row)
        vbox.addLayout(pad_vbox)

        vbox.addSpacing(8)

        # ── 오류 메시지 ──
        self._err_label = QLabel('')
        self._err_label.setFont(QFont('Segoe UI', 12))
        self._err_label.setStyleSheet('color:#ef4444; border:none;')
        self._err_label.setAlignment(Qt.AlignCenter)
        self._err_label.setFixedHeight(18)
        vbox.addWidget(self._err_label)

    # ── 배경 그라디언트 ───────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor('#0f172a'))
        grad.setColorAt(0.5, QColor('#1e293b'))
        grad.setColorAt(1.0, QColor('#0f172a'))
        painter.fillRect(self.rect(), grad)

    # ── 포커스 관리 ──────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(50, self.setFocus)

    # ── 입력 처리 ────────────────────────────────────────────────────

    def _input(self, digit: str) -> None:
        if len(self._entered) < self.MAX_LEN:
            self._entered += digit
            self._refresh_dots()

    def _del(self) -> None:
        self._entered = self._entered[:-1]
        self._refresh_dots(error=False)
        self._err_label.setText('')

    def _confirm(self) -> None:
        if len(self._entered) < self.MAX_LEN:
            return
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
                    'border-radius:7px; border:2px solid #ef4444; background:#ef4444;')
            elif i < len(self._entered):
                dot.setStyleSheet(
                    'border-radius:7px; border:2px solid #3b82f6; background:#3b82f6;')
            else:
                dot.setStyleSheet(
                    'border-radius:7px; border:2px solid #475569; background:transparent;')

    def reset(self) -> None:
        self._entered = ''
        self._err_label.setText('')
        self._refresh_dots()

    # ── 키보드 입력 ───────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if Qt.Key_0 <= key <= Qt.Key_9:
            self._input(str(key - Qt.Key_0))
        elif key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._del()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        else:
            super().keyPressEvent(event)
