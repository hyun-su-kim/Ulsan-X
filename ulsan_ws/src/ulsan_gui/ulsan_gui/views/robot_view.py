import time
import threading
import urllib.request
import json

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QFrame, QSizePolicy,
    QDialog, QScrollArea, QStackedWidget,
)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QFont, QImage, QPixmap, QKeyEvent, QPainter, QPen, QColor

STATUS_COLOR = {
    'IDLE':      '#16a34a', 'BUSY': '#d97706',
    'RETURNING': '#2563eb', 'WAITING': '#9333ea', 'UNKNOWN': '#9ca3af',
}
STATUS_BG = {
    'IDLE':      '#f0fdf4', 'BUSY': '#fffbeb',
    'RETURNING': '#eff6ff', 'WAITING': '#faf5ff', 'UNKNOWN': '#f8fafc',
}

_BATT_V_MAX = 12.6
_BATT_V_MIN = 9.0

def _voltage_to_pct(voltage: float) -> float:
    pct = (voltage - _BATT_V_MIN) / (_BATT_V_MAX - _BATT_V_MIN) * 100.0
    return max(0.0, min(100.0, pct))


TELEOP_KEYS = {
    Qt.Key_U:     (1,  1),
    Qt.Key_I:     (1,  0),
    Qt.Key_O:     (1, -1),
    Qt.Key_J:     (0,  1),
    Qt.Key_K:     (0,  0),
    Qt.Key_L:     (0, -1),
    Qt.Key_M:     (-1, 1),
    Qt.Key_Comma: (-1, 0),
    Qt.Key_Period:(-1,-1),
}

CARD_STYLE  = 'background:#fff; border-radius:10px; border:1px solid #e5e7eb;'
LABEL_STYLE = 'color:#111827; border:none;'

_DPAD_KEY_HINTS: dict[tuple, str] = {
    (1,  1):  'U',
    (1,  0):  'I',
    (1, -1):  'O',
    (0,  1):  'J',
    (0,  0):  'K',
    (0, -1):  'L',
    (-1, 1):  'M',
    (-1, 0):  ',',
    (-1,-1):  '.',
}


class _DpadBtn(QFrame):
    """방향 기호 + 키 힌트를 함께 표시하는 D-pad 버튼."""

    def __init__(self, sym: str, key_hint: str, is_diag: bool, on_press, on_release):
        super().__init__()
        self._on_press   = on_press
        self._on_release = on_release
        self._is_diag    = is_diag
        self.setFixedSize(52, 50)
        self.setCursor(Qt.PointingHandCursor)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(2, 5, 2, 4)
        vbox.setSpacing(0)

        sym_lbl = QLabel(sym)
        sym_lbl.setAlignment(Qt.AlignCenter)
        sym_lbl.setFont(QFont('Segoe UI', 13))
        sym_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        vbox.addWidget(sym_lbl)

        key_lbl = QLabel(key_hint)
        key_lbl.setAlignment(Qt.AlignCenter)
        key_lbl.setFont(QFont('Segoe UI', 7))
        key_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        vbox.addWidget(key_lbl)

        self._sym_lbl = sym_lbl
        self._key_lbl = key_lbl
        self._teleop_enabled = False
        self._apply_style(False)

    def set_teleop_enabled(self, enabled: bool) -> None:
        self._teleop_enabled = enabled
        self._apply_style(False)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)

    def _apply_style(self, pressed: bool) -> None:
        if not self._teleop_enabled:
            bg, border = '#f9fafb', '#e5e7eb'
            sym_c, key_c = '#d1d5db', '#e5e7eb'
        elif pressed:
            bg, border = '#dbeafe', '#93c5fd'
            sym_c, key_c = '#1e40af', '#3b82f6'
        else:
            bg, border = '#f3f4f6', '#d1d5db'
            sym_c, key_c = '#374151', '#6b7280'
        self.setStyleSheet(
            f'QFrame {{ background:{bg}; border:1px solid {border}; border-radius:7px; }}'
        )
        self._sym_lbl.setStyleSheet(f'color:{sym_c}; background:transparent; border:none;')
        self._key_lbl.setStyleSheet(f'color:{key_c}; background:transparent; border:none;')

    def mousePressEvent(self, _) -> None:
        if not self._teleop_enabled:
            return
        self._apply_style(True)
        self._on_press()

    def mouseReleaseEvent(self, _) -> None:
        if not self._teleop_enabled:
            return
        self._apply_style(False)
        self._on_release()


# ── 배터리 원형 게이지 ────────────────────────────────────────────────

class BatteryGauge(QWidget):
    """도넛 형태의 배터리 게이지. set_value(pct) 로 업데이트."""

    def __init__(self):
        super().__init__()
        self._pct: float | None = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(56, 56)

    def set_value(self, pct: float | None) -> None:
        self._pct = pct
        self.update()

    def paintEvent(self, _) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        size   = min(w, h)
        margin = max(6, size // 8)
        pen_w  = max(7, size // 7)
        x = (w - size) // 2 + margin
        y = (h - size) // 2 + margin
        rect = QRect(x, y, size - 2 * margin, size - 2 * margin)

        # 배경 원호
        bg_pen = QPen(QColor('#e5e7eb'))
        bg_pen.setWidth(pen_w)
        bg_pen.setCapStyle(Qt.FlatCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self._pct is not None:
            pct = max(0.0, min(100.0, self._pct))
            if pct >= 50:
                color = QColor('#10b981')
            elif pct >= 20:
                color = QColor('#f59e0b')
            else:
                color = QColor('#ef4444')

            fg_pen = QPen(color)
            fg_pen.setWidth(pen_w)
            fg_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(fg_pen)
            span = int(pct / 100.0 * 360 * 16)
            painter.drawArc(rect, 90 * 16, -span)

            painter.setPen(QColor('#111827'))
            painter.setFont(QFont('Segoe UI', max(9, size // 5), QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, f'{pct:.0f}%')
        else:
            painter.setPen(QColor('#9ca3af'))
            painter.setFont(QFont('Segoe UI', max(8, size // 6)))
            painter.drawText(rect, Qt.AlignCenter, '--')


# ── 카메라 위젯 ───────────────────────────────────────────────────────

class CameraWidget(QLabel):
    def __init__(self, robot: str, ros_node):
        super().__init__()
        self.robot = robot
        self.ros   = ros_node
        self._raw_bytes: bytes | None = None
        self._fmt: str = ''

        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)
        self.setText('카메라 신호 없음')
        self.setFont(QFont('Segoe UI', 10))
        self.setStyleSheet('background:#0d1117; border-radius:8px; border:none; color:#4b5563;')

    def update_image(self, data: bytes, fmt: str) -> None:
        self._raw_bytes = data
        self._fmt = fmt
        img = QImage.fromData(data)
        if not img.isNull():
            pix = QPixmap.fromImage(img).scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(pix)

    def resizeEvent(self, _) -> None:
        if self._raw_bytes:
            self.update_image(self._raw_bytes, self._fmt)

    def open_fullscreen(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(f'{self.robot.upper()} 전방 카메라')
        dlg.showFullScreen()
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)

        cam = QLabel()
        cam.setAlignment(Qt.AlignCenter)
        cam.setStyleSheet('background:#000;')
        layout.addWidget(cam)

        close_btn = QPushButton('닫기  [Esc]')
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet('background:#374151; color:#fff; border:none; font-size:12px;')
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn)

        def _refresh():
            if self._raw_bytes:
                img = QImage.fromData(self._raw_bytes)
                if not img.isNull():
                    pix = QPixmap.fromImage(img).scaled(
                        cam.width(), cam.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    cam.setPixmap(pix)

        timer = QTimer(dlg)
        timer.timeout.connect(_refresh)
        timer.start(33)
        dlg.keyPressEvent = lambda e: dlg.close() if e.key() == Qt.Key_Escape else None
        dlg.exec_()


# ── 텔레옵 카드 ───────────────────────────────────────────────────────

class TeleopCard(QFrame):
    LINEAR_SPEED  = 0.3
    ANGULAR_SPEED = 0.5

    def __init__(self, robot: str, ros_node):
        super().__init__()
        self.robot        = robot
        self.ros          = ros_node
        self._speed_scale = 0.3
        self._manual_mode = False
        self.setStyleSheet(CARD_STYLE)
        self.setFocusPolicy(Qt.StrongFocus)
        self._build_ui()

    def _build_ui(self) -> None:
        self._dpad_btns: dict[tuple, '_DpadBtn'] = {}
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        # 헤더
        header = QHBoxLayout()
        title = QLabel('🕹 수동 조작')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        header.addWidget(title)
        header.addStretch()
        sub = QLabel(f'{self.robot.upper()} · /cmd_vel')
        sub.setFont(QFont('Segoe UI', 9))
        sub.setStyleSheet('color:#6b7280; border:none;')
        header.addWidget(sub)
        vbox.addLayout(header)

        # 모드 전환 버튼
        self._mode_btn = QPushButton('수동 조작 전환')
        self._mode_btn.setFixedHeight(34)
        self._mode_btn.setFont(QFont('Segoe UI', 10))
        self._mode_btn.setFocusPolicy(Qt.NoFocus)
        self._mode_btn.clicked.connect(self._toggle_manual_mode)
        self._apply_mode_style()
        vbox.addWidget(self._mode_btn)

        # D-pad (3×3, 대각선 포함)
        grid = [['↖', '↑', '↗'], ['←', '■', '→'], ['↙', '↓', '↘']]
        acts = [[(1,1),(1,0),(1,-1)],[(0,1),(0,0),(0,-1)],[(-1,1),(-1,0),(-1,-1)]]
        dpad_w = QWidget()
        dpad_l = QVBoxLayout(dpad_w)
        dpad_l.setSpacing(5)
        dpad_l.setContentsMargins(0, 0, 0, 0)
        for r_i, row in enumerate(grid):
            row_h = QHBoxLayout()
            row_h.setSpacing(5)
            for c_i, sym in enumerate(row):
                act      = acts[r_i][c_i]
                is_diag  = sym in ('↖', '↗', '↙', '↘')
                key_hint = _DPAD_KEY_HINTS[act]
                btn = _DpadBtn(
                    sym, key_hint, is_diag,
                    on_press=lambda lin=act[0], ang=act[1]: self._send(lin, ang),
                    on_release=lambda: self._send(0, 0),
                )
                self._dpad_btns[act] = btn
                row_h.addWidget(btn)
            dpad_l.addLayout(row_h)
        vbox.addWidget(dpad_w, alignment=Qt.AlignHCenter)

        # 속도 슬라이더
        speed_row = QHBoxLayout()
        speed_lbl = QLabel('속도')
        speed_lbl.setFont(QFont('Segoe UI', 10))
        speed_lbl.setStyleSheet('color:#6b7280; border:none;')

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(1, 10)
        self._slider.setValue(3)
        self._slider.valueChanged.connect(self._on_speed_change)

        self._speed_val_lbl = QLabel('0.3 m/s')
        self._speed_val_lbl.setFont(QFont('Segoe UI', 10))
        self._speed_val_lbl.setStyleSheet('color:#374151; border:none;')

        speed_row.addWidget(speed_lbl)
        speed_row.addWidget(self._slider, 1)
        speed_row.addWidget(self._speed_val_lbl)
        vbox.addLayout(speed_row)

    def _toggle_manual_mode(self) -> None:
        self._manual_mode = not self._manual_mode
        label = 'LIMO 1' if self.robot == 'limo1' else 'LIMO 2'
        if self._manual_mode:
            self.ros.publish_pause(self.robot)
            self.ros.signals.sig_gui_log.emit('system', label, '수동조작 전환')
        else:
            self._send(0, 0)
            self.ros.publish_resume(self.robot)
            self.ros.signals.sig_gui_log.emit('system', label, '자율주행 복귀')
        self._apply_mode_style()
        for btn in self._dpad_btns.values():
            btn.set_teleop_enabled(self._manual_mode)

    def _apply_mode_style(self) -> None:
        if self._manual_mode:
            self._mode_btn.setText('자율주행 복귀')
            self._mode_btn.setStyleSheet(
                'background:#1e40af; color:#fff; border:none; border-radius:6px;'
            )
        else:
            self._mode_btn.setText('수동 조작 전환')
            self._mode_btn.setStyleSheet(
                'background:#f1f5f9; color:#6b7280;'
                'border:1px solid #e5e7eb; border-radius:6px;'
            )

    def _on_speed_change(self, val: int) -> None:
        self._speed_scale = val / 10.0
        self._speed_val_lbl.setText(f'{self._speed_scale:.1f} m/s')

    def _send(self, lin: int, ang: int) -> None:
        self.ros.publish_cmd_vel(
            self.robot,
            lin * self.LINEAR_SPEED  * self._speed_scale,
            ang * self.ANGULAR_SPEED * self._speed_scale,
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        if not self._manual_mode:
            super().keyPressEvent(event)
            return
        act = TELEOP_KEYS.get(event.key())
        if act is not None:
            self._send(act[0], act[1])
            btn = self._dpad_btns.get(act)
            if btn:
                btn._apply_style(True)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        if not self._manual_mode:
            super().keyReleaseEvent(event)
            return
        act = TELEOP_KEYS.get(event.key())
        if act is not None:
            if event.key() != Qt.Key_K:
                self._send(0, 0)
            btn = self._dpad_btns.get(act)
            if btn:
                btn._apply_style(False)
        else:
            super().keyReleaseEvent(event)


# ── 단일 로봇 상세 패널 ───────────────────────────────────────────────

class RobotPanel(QWidget):
    def __init__(self, robot: str, ros_node):
        super().__init__()
        self.robot = robot
        self.ros   = ros_node
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(10, 10, 10, 10)
        main_vbox.setSpacing(10)

        # 상단: 정보(1) | 카메라(3) | [이벤트(상)+텔레옵(하)](1)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._build_info_card(), 1)
        top.addWidget(self._build_camera_card(), 3)

        right_col = QWidget()
        right_vbox = QVBoxLayout(right_col)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(10)
        right_vbox.addWidget(self._build_events_card(), 1)
        right_vbox.addWidget(self._build_teleop_card(), 1)
        top.addWidget(right_col, 1)

        main_vbox.addLayout(top, 1)

    def _build_info_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(6)

        # 헤더
        header_hbox = QHBoxLayout()
        name_lbl = QLabel(f'🤖 {self.robot.upper()}')
        name_lbl.setFont(QFont('Segoe UI', 14, QFont.Bold))
        name_lbl.setStyleSheet(LABEL_STYLE)
        header_hbox.addWidget(name_lbl)
        header_hbox.addStretch()

        self._status_badge = QLabel('UNKNOWN')
        self._status_badge.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._status_badge.setStyleSheet(
            f'border-radius:8px; padding:3px 10px; border:none;'
            f'color:{STATUS_COLOR["UNKNOWN"]}; background:{STATUS_BG["UNKNOWN"]};'
        )
        header_hbox.addWidget(self._status_badge)
        vbox.addLayout(header_hbox)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('border:none; border-top:1px solid #e5e7eb;')
        vbox.addWidget(sep)

        # 현재 임무 박스
        self._mission_box = QFrame()
        self._mission_box.setStyleSheet(
            'background:#eff6ff; border-radius:8px; border:1px solid #bfdbfe;'
        )
        mb_vbox = QVBoxLayout(self._mission_box)
        mb_vbox.setContentsMargins(10, 8, 10, 8)
        mb_vbox.setSpacing(2)

        self._mission_lbl_title = QLabel('현재 임무')
        self._mission_lbl_title.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._mission_lbl_title.setStyleSheet('color:#1d4ed8; border:none;')
        mb_vbox.addWidget(self._mission_lbl_title)

        self._mission_lbl_dest = QLabel('대기 중')
        self._mission_lbl_dest.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self._mission_lbl_dest.setStyleSheet('color:#111827; border:none;')
        mb_vbox.addWidget(self._mission_lbl_dest)

        vbox.addWidget(self._mission_box)

        # 배터리 게이지 (전체 폭)
        batt_box = QFrame()
        batt_box.setStyleSheet('background:#f8fafc; border-radius:8px; border:1px solid #f1f5f9;')
        batt_vbox = QVBoxLayout(batt_box)
        batt_vbox.setContentsMargins(8, 8, 8, 8)
        batt_vbox.setSpacing(2)
        batt_lbl = QLabel('배터리')
        batt_lbl.setFont(QFont('Segoe UI', 9, QFont.Bold))
        batt_lbl.setStyleSheet('color:#9ca3af; border:none;')
        batt_vbox.addWidget(batt_lbl)
        self._batt_gauge = BatteryGauge()
        batt_vbox.addWidget(self._batt_gauge, 1)
        vbox.addWidget(batt_box)

        # 금일 임무 수 + 완료 수
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self._metric_task_total = _metric_box('금일 임무', '--', '건')
        self._metric_task_done  = _metric_box('완료',     '--', '건')
        row2.addWidget(self._metric_task_total)
        row2.addWidget(self._metric_task_done)
        vbox.addLayout(row2)

        vbox.addStretch()
        return card

    def _build_events_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 10)
        vbox.setSpacing(6)

        title = QLabel('⚡ 오늘 이벤트')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        vbox.addWidget(title)

        self._evt_area = QScrollArea()
        self._evt_area.setWidgetResizable(True)
        self._evt_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._evt_area.setStyleSheet('border:none; background:transparent;')

        self._evt_container = QWidget()
        self._evt_layout = QVBoxLayout(self._evt_container)
        self._evt_layout.setContentsMargins(0, 0, 0, 0)
        self._evt_layout.setSpacing(2)
        self._evt_layout.addStretch()
        self._evt_area.setWidget(self._evt_container)
        vbox.addWidget(self._evt_area, 1)

        return card

    def _build_camera_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel(f'📷 {self.robot.upper()} 전방 카메라')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        header.addWidget(title)

        self._live_badge = QLabel('LIVE')
        self._live_badge.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._live_badge.setStyleSheet(
            'background:#1f2937; color:#6b7280; border-radius:4px; padding:1px 6px; border:none;'
        )
        header.addWidget(self._live_badge)
        header.addStretch()

        fs_btn = QPushButton('⛶ 전체화면')
        fs_btn.setFont(QFont('Segoe UI', 9))
        fs_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #d1d5db; border-radius:6px;'
            'padding:3px 10px; color:#374151;'
        )
        header.addWidget(fs_btn)
        vbox.addLayout(header)

        self._camera = CameraWidget(self.robot, self.ros)
        vbox.addWidget(self._camera, 1)
        fs_btn.clicked.connect(self._camera.open_fullscreen)

        return card

    def _build_teleop_card(self) -> TeleopCard:
        self._teleop = TeleopCard(self.robot, self.ros)
        return self._teleop

    # ── 시그널 연결 ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._cam_last_recv: float = 0.0

        if self.robot == 'limo1':
            self.ros.signals.sig_status_1.connect(self._on_status)
            self.ros.signals.sig_camera_1.connect(self._on_camera)
            self.ros.signals.sig_dest_1.connect(self._on_dest)
            self.ros.signals.sig_battery_1.connect(self._on_battery)
        else:
            self.ros.signals.sig_status_2.connect(self._on_status)
            self.ros.signals.sig_camera_2.connect(self._on_camera)
            self.ros.signals.sig_dest_2.connect(self._on_dest)
            self.ros.signals.sig_battery_2.connect(self._on_battery)

        cam_timer = QTimer(self)
        cam_timer.timeout.connect(self._check_cam_live)
        cam_timer.start(2000)

    def _on_camera(self, data: bytes, fmt: str) -> None:
        self._camera.update_image(data, fmt)
        self._cam_last_recv = time.time()

    def _check_cam_live(self) -> None:
        live = (time.time() - self._cam_last_recv) < 3.0
        if live:
            self._live_badge.setStyleSheet(
                'background:#ef4444; color:#fff; border-radius:4px; padding:1px 6px; border:none;'
            )
        else:
            self._live_badge.setStyleSheet(
                'background:#1f2937; color:#6b7280; border-radius:4px; padding:1px 6px; border:none;'
            )

    def _on_status(self, status: str) -> None:
        self._status_badge.setText(status)
        c  = STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN'])
        bg = STATUS_BG.get(status, STATUS_BG['UNKNOWN'])
        self._status_badge.setStyleSheet(
            f'border-radius:8px; padding:3px 10px; border:none; color:{c}; background:{bg};'
        )
        if status == 'IDLE':
            self._mission_lbl_dest.setText('HOME — 대기 중')
            self._mission_box.setStyleSheet(
                'background:#f0fdf4; border-radius:8px; border:1px solid #bbf7d0;'
            )
            self._mission_lbl_title.setStyleSheet('color:#047857; border:none;')
        else:
            self._mission_box.setStyleSheet(
                'background:#eff6ff; border-radius:8px; border:1px solid #bfdbfe;'
            )
            self._mission_lbl_title.setStyleSheet('color:#1d4ed8; border:none;')
        self._add_event(status)

    def _on_dest(self, dest: str) -> None:
        if dest:
            self._mission_lbl_dest.setText(dest)

    def _on_battery(self, voltage: float) -> None:
        self._batt_gauge.set_value(_voltage_to_pct(voltage))

    def set_today_tasks(self, total: int, done: int) -> None:
        self._metric_task_total._val.setText(str(total))
        self._metric_task_done._val.setText(str(done))

    def _add_event(self, msg: str) -> None:
        from datetime import datetime
        row = QHBoxLayout()
        time_lbl = QLabel(datetime.now().strftime('%H:%M:%S'))
        time_lbl.setFont(QFont('Segoe UI', 9))
        time_lbl.setFixedWidth(54)
        time_lbl.setStyleSheet('color:#9ca3af; border:none;')

        msg_lbl = QLabel(msg)
        msg_lbl.setFont(QFont('Segoe UI', 9))
        msg_lbl.setStyleSheet('color:#374151; border:none;')

        row.addWidget(time_lbl)
        row.addWidget(msg_lbl, 1)

        container = QWidget()
        container.setLayout(row)
        container.setStyleSheet('border:none; border-bottom:1px solid #f9fafb;')
        self._evt_layout.insertWidget(self._evt_layout.count() - 1, container)
        while self._evt_layout.count() > 51:
            item = self._evt_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._evt_area.verticalScrollBar().setValue(
            self._evt_area.verticalScrollBar().maximum()
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._teleop.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._teleop.keyReleaseEvent(event)


def _metric_box(label: str, value: str, unit: str) -> QFrame:
    box = QFrame()
    box.setStyleSheet(
        'background:#f8fafc; border-radius:8px; border:1px solid #f1f5f9;'
    )
    vbox = QVBoxLayout(box)
    vbox.setContentsMargins(10, 8, 10, 8)
    vbox.setSpacing(2)

    lbl = QLabel(label)
    lbl.setFont(QFont('Segoe UI', 9, QFont.Bold))
    lbl.setStyleSheet('color:#9ca3af; border:none;')
    vbox.addWidget(lbl)

    val_row = QHBoxLayout()
    val_lbl = QLabel(value)
    val_lbl.setFont(QFont('Segoe UI', 18, QFont.Bold))
    val_lbl.setStyleSheet('color:#111827; border:none;')
    val_row.addWidget(val_lbl)

    if unit:
        unit_lbl = QLabel(unit)
        unit_lbl.setFont(QFont('Segoe UI', 10))
        unit_lbl.setStyleSheet('color:#6b7280; border:none;')
        val_row.addWidget(unit_lbl)
    val_row.addStretch()
    vbox.addLayout(val_row)

    box._val = val_lbl
    return box


# ── 로봇 뷰 (탭 선택) ────────────────────────────────────────────────

class RobotView(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self._statuses = {'limo1': 'UNKNOWN', 'limo2': 'UNKNOWN'}
        self._build_ui(ros_node)

        ros_node.signals.sig_status_1.connect(lambda s: self._on_tab_status('limo1', s))
        ros_node.signals.sig_status_2.connect(lambda s: self._on_tab_status('limo2', s))

        self._task_timer = QTimer(self)
        self._task_timer.timeout.connect(self._fetch_today_tasks)
        self._task_timer.start(30_000)
        self._fetch_today_tasks()

    def _build_ui(self, ros_node) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 탭 바
        tab_bar = QFrame()
        tab_bar.setFixedHeight(52)
        tab_bar.setStyleSheet('background:#f8fafc; border-bottom:1px solid #e5e7eb;')
        tab_hbox = QHBoxLayout(tab_bar)
        tab_hbox.setContentsMargins(12, 8, 12, 8)
        tab_hbox.setSpacing(8)

        self._panels: dict[str, RobotPanel] = {}
        self._tab_btns: dict[str, QFrame] = {}
        self._tab_name_lbls: dict[str, QLabel] = {}
        self._tab_badges: dict[str, QLabel] = {}

        for robot in ('limo1', 'limo2'):
            label = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'

            # QFrame 기반 클릭 가능 탭 (QPushButton.setLayout은 Qt에서 렌더링 깨짐)
            tab_frame = QFrame()
            tab_frame.setFixedHeight(36)
            tab_frame.setCursor(Qt.PointingHandCursor)
            tab_frame.setStyleSheet(self._tab_style(False))
            tab_frame.mousePressEvent = lambda e, r=robot: self._select(r)
            self._tab_btns[robot] = tab_frame

            tab_inner = QHBoxLayout(tab_frame)
            tab_inner.setSpacing(8)
            tab_inner.setContentsMargins(14, 0, 14, 0)

            lbl_text = QLabel(f'🤖 {label}')
            lbl_text.setFont(QFont('Segoe UI', 11, QFont.Bold))
            lbl_text.setStyleSheet('background:transparent; border:none; color:#6b7280;')
            lbl_text.setAttribute(Qt.WA_TransparentForMouseEvents)
            tab_inner.addWidget(lbl_text)
            self._tab_name_lbls[robot] = lbl_text

            badge = QLabel('UNKNOWN')
            badge.setFont(QFont('Segoe UI', 9, QFont.Bold))
            badge.setStyleSheet(
                'background:#f3f4f6; color:#9ca3af;'
                'border-radius:8px; padding:1px 6px; border:none;'
            )
            badge.setAttribute(Qt.WA_TransparentForMouseEvents)
            tab_inner.addWidget(badge)
            self._tab_badges[robot] = badge

            tab_hbox.addWidget(tab_frame)
            self._panels[robot] = RobotPanel(robot, ros_node)

        tab_hbox.addStretch()
        vbox.addWidget(tab_bar)

        self._stack = QStackedWidget()
        for panel in self._panels.values():
            self._stack.addWidget(panel)
        vbox.addWidget(self._stack, 1)

        self._select('limo1')

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fetch_today_tasks()

    def _fetch_today_tasks(self) -> None:
        def _do():
            try:
                with urllib.request.urlopen(
                    'http://localhost:8000/reservations/today', timeout=3
                ) as resp:
                    data = json.loads(resp.read())
                total = len(data)
                done  = sum(1 for r in data if r.get('status') == 'COMPLETED')
                for panel in self._panels.values():
                    panel.set_today_tasks(total, done)
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _on_tab_status(self, robot: str, status: str) -> None:
        self._statuses[robot] = status
        badge = self._tab_badges[robot]
        active = (self._stack.currentWidget() == self._panels[robot])
        c  = STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN'])
        bg = STATUS_BG.get(status, STATUS_BG['UNKNOWN'])
        badge.setText(status)
        badge.setStyleSheet(
            f'border-radius:8px; padding:1px 6px; border:none;'
            f'color:{c}; background:{"rgba(0,0,0,0.1)" if active else bg};'
        )

    def _select(self, robot: str) -> None:
        self._stack.setCurrentWidget(self._panels[robot])
        for r, frame in self._tab_btns.items():
            active = (r == robot)
            frame.setStyleSheet(self._tab_style(active))
            self._tab_name_lbls[r].setStyleSheet(
                f'background:transparent; border:none;'
                f'color:{"#1e40af" if active else "#6b7280"};'
            )
        self._panels[robot].setFocus()
        for r in ('limo1', 'limo2'):
            self._on_tab_status(r, self._statuses[r])

    @staticmethod
    def _tab_style(active: bool) -> str:
        if active:
            return 'QFrame { background:#eff6ff; border:2px solid #1e40af; border-radius:8px; }'
        return 'QFrame { background:#fff; border:2px solid #e5e7eb; border-radius:8px; }'

    def keyPressEvent(self, event: QKeyEvent) -> None:
        current = self._stack.currentWidget()
        if isinstance(current, RobotPanel):
            current.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        current = self._stack.currentWidget()
        if isinstance(current, RobotPanel):
            current.keyReleaseEvent(event)
