import math
from datetime import datetime

import requests
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, QThread, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap, QPainter, QColor, QPen, QBrush, QPolygon

STATUS_COLOR = {
    'IDLE':      '#16a34a', 'BUSY':      '#d97706',
    'RETURNING': '#2563eb', 'WAITING':   '#9333ea',
    'FAILED':    '#dc2626', 'UNKNOWN':   '#9ca3af',
}
STATUS_BG = {
    'IDLE':      '#f0fdf4', 'BUSY':      '#fffbeb',
    'RETURNING': '#eff6ff', 'WAITING':   '#faf5ff',
    'FAILED':    '#fef2f2', 'UNKNOWN':   '#f8fafc',
}
STATUS_BORDER = {
    'IDLE':      '#10b981', 'BUSY':      '#f59e0b',
    'RETURNING': '#3b82f6', 'WAITING':   '#9333ea',
    'FAILED':    '#ef4444', 'UNKNOWN':   '#9ca3af',
}
LOG_TYPE_COLOR = {
    'mission_start':    ('#dbeafe', '#1d4ed8'),
    'mission_complete': ('#d1fae5', '#047857'),
    'mission_fail':     ('#fee2e2', '#b91c1c'),
    'waiting':          ('#fef3c7', '#b45309'),
    'system':           ('#f3f4f6', '#374151'),
}

CARD_TITLE_STYLE = (
    'font-size:11px; font-weight:600; color:#6b7280;'
    'letter-spacing:0.5px; border:none;'
)


# ── FastAPI 비동기 체크 스레드 ────────────────────────────────────────

class _FastApiChecker(QThread):
    done = pyqtSignal(bool)

    def run(self) -> None:
        try:
            r = requests.get('http://localhost:8000/logs', timeout=0.5)
            self.done.emit(r.ok)
        except Exception:
            self.done.emit(False)


# ── 맵 캔버스 ────────────────────────────────────────────────────────

class MapCanvas(QWidget):
    """OccupancyGrid + 로봇 마커 + 범례 + 줌/패닝 컨트롤."""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            'background:#f8fafc; border-radius:6px; border:1px solid #e5e7eb;'
        )
        self._map_pixmap: QPixmap | None = None
        self._map_info   = None
        self._poses: dict[str, tuple | None] = {'limo1': None, 'limo2': None}
        self._statuses: dict[str, str] = {'limo1': 'UNKNOWN', 'limo2': 'UNKNOWN'}
        self._robot_colors = {'limo1': QColor('#2563eb'), 'limo2': QColor('#d97706')}

        # 줌/패닝 상태
        self._zoom: float = 1.0
        self._pan = QPoint(0, 0)
        self._drag_pos = None
        self.setCursor(Qt.OpenHandCursor)

        # ── 줌 컨트롤 (우하단 오버레이) ──
        ctrl_frame = QFrame(self)
        ctrl_frame.setStyleSheet('background:transparent; border:none;')
        ctrl_vbox = QVBoxLayout(ctrl_frame)
        ctrl_vbox.setContentsMargins(0, 0, 0, 0)
        ctrl_vbox.setSpacing(4)
        for sym, cb in (('+', self._zoom_in), ('−', self._zoom_out)):
            b = QPushButton(sym)
            b.setFixedSize(28, 28)
            b.setFont(QFont('Segoe UI', 13))
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(
                'background:white; border:1px solid #d1d5db; border-radius:6px;'
                'color:#374151;'
            )
            b.clicked.connect(lambda _, f=cb: f())
            ctrl_vbox.addWidget(b)
        self._ctrl_frame = ctrl_frame

        # ── 범례 (좌상단 오버레이) ──
        leg_frame = QFrame(self)
        leg_frame.setStyleSheet(
            'background:rgba(255,255,255,230); border-radius:8px; border:1px solid #e5e7eb;'
        )
        leg_vbox = QVBoxLayout(leg_frame)
        leg_vbox.setContentsMargins(8, 8, 10, 8)
        leg_vbox.setSpacing(4)

        self._legend_rows: dict[str, QLabel] = {}
        for robot_id, label, color in (
            ('limo1', 'LIMO 1 (UNKNOWN)', '#f59e0b'),
            ('limo2', 'LIMO 2 (UNKNOWN)', '#10b981'),
        ):
            row = QHBoxLayout()
            row.setSpacing(6)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f'background:{color}; border-radius:5px; border:none;')
            row.addWidget(dot)
            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 11))
            lbl.setStyleSheet('color:#374151; border:none; background:transparent;')
            row.addWidget(lbl)
            row.addStretch()
            leg_vbox.addLayout(row)
            self._legend_rows[robot_id] = lbl
        self._leg_frame = leg_frame

        QTimer.singleShot(0, self._reposition_overlays)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        if self._ctrl_frame:
            self._ctrl_frame.adjustSize()
            cw = self._ctrl_frame.sizeHint().width()
            ch = self._ctrl_frame.sizeHint().height()
            self._ctrl_frame.setGeometry(self.width() - cw - 12, self.height() - ch - 12, cw, ch)
        if self._leg_frame:
            self._leg_frame.adjustSize()
            lw = self._leg_frame.sizeHint().width()
            lh = self._leg_frame.sizeHint().height()
            self._leg_frame.setGeometry(10, 10, max(lw, 140), lh)

    # ── 줌/패닝 ──────────────────────────────────────────────────────

    def _zoom_in(self)  -> None: self._apply_zoom(1.25, self.rect().center())
    def _zoom_out(self) -> None: self._apply_zoom(1/1.25, self.rect().center())

    def _zoom_reset(self) -> None:
        self._zoom = 1.0
        self._pan  = QPoint(0, 0)
        self.update()

    def _apply_zoom(self, factor: float, cursor_pos) -> None:
        new_zoom = max(0.3, min(10.0, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        wx, wy = self.width() / 2, self.height() / 2
        cx, cy = cursor_pos.x(), cursor_pos.y()
        ratio  = new_zoom / self._zoom
        rel_x  = cx - wx - self._pan.x()
        rel_y  = cy - wy - self._pan.y()
        self._pan  = QPoint(int(cx - wx - rel_x * ratio),
                            int(cy - wy - rel_y * ratio))
        self._zoom = new_zoom
        self.update()

    def wheelEvent(self, e) -> None:
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self._apply_zoom(factor, e.pos())

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_pos is not None:
            self._pan += e.pos() - self._drag_pos
            self._drag_pos = e.pos()
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_pos = None
            self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._zoom_reset()

    # ── 데이터 업데이트 ───────────────────────────────────────────────

    def update_map(self, msg) -> None:
        import numpy as np
        info = msg.info
        w, h = info.width, info.height

        arr = np.array(msg.data, dtype=np.int8).reshape(h, w)

        # RGBA 4채널: free=밝은 배경, unknown=중간 회색, occupied=진한 벽
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        free     = arr == 0
        unknown  = arr == -1
        occupied = arr > 0

        rgba[free]     = [242, 244, 246, 255]   # 밝은 회백색
        rgba[unknown]  = [180, 185, 192, 255]   # 중간 회색
        rgba[occupied] = [ 40,  44,  52, 255]   # 진한 벽

        rgba = np.ascontiguousarray(np.flipud(rgba))
        img = QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
        self._map_pixmap = QPixmap.fromImage(img.copy())
        self._map_info   = info
        self.update()

    def update_pose(self, robot: str, msg) -> None:
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y ** 2 + q.z ** 2)
        )
        self._poses[robot] = (p.x, p.y, yaw)
        self.update()

    def update_status(self, robot: str, status: str) -> None:
        self._statuses[robot] = status
        lbl = self._legend_rows.get(robot)
        if lbl:
            name = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'
            lbl.setText(f'{name} ({status})')

    def paintEvent(self, _) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        if self._map_pixmap is None:
            painter.setPen(QColor('#94a3b8'))
            painter.setFont(QFont('Segoe UI', 13))
            painter.drawText(self.rect(), Qt.AlignCenter, '/map 토픽 대기 중...')
            return

        info       = self._map_info
        base_scale = min(w / info.width, h / info.height)
        eff_scale  = base_scale * self._zoom
        draw_w     = int(info.width  * eff_scale)
        draw_h     = int(info.height * eff_scale)
        off_x      = (w - draw_w) // 2 + self._pan.x()
        off_y      = (h - draw_h) // 2 + self._pan.y()

        scaled_pm = self._map_pixmap.scaled(
            draw_w, draw_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )
        painter.drawPixmap(off_x, off_y, scaled_pm)

        for robot, pose in self._poses.items():
            if pose is None:
                continue
            rx, ry, ryaw = pose
            px = off_x + int((rx - info.origin.position.x) / info.resolution * eff_scale)
            py = off_y + draw_h - int((ry - info.origin.position.y) / info.resolution * eff_scale)

            color = self._robot_colors[robot]
            painter.save()
            painter.translate(px, py)
            painter.rotate(-math.degrees(ryaw))

            R = 13
            # 흰색 외곽선으로 배경과 구분
            painter.setPen(QPen(Qt.white, 3))
            painter.setBrush(QBrush(Qt.white))
            painter.drawEllipse(-(R + 2), -(R + 2), 2 * (R + 2), 2 * (R + 2))
            # 본체 원
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(-R, -R, 2 * R, 2 * R)
            # 방향 화살표 (삼각형, 앞방향=위)
            arrow = QPolygon([
                QPoint(0,  -(R + 14)),
                QPoint(-8, -(R - 3)),
                QPoint(8,  -(R - 3)),
            ])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(Qt.white))
            painter.drawPolygon(arrow)

            painter.restore()

            label = 'L1' if robot == 'limo1' else 'L2'
            painter.setPen(color)
            painter.setFont(QFont('Segoe UI', 9, QFont.Bold))
            painter.drawText(px + R + 6, py - 4, label)


# ── 로봇 상태 카드 ────────────────────────────────────────────────────

class RobotStatusCard(QFrame):
    def __init__(self, robot_id: str, on_click=None):
        super().__init__()
        self._robot_id = robot_id
        self._status   = 'UNKNOWN'
        self._on_click = on_click
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if on_click:
            self.setCursor(Qt.PointingHandCursor)
        self._build_ui()
        self._apply_border()

    def _build_ui(self) -> None:
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(12, 10, 12, 10)
        hbox.setSpacing(10)

        self._avatar = QLabel('🤖')
        self._avatar.setFixedSize(38, 38)
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setFont(QFont('Segoe UI', 18))
        self._avatar.setStyleSheet(
            f'border-radius:9px; background:{STATUS_BG["UNKNOWN"]}; border:none;'
        )
        hbox.addWidget(self._avatar)

        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(2)
        info_vbox.setContentsMargins(0, 0, 0, 0)

        name = 'LIMO 1' if self._robot_id == 'limo1' else 'LIMO 2'
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont('Segoe UI', 13, QFont.Bold))
        name_lbl.setStyleSheet('color:#111827; border:none;')

        self._dest_lbl = QLabel('방문자 대기 중')
        self._dest_lbl.setFont(QFont('Segoe UI', 11))
        self._dest_lbl.setStyleSheet('color:#6b7280; border:none;')

        self._sub_lbl = QLabel('배터리 -- %')
        self._sub_lbl.setFont(QFont('Segoe UI', 10))
        self._sub_lbl.setStyleSheet('color:#9ca3af; border:none;')

        info_vbox.addWidget(name_lbl)
        info_vbox.addWidget(self._dest_lbl)
        info_vbox.addWidget(self._sub_lbl)
        hbox.addLayout(info_vbox, 1)

        self._badge = QLabel('UNKNOWN')
        self._badge.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setStyleSheet(
            f'border-radius:10px; padding:2px 6px; border:none;'
            f'color:{STATUS_COLOR["UNKNOWN"]}; background:{STATUS_BG["UNKNOWN"]};'
        )
        hbox.addWidget(self._badge)

    def _apply_border(self) -> None:
        border = STATUS_BORDER.get(self._status, STATUS_BORDER['UNKNOWN'])
        bg     = STATUS_BG.get(self._status, STATUS_BG['UNKNOWN'])
        # Qt에서 border 단축형 후 border-left 오버라이드가 불안정하므로 4방향 개별 지정
        self.setStyleSheet(
            f'background:#fff; border-radius:10px;'
            f'border-top:1px solid #e5e7eb;'
            f'border-right:1px solid #e5e7eb;'
            f'border-bottom:1px solid #e5e7eb;'
            f'border-left:4px solid {border};'
        )
        self._avatar.setStyleSheet(
            f'border-radius:9px; background:{bg}; border:none;'
        )

    def update_status(self, status: str) -> None:
        self._status = status
        self._apply_border()
        c  = STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN'])
        bg = STATUS_BG.get(status, STATUS_BG['UNKNOWN'])
        self._badge.setText(status)
        self._badge.setStyleSheet(
            f'border-radius:10px; padding:2px 6px; border:none;'
            f'color:{c}; background:{bg};'
        )
        if status == 'IDLE':
            self._dest_lbl.setText('방문자 대기 중')

    def update_battery(self, voltage: float) -> None:
        pct = max(0.0, min(100.0, (voltage - 9.0) / (12.6 - 9.0) * 100.0))
        self._sub_lbl.setText(f'배터리 {pct:.0f}%')

    def update_destination(self, dest: str) -> None:
        if dest:
            self._dest_lbl.setText(f'→ {dest}')

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and self._on_click:
            self._on_click()


# ── 미니 이벤트 로그 카드 ─────────────────────────────────────────────

class MiniLogCard(QFrame):
    """GUI 이벤트(버튼 조작, 상태 전이)를 실시간으로 표시하는 로컬 로그."""

    _MAX_ROWS = 50

    def __init__(self):
        super().__init__()
        self.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 12, 14, 10)
        vbox.setSpacing(6)

        title = QLabel('📋 이벤트 로그')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        vbox.addWidget(title)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(['시각', '로봇', '내용'])
        self._table.horizontalHeader().setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setFont(QFont('Segoe UI', 9))
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.setStyleSheet(
            'QTableWidget { border:none; background:#fff; }'
            'QHeaderView::section { background:#f8fafc; border:none;'
            '  border-bottom:1px solid #e5e7eb; padding:3px; }'
            'QTableWidget::item { padding:2px 4px; }'
        )
        vbox.addWidget(self._table, 1)

    def add_log(self, log_type: str, robot: str, message: str) -> None:
        ts = datetime.now().strftime('%H:%M:%S')
        bg, fg = LOG_TYPE_COLOR.get(log_type, ('#fff', '#374151'))
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, text in enumerate([ts, robot, message]):
            item = QTableWidgetItem(text)
            item.setForeground(QColor(fg))
            item.setBackground(QColor(bg))
            self._table.setItem(row, col, item)
        self._table.scrollToBottom()
        while self._table.rowCount() > self._MAX_ROWS:
            self._table.removeRow(0)


# ── 메인 뷰 ──────────────────────────────────────────────────────────

_PAUSE_NORMAL  = 'background:#fef3c7; color:#b45309; border:1.5px solid #fcd34d; border-radius:6px;'
_RESUME_NORMAL = 'background:#d1fae5; color:#065f46; border:1.5px solid #6ee7b7; border-radius:6px;'
_ABORT_NORMAL  = 'background:#fee2e2; color:#b91c1c; border:1.5px solid #fca5a5; border-radius:6px;'
_PAUSE_FLASH   = 'background:#b45309; color:#fff;    border:1.5px solid #b45309; border-radius:6px;'
_RESUME_FLASH  = 'background:#065f46; color:#fff;    border:1.5px solid #065f46; border-radius:6px;'
_ABORT_FLASH   = 'background:#b91c1c; color:#fff;    border:1.5px solid #b91c1c; border-radius:6px;'


class MapView(QWidget):
    def __init__(self, ros_node, switch_view_cb=None):
        super().__init__()
        self.setStyleSheet('background:#f0f2f5;')
        self.ros = ros_node
        self._selected_robot = 'limo1'
        self._switch_view_cb = switch_view_cb
        self._build_ui()
        self._connect_signals()

        self._conn_timer = QTimer()
        self._conn_timer.timeout.connect(self._check_connections)
        self._conn_timer.start(2000)

    def _build_ui(self) -> None:
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(10, 10, 10, 10)
        hbox.setSpacing(10)

        # ── 좌열 (260px): 로봇 카드 + 미니 로그 ──
        left = QWidget()
        left.setFixedWidth(260)
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(8)

        # 로봇 카드 (168px — 목업 grid-template-rows:168px)
        cards_area = QWidget()
        cards_area.setFixedHeight(168)
        cards_vbox = QVBoxLayout(cards_area)
        cards_vbox.setContentsMargins(0, 0, 0, 0)
        cards_vbox.setSpacing(8)
        self._card1 = RobotStatusCard('limo1', on_click=lambda: self._navigate_to_robot('limo1'))
        self._card2 = RobotStatusCard('limo2', on_click=lambda: self._navigate_to_robot('limo2'))
        cards_vbox.addWidget(self._card1)
        cards_vbox.addWidget(self._card2)
        left_vbox.addWidget(cards_area)

        # 미니 로그 (나머지 공간)
        self._mini_log = MiniLogCard()
        left_vbox.addWidget(self._mini_log, 1)
        hbox.addWidget(left)

        # ── 중앙: 지도 패널 (카드 + 타이틀 + 캔버스) ──
        map_card = QFrame()
        map_card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        map_card_vbox = QVBoxLayout(map_card)
        map_card_vbox.setContentsMargins(14, 12, 14, 14)
        map_card_vbox.setSpacing(8)

        map_title = QLabel('🗺  실시간 위치')
        map_title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        map_title.setStyleSheet(CARD_TITLE_STYLE)
        map_card_vbox.addWidget(map_title)

        self._canvas = MapCanvas()
        map_card_vbox.addWidget(self._canvas, 1)
        hbox.addWidget(map_card, 1)

        # ── 우열 (260px): 제어 패널 ──
        right = QWidget()
        right.setFixedWidth(260)
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(8)
        right_vbox.addWidget(self._build_emergency_card())
        right_vbox.addWidget(self._build_sys_card(), 1)
        hbox.addWidget(right)

    def _build_emergency_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        title = QLabel('⚠️  긴급 제어')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        vbox.addWidget(title)

        # 로봇 선택 토글
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        self._rsel_btns: dict[str, QPushButton] = {}
        for robot_id, label in (('limo1', 'LIMO 1'), ('limo2', 'LIMO 2')):
            btn = QPushButton(label)
            btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
            btn.setFixedHeight(32)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(self._rsel_style(robot_id == 'limo1'))
            btn.clicked.connect(lambda _, r=robot_id: self._select_robot(r))
            self._rsel_btns[robot_id] = btn
            toggle_row.addWidget(btn)
        vbox.addLayout(toggle_row)

        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self._pause_btn = QPushButton('⏸ 일시정지')
        self._pause_btn.setFixedHeight(34)
        self._pause_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        self._pause_btn.setFocusPolicy(Qt.NoFocus)
        self._pause_btn.setStyleSheet(_PAUSE_NORMAL)
        self._pause_btn.clicked.connect(self._send_pause)
        row1.addWidget(self._pause_btn)

        self._resume_btn = QPushButton('▶ 재개')
        self._resume_btn.setFixedHeight(34)
        self._resume_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        self._resume_btn.setFocusPolicy(Qt.NoFocus)
        self._resume_btn.setStyleSheet(_RESUME_NORMAL)
        self._resume_btn.clicked.connect(self._send_resume)
        row1.addWidget(self._resume_btn)
        vbox.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self._abort_btn = QPushButton('🛑 임무중단 (홈 복귀)')
        self._abort_btn.setFixedHeight(34)
        self._abort_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        self._abort_btn.setFocusPolicy(Qt.NoFocus)
        self._abort_btn.setStyleSheet(_ABORT_NORMAL)
        self._abort_btn.clicked.connect(self._send_abort_home)
        row2.addWidget(self._abort_btn)
        vbox.addLayout(row2)

        return card

    def _build_sys_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)

        title = QLabel('📡  시스템 상태')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        outer.addWidget(title)

        # 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet('background:transparent;')

        inner = QWidget()
        inner.setStyleSheet('background:transparent;')
        vbox = QVBoxLayout(inner)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self._sys_vals: dict[str, QLabel] = {}
        rows = [
            ('limo1_conn', 'LIMO 1',  '● 확인 중', '#9ca3af'),
            ('limo2_conn', 'LIMO 2',  '● 확인 중', '#9ca3af'),
            ('map_server', '맵 서버',       '● 확인 중', '#9ca3af'),
            ('fastapi',    'FastAPI',       '● 확인 중', '#9ca3af'),
            ('dispatcher', '배차 노드',     '● 확인 중', '#9ca3af'),
            ('traffic',    '충돌 방지',     '● 확인 중', '#9ca3af'),
        ]
        for key, label, init_txt, init_color in rows:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet('border:none; border-top:1px solid #f3f4f6;')
            vbox.addWidget(sep)

            row_w = QWidget()
            row_w.setStyleSheet('background:transparent;')
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(8, 5, 8, 5)
            rh.setSpacing(8)

            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 11))
            lbl.setStyleSheet('color:#6b7280; border:none;')
            rh.addWidget(lbl)
            rh.addStretch()

            val = QLabel(init_txt)
            val.setFont(QFont('Segoe UI', 11, QFont.Bold))
            val.setStyleSheet(f'color:{init_color}; border:none;')
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rh.addWidget(val)

            self._sys_vals[key] = val
            vbox.addWidget(row_w)

        vbox.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return card

    # ── 시그널 연결 ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.ros.signals.sig_status_1.connect(
            lambda s: (self._card1.update_status(s), self._canvas.update_status('limo1', s)))
        self.ros.signals.sig_status_2.connect(
            lambda s: (self._card2.update_status(s), self._canvas.update_status('limo2', s)))
        self.ros.signals.sig_pose_1.connect(lambda m: self._canvas.update_pose('limo1', m))
        self.ros.signals.sig_pose_2.connect(lambda m: self._canvas.update_pose('limo2', m))
        self.ros.signals.sig_map.connect(self._canvas.update_map)
        self.ros.signals.sig_dest_1.connect(self._card1.update_destination)
        self.ros.signals.sig_dest_2.connect(self._card2.update_destination)
        self.ros.signals.sig_battery_1.connect(self._card1.update_battery)
        self.ros.signals.sig_battery_2.connect(self._card2.update_battery)
        self.ros.signals.sig_gui_log.connect(self._mini_log.add_log)

        if self.ros.latest_map is not None:
            self._canvas.update_map(self.ros.latest_map)

    # ── 동작 ─────────────────────────────────────────────────────────

    def _navigate_to_robot(self, robot: str) -> None:
        if self._switch_view_cb:
            self._switch_view_cb(robot)

    def _select_robot(self, robot: str) -> None:
        self._selected_robot = robot
        for r, btn in self._rsel_btns.items():
            btn.setStyleSheet(self._rsel_style(r == robot))

    @staticmethod
    def _flash_btn(btn: QPushButton, flash_style: str, normal_style: str) -> None:
        btn.setStyleSheet(flash_style)
        QTimer.singleShot(220, lambda: btn.setStyleSheet(normal_style))

    def _send_pause(self) -> None:
        label = 'LIMO 1' if self._selected_robot == 'limo1' else 'LIMO 2'
        self.ros.publish_pause(self._selected_robot)
        self.ros.signals.sig_gui_log.emit('waiting', label, '일시정지')
        self._flash_btn(self._pause_btn, _PAUSE_FLASH, _PAUSE_NORMAL)

    def _send_resume(self) -> None:
        label = 'LIMO 1' if self._selected_robot == 'limo1' else 'LIMO 2'
        self.ros.publish_resume(self._selected_robot)
        self.ros.signals.sig_gui_log.emit('system', label, '재개')
        self._flash_btn(self._resume_btn, _RESUME_FLASH, _RESUME_NORMAL)

    def _send_abort_home(self) -> None:
        label = 'LIMO 1' if self._selected_robot == 'limo1' else 'LIMO 2'
        self.ros.publish_abort(self._selected_robot)
        self.ros.signals.sig_gui_log.emit('mission_fail', label, '임무중단')
        self._flash_btn(self._abort_btn, _ABORT_FLASH, _ABORT_NORMAL)

    def _check_connections(self) -> None:
        for robot, key in (('limo1', 'limo1_conn'), ('limo2', 'limo2_conn')):
            val = self._sys_vals[key]
            if self.ros.is_connected(robot):
                val.setText('● 연결')
                val.setStyleSheet('color:#059669; border:none;')
            else:
                val.setText('● 미연결')
                val.setStyleSheet('color:#ef4444; border:none;')

        val = self._sys_vals['map_server']
        if self.ros.latest_map is not None:
            val.setText('● 연결')
            val.setStyleSheet('color:#059669; border:none;')
        else:
            val.setText('● 미연결')
            val.setStyleSheet('color:#ef4444; border:none;')

        if not hasattr(self, '_api_checker') or not self._api_checker.isRunning():
            self._api_checker = _FastApiChecker()
            self._api_checker.done.connect(self._on_fastapi_result)
            self._api_checker.start()

        try:
            node_names = self.ros.get_node_names()
            for key, node_name in (
                ('dispatcher', 'wego_dispatcher'),
                ('traffic',    'wego_traffic'),
            ):
                val = self._sys_vals[key]
                if node_name in node_names:
                    val.setText('● 연결')
                    val.setStyleSheet('color:#059669; border:none;')
                else:
                    val.setText('● 미연결')
                    val.setStyleSheet('color:#ef4444; border:none;')
        except Exception:
            pass

    def _on_fastapi_result(self, ok: bool) -> None:
        val = self._sys_vals['fastapi']
        if ok:
            val.setText('● 연결')
            val.setStyleSheet('color:#059669; border:none;')
        else:
            val.setText('● 미연결')
            val.setStyleSheet('color:#ef4444; border:none;')

    @staticmethod
    def _rsel_style(active: bool) -> str:
        if active:
            return ('background:#eff6ff; color:#1e40af; border:1.5px solid #1e40af;'
                    'border-radius:6px; padding:4px;')
        return ('background:#f9fafb; color:#374151; border:1.5px solid #e5e7eb;'
                'border-radius:6px; padding:4px;')
