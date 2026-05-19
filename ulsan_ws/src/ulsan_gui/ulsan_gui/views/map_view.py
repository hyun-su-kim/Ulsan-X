import math

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QImage, QPixmap, QPainter, QColor, QPen, QBrush

STATUS_COLOR = {
    'IDLE':      '#16a34a',
    'BUSY':      '#d97706',
    'RETURNING': '#2563eb',
    'WAITING':   '#9333ea',
    'UNKNOWN':   '#9ca3af',
}
STATUS_BG = {
    'IDLE':      '#f0fdf4',
    'BUSY':      '#fffbeb',
    'RETURNING': '#eff6ff',
    'WAITING':   '#faf5ff',
    'UNKNOWN':   '#f8fafc',
}


class MapCanvas(QWidget):
    """OccupancyGrid + 로봇 마커 렌더링."""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._map_pixmap: QPixmap | None = None
        self._map_info   = None
        self._poses: dict[str, tuple | None] = {'limo1': None, 'limo2': None}
        self._robot_colors = {'limo1': QColor('#2563eb'), 'limo2': QColor('#d97706')}

    def update_map(self, msg) -> None:
        info = msg.info
        w, h = info.width, info.height
        data = msg.data

        img = QImage(w, h, QImage.Format_RGB888)
        for y in range(h):
            for x in range(w):
                v = data[y * w + x]
                if v == -1:
                    c = 200
                elif v == 0:
                    c = 255
                else:
                    c = 0
                img.setPixel(x, h - 1 - y, QColor(c, c, c).rgb())

        self._map_pixmap = QPixmap.fromImage(img)
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

    def paintEvent(self, _) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor('#1e293b'))

        if self._map_pixmap is None:
            painter.setPen(QColor('#64748b'))
            painter.drawText(self.rect(), Qt.AlignCenter, '/map 토픽 대기 중...')
            return

        info = self._map_info
        scale = min(w / info.width, h / info.height)
        draw_w = int(info.width  * scale)
        draw_h = int(info.height * scale)
        off_x  = (w - draw_w) // 2
        off_y  = (h - draw_h) // 2

        painter.drawPixmap(off_x, off_y, draw_w, draw_h, self._map_pixmap)

        # 로봇 마커
        for robot, pose in self._poses.items():
            if pose is None:
                continue
            rx, ry, ryaw = pose
            px = off_x + int((rx - info.origin.position.x) / info.resolution * scale)
            py = off_y + draw_h - int((ry - info.origin.position.y) / info.resolution * scale)

            color = self._robot_colors[robot]
            # 방향 화살표
            painter.save()
            painter.translate(px, py)
            painter.rotate(-math.degrees(ryaw))
            painter.setPen(QPen(color, 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(-8, -8, 16, 16)
            painter.setPen(QPen(Qt.white, 2))
            painter.drawLine(0, 0, 0, -12)
            painter.restore()

            # 라벨
            label = 'L1' if robot == 'limo1' else 'L2'
            painter.setPen(Qt.white)
            painter.setFont(QFont('Segoe UI', 8, QFont.Bold))
            painter.drawText(px + 10, py - 4, label)


class RobotCard(QFrame):
    def __init__(self, robot_name: str):
        super().__init__()
        self.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(4)

        top = QHBoxLayout()
        self._name_label  = QLabel(robot_name)
        self._name_label.setFont(QFont('Segoe UI', 12, QFont.Bold))
        self._name_label.setStyleSheet('border:none; color:#111827;')

        self._status_badge = QLabel('UNKNOWN')
        self._status_badge.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._status_badge.setStyleSheet(
            'border-radius:8px; padding:2px 8px; border:none;'
            f'color:{STATUS_COLOR["UNKNOWN"]}; background:{STATUS_BG["UNKNOWN"]};'
        )
        top.addWidget(self._name_label)
        top.addStretch()
        top.addWidget(self._status_badge)
        vbox.addLayout(top)

        self._conn_label = QLabel('● 연결 대기')
        self._conn_label.setFont(QFont('Segoe UI', 10))
        self._conn_label.setStyleSheet('color:#9ca3af; border:none;')
        vbox.addWidget(self._conn_label)

    def update_status(self, status: str) -> None:
        self._status_badge.setText(status)
        c  = STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN'])
        bg = STATUS_BG.get(status, STATUS_BG['UNKNOWN'])
        self._status_badge.setStyleSheet(
            f'border-radius:8px; padding:2px 8px; border:none; color:{c}; background:{bg};'
        )

    def update_conn(self, connected: bool) -> None:
        if connected:
            self._conn_label.setText('● 연결됨')
            self._conn_label.setStyleSheet('color:#16a34a; border:none;')
        else:
            self._conn_label.setText('● 연결 끊김')
            self._conn_label.setStyleSheet('color:#ef4444; border:none;')


class MapView(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros = ros_node
        self._build_ui()
        self._connect_signals()

        # 연결 상태 체크 타이머
        self._conn_timer = QTimer()
        self._conn_timer.timeout.connect(self._check_connections)
        self._conn_timer.start(2000)

    def _build_ui(self) -> None:
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(10, 10, 10, 10)
        hbox.setSpacing(10)

        # ── 좌: 지도 캔버스 ──
        self._canvas = MapCanvas()
        self._canvas.setStyleSheet('background:#1e293b; border-radius:10px;')
        hbox.addWidget(self._canvas, 3)

        # ── 우: 컨트롤 패널 ──
        right = QVBoxLayout()
        right.setSpacing(10)

        # 로봇 상태 카드
        self._card1 = RobotCard('LIMO 1')
        self._card2 = RobotCard('LIMO 2')
        right.addWidget(self._card1)
        right.addWidget(self._card2)

        # 수동 임무 발행
        mission_card = self._build_mission_card()
        right.addWidget(mission_card)

        # 시스템 상태
        sys_card = self._build_sys_card()
        right.addWidget(sys_card)

        right.addStretch()

        # 비상정지
        estop = QPushButton('🛑  비상 정지')
        estop.setFixedHeight(44)
        estop.setFont(QFont('Segoe UI', 12, QFont.Bold))
        estop.setStyleSheet(
            'background:#dc2626; color:#fff; border-radius:10px; border:none;'
        )
        estop.clicked.connect(self._emergency_stop)
        right.addWidget(estop)

        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setFixedWidth(260)
        hbox.addWidget(right_widget)

    def _build_mission_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)

        title = QLabel('🎯 수동 임무 발행')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet('color:#111827; border:none;')
        vbox.addWidget(title)

        self._robot_combo = QComboBox()
        self._robot_combo.addItems(['LIMO 1', 'LIMO 2'])
        self._robot_combo.setStyleSheet('border:1px solid #d1d5db; border-radius:6px; padding:4px;')
        vbox.addWidget(self._robot_combo)

        self._dest_combo = QComboBox()
        self._dest_combo.setStyleSheet('border:1px solid #d1d5db; border-radius:6px; padding:4px;')
        vbox.addWidget(self._dest_combo)
        QTimer.singleShot(800, self._refresh_destinations)

        send_btn = QPushButton('임무 발행')
        send_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border-radius:6px; padding:6px; border:none;'
        )
        send_btn.clicked.connect(self._send_mission)
        vbox.addWidget(send_btn)

        return card

    def _build_sys_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(6)

        title = QLabel('📡 시스템 상태')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet('color:#111827; border:none;')
        vbox.addWidget(title)

        self._sys_limo1 = QLabel('LIMO 1  ● 대기')
        self._sys_limo2 = QLabel('LIMO 2  ● 대기')
        for lbl in (self._sys_limo1, self._sys_limo2):
            lbl.setFont(QFont('Segoe UI', 10))
            lbl.setStyleSheet('color:#9ca3af; border:none;')
            vbox.addWidget(lbl)

        return card

    def _connect_signals(self) -> None:
        self.ros.signals.sig_status_1.connect(lambda s: self._card1.update_status(s))
        self.ros.signals.sig_status_2.connect(lambda s: self._card2.update_status(s))
        self.ros.signals.sig_pose_1.connect(lambda m: self._canvas.update_pose('limo1', m))
        self.ros.signals.sig_pose_2.connect(lambda m: self._canvas.update_pose('limo2', m))
        self.ros.signals.sig_map.connect(self._canvas.update_map)

    def _refresh_destinations(self) -> None:
        self._dest_combo.clear()
        result = self.ros.call_waypoint_crud('list')
        if result['success']:
            import json
            wps = json.loads(result['waypoints_json'])
            for key, wp in wps.items():
                self._dest_combo.addItem(f"{wp['label']} ({key})", userData=key)
        else:
            self._dest_combo.addItem('(waypoint 조회 실패)')

    def _send_mission(self) -> None:
        robot = 'limo1' if self._robot_combo.currentIndex() == 0 else 'limo2'
        key   = self._dest_combo.currentData()
        if key:
            self.ros.publish_goal(robot, key)

    def _emergency_stop(self) -> None:
        for robot in ('limo1', 'limo2'):
            self.ros.publish_cmd_vel(robot, 0.0, 0.0)

    def _check_connections(self) -> None:
        for robot, lbl in (('limo1', self._sys_limo1), ('limo2', self._sys_limo2)):
            name = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'
            card = self._card1 if robot == 'limo1' else self._card2
            conn = self.ros.is_connected(robot)
            card.update_conn(conn)
            if conn:
                lbl.setText(f'{name}  ● 연결됨')
                lbl.setStyleSheet('color:#16a34a; border:none;')
            else:
                lbl.setText(f'{name}  ● 연결 끊김')
                lbl.setStyleSheet('color:#ef4444; border:none;')
