from datetime import date as date_type

import requests
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QDateEdit, QMessageBox,
    QCalendarWidget,
)
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QFont, QColor, QTextCharFormat
from PyQt5.QtWidgets import QApplication

from ulsan_gui.http_thread import HttpGetThread
from ulsan_gui.ros_node import FASTAPI_URL

API_BASE = FASTAPI_URL

STATUS_LABEL = {
    'PENDING':     '대기',
    'IN_PROGRESS': '안내 중',
    'COMPLETED':   '완료',
}

STATUS_COLOR = {
    'PENDING':     ('#fffbeb', '#d97706'),
    'IN_PROGRESS': ('#eff6ff', '#1d4ed8'),
    'COMPLETED':   ('#f0fdf4', '#15803d'),
}

COLUMNS = ['ID', '이름', '전화번호', '날짜', '시간대', '교실', '상태']

_BTN_STYLE = (
    'background:#f1f5f9; border:1px solid #e2e8f0; border-radius:6px;'
    'padding:0 12px; font-size:12px; color:#374151;'
)
_COMBO_STYLE = (
    'QComboBox { border:1px solid #d1d5db; border-radius:6px; padding:4px 10px;'
    '  background:#fff; color:#111827; min-width:80px; }'
    'QComboBox::drop-down { border:none; width:18px; }'
    'QComboBox QAbstractItemView {'
    '  background:#fff; color:#111827; border:1px solid #d1d5db;'
    '  selection-background-color:#eff6ff; selection-color:#1e40af; outline:0; }'
)


# ── 예약 추가 / 수정 다이얼로그 ──────────────────────────────────────────

class _ReservationDialog(QDialog):
    def __init__(self, parent=None, data: dict = None):
        super().__init__(parent)
        self._is_edit = data is not None
        self.setWindowTitle('예약 수정' if self._is_edit else '예약 추가')
        self.setFixedWidth(340)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        field_style = (
            'border:1px solid #d1d5db; border-radius:6px;'
            'padding:5px 8px; font-size:13px;'
        )

        if not self._is_edit:
            self._name = QLineEdit()
            self._name.setPlaceholderText('홍길동')
            self._name.setStyleSheet(field_style)
            form.addRow('이름', self._name)

            self._phone = QLineEdit()
            self._phone.setPlaceholderText('01012345678')
            self._phone.setStyleSheet(field_style)
            form.addRow('전화번호', self._phone)

        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setMinimumDate(QDate.currentDate())
        self._date_edit.setMaximumDate(QDate.currentDate().addDays(14))
        self._date_edit.setStyleSheet(field_style)
        form.addRow('날짜', self._date_edit)

        self._time_combo = QComboBox()
        self._time_combo.setStyleSheet(_COMBO_STYLE)
        for h in range(9, 18):
            self._time_combo.addItem(f'{h:02d}:00', userData=h)
        form.addRow('시간대', self._time_combo)

        layout.addLayout(form)

        if self._is_edit and data:
            raw_date = data.get('date', '')
            if raw_date:
                parts = raw_date.split('-')
                if len(parts) == 3:
                    self._date_edit.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
            ts = data.get('time_slot', 9)
            self._time_combo.setCurrentIndex(max(0, ts - 9))

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('border:none; border-top:1px solid #f3f4f6;')
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton('취소')
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet(_BTN_STYLE)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton('저장')
        ok_btn.setFixedHeight(34)
        ok_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none;'
            'border-radius:6px; font-size:13px; padding:0 12px;'
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        d = self._date_edit.date()
        result = {
            'date': f'{d.year()}-{d.month():02d}-{d.day():02d}',
            'time_slot': self._time_combo.currentData(),
        }
        if not self._is_edit:
            result['name']  = self._name.text().strip()
            result['phone'] = self._phone.text().strip()
        return result


# ── 메인 뷰 ──────────────────────────────────────────────────────────

class ReservationView(QWidget):
    def __init__(self):
        super().__init__()
        self._all_data: list[dict] = []
        self._build_ui()

        self._scroll_top_next = False

        # HTTP GET 스레드 단일 인스턴스 재사용 — 폴링/이벤트마다 새 QThread 생성 방지
        # (재할당 시 실행 중 스레드 참조가 끊겨 'QThread destroyed while running' 크래시 위험)
        self._thread = HttpGetThread(f'{API_BASE}/reservations/')
        self._thread.done.connect(self._on_fetched)

        self._timer = QTimer()
        self._timer.timeout.connect(self._fetch)
        self._timer.start(5000)
        self._fetch()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        # ── 툴바 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title = QLabel('📅 예약 목록')
        title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        title.setStyleSheet('color:#111827;')
        toolbar.addWidget(title)
        toolbar.addSpacing(4)

        self._count_lbl = QLabel('전체 0건')
        self._count_lbl.setFont(QFont('Segoe UI', 11))
        self._count_lbl.setStyleSheet('color:#6b7280;')
        toolbar.addWidget(self._count_lbl)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText('🔍 이름 / 전화번호')
        self._search.setFixedWidth(180)
        self._search.setStyleSheet(
            'border:1px solid #d1d5db; border-radius:6px; padding:5px 10px; font-size:12px;'
        )
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search)

        self._status_combo = QComboBox()
        self._status_combo.addItems(['전체', '대기', '안내 중', '완료'])
        self._status_combo.setStyleSheet(_COMBO_STYLE)
        self._status_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._status_combo)

        self._cal_btn = QPushButton('📅 날짜 이동')
        self._cal_btn.setFixedHeight(30)
        self._cal_btn.setStyleSheet(_BTN_STYLE)
        self._cal_btn.clicked.connect(self._show_calendar)
        toolbar.addWidget(self._cal_btn)

        refresh_btn = QPushButton('🔄 새로고침')
        refresh_btn.setFixedHeight(30)
        refresh_btn.setStyleSheet(_BTN_STYLE)
        refresh_btn.clicked.connect(self._manual_refresh)
        toolbar.addWidget(refresh_btn)

        add_btn = QPushButton('＋ 예약 추가')
        add_btn.setFixedHeight(30)
        add_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none;'
            'border-radius:6px; padding:0 12px; font-size:12px;'
        )
        add_btn.clicked.connect(self._add)
        toolbar.addWidget(add_btn)

        vbox.addLayout(toolbar)

        # ── 테이블 ──
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        hdr = self._table.horizontalHeader()
        hdr.setFont(QFont('Segoe UI', 10, QFont.Bold))
        hdr.setSectionResizeMode(QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)   # 교실만 늘어남
        self._table.setFont(QFont('Segoe UI', 11))
        self._table.setAlternatingRowColors(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(30)
        self._table.setColumnHidden(0, True)
        # 컬럼 너비 (ID 숨김, 이름~상태)
        self._table.setColumnWidth(1, 80)    # 이름
        self._table.setColumnWidth(2, 115)   # 전화번호
        self._table.setColumnWidth(3, 95)    # 날짜
        self._table.setColumnWidth(4, 58)    # 시간대
        # 5: 교실 (Stretch)
        self._table.setColumnWidth(6, 72)    # 상태
        self._table.setStyleSheet(
            'QTableWidget { border:1px solid #e5e7eb; border-radius:8px;'
            '  background:#fff; gridline-color:#f3f4f6; }'
            'QHeaderView::section { background:#f8fafc; border:none;'
            '  border-bottom:1px solid #e5e7eb; padding:6px; }'
            'QTableWidget::item:selected { background:#eff6ff; color:#1e40af; }'
        )
        self._table.doubleClicked.connect(self._edit)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        vbox.addWidget(self._table, 1)

        # ── 액션 바 ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self._status_label = QLabel('행을 선택하면 작업을 실행할 수 있습니다.')
        self._status_label.setFont(QFont('Segoe UI', 11))
        self._status_label.setStyleSheet('color:#9ca3af;')
        action_bar.addWidget(self._status_label)
        action_bar.addStretch()

        self._btn_pending = QPushButton('대기로 변경')
        self._btn_inprogress = QPushButton('안내 중으로 변경')
        self._btn_completed = QPushButton('완료로 변경')
        self._btn_edit = QPushButton('✏ 수정')
        self._btn_delete = QPushButton('🗑 삭제')

        for btn, color in (
            (self._btn_pending,    '#f59e0b'),
            (self._btn_inprogress, '#2563eb'),
            (self._btn_completed,  '#16a34a'),
        ):
            btn.setFixedHeight(30)
            btn.setStyleSheet(
                f'background:{color}; color:#fff; border:none;'
                'border-radius:6px; padding:0 10px; font-size:12px;'
            )
            btn.setEnabled(False)
            action_bar.addWidget(btn)

        self._btn_edit.setFixedHeight(30)
        self._btn_edit.setStyleSheet(_BTN_STYLE)
        self._btn_edit.setEnabled(False)
        action_bar.addWidget(self._btn_edit)

        self._btn_delete.setFixedHeight(30)
        self._btn_delete.setStyleSheet(
            'background:#fee2e2; color:#b91c1c; border:1.5px solid #fca5a5;'
            'border-radius:6px; padding:0 10px; font-size:12px;'
        )
        self._btn_delete.setEnabled(False)
        action_bar.addWidget(self._btn_delete)

        self._btn_pending.clicked.connect(lambda: self._change_status('PENDING'))
        self._btn_inprogress.clicked.connect(lambda: self._change_status('IN_PROGRESS'))
        self._btn_completed.clicked.connect(lambda: self._change_status('COMPLETED'))
        self._btn_edit.clicked.connect(self._edit)
        self._btn_delete.clicked.connect(self._delete)

        vbox.addLayout(action_bar)

    # ── 데이터 ────────────────────────────────────────────────────────

    def _manual_refresh(self) -> None:
        self._scroll_top_next = True
        self._fetch()

    def _fetch(self) -> None:
        if not self._thread.isRunning():
            self._thread.start()

    def _on_fetched(self, response) -> None:
        self._all_data = response.json() if response is not None else []
        self._apply_filter()
        if self._scroll_top_next:
            self._table.scrollToTop()
            self._scroll_top_next = False

    def _apply_filter(self) -> None:
        keyword    = self._search.text().lower()
        status_idx = self._status_combo.currentIndex()
        status_map = {1: 'PENDING', 2: 'IN_PROGRESS', 3: 'COMPLETED'}

        filtered = []
        for row in self._all_data:
            if status_idx > 0 and row.get('status') != status_map.get(status_idx):
                continue
            searchable = f"{row.get('name','')} {row.get('phone','')}".lower()
            if keyword and keyword not in searchable:
                continue
            filtered.append(row)

        self._render(filtered)

    def _render(self, rows: list) -> None:
        self._table.clearSpans()   # 이전 렌더링의 span 잔재 제거

        # 날짜 내림차순 → 시간대 오름차순 그룹
        groups: dict[str, list] = {}
        for row in rows:
            d = row.get('date', '')
            groups.setdefault(d, []).append(row)
        sorted_dates = sorted(groups.keys(), reverse=True)
        for d in sorted_dates:
            groups[d].sort(key=lambda r: r.get('time_slot', 0))

        total_rows = sum(1 + len(groups[d]) for d in sorted_dates)
        self._table.setRowCount(total_rows)
        self._date_row_map: dict[str, int] = {}

        tr = 0
        for d in sorted_dates:
            # ── 날짜 헤더 행 ──
            self._date_row_map[d] = tr
            header = QTableWidgetItem(f'  {d}  ·  {len(groups[d])}건')
            header.setFont(QFont('Segoe UI', 10, QFont.Bold))
            header.setForeground(QColor('#1e40af'))
            header.setBackground(QColor('#eff6ff'))
            header.setFlags(Qt.ItemIsEnabled)   # 선택 불가
            self._table.setItem(tr, 1, header)
            self._table.setSpan(tr, 1, 1, 6)
            self._table.setRowHeight(tr, 24)
            tr += 1

            # ── 데이터 행 ──
            for item in groups[d]:
                status = item.get('status', 'PENDING')
                bg, fg = STATUS_COLOR.get(status, ('#fff', '#374151'))
                cells = [
                    str(item.get('id', '')),
                    item.get('name', ''),
                    item.get('phone', ''),
                    str(item.get('date', '')),
                    f"{item.get('time_slot', '')}:00",
                    item.get('room', ''),
                    STATUS_LABEL.get(status, status),
                ]
                for c, text in enumerate(cells):
                    cell = QTableWidgetItem(text)
                    cell.setTextAlignment(Qt.AlignCenter)
                    cell.setForeground(QColor(fg))
                    cell.setBackground(QColor(bg))
                    self._table.setItem(tr, c, cell)
                tr += 1

        self._count_lbl.setText(f'전체 {len(rows)}건')

    def _show_calendar(self) -> None:
        popup = QDialog(self)
        popup.setWindowFlags(Qt.Popup)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(6, 6, 6, 6)

        cal = QCalendarWidget()
        cal.setGridVisible(True)
        cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setMinimumSize(320, 240)
        cal.setStyleSheet(
            'QCalendarWidget QWidget#qt_calendar_navigationbar {'
            '  background:#1e40af;'
            '}'
            'QCalendarWidget QToolButton {'
            '  color:#ffffff; font-size:13px; font-weight:600;'
            '  background:transparent; border:none;'
            '}'
            'QCalendarWidget QToolButton:hover {'
            '  background:#1d4ed8; border-radius:4px;'
            '}'
            'QCalendarWidget QSpinBox { color:#ffffff; background:transparent; border:none; }'
        )

        # 주말 회색 처리
        weekend_fmt = QTextCharFormat()
        weekend_fmt.setForeground(QColor('#d1d5db'))
        weekend_fmt.setBackground(QColor('#f9fafb'))
        cal.setWeekdayTextFormat(Qt.Saturday, weekend_fmt)
        cal.setWeekdayTextFormat(Qt.Sunday, weekend_fmt)

        def _on_date_clicked(d: QDate) -> None:
            if d.dayOfWeek() in (6, 7):   # 토=6, 일=7 — 클릭 무시
                return
            self._jump_to_date(d.toString('yyyy-MM-dd'))
            popup.close()

        cal.clicked.connect(_on_date_clicked)
        layout.addWidget(cal)
        popup.adjustSize()

        # 화면 밖으로 잘리지 않도록 위치 보정
        pos    = self._cal_btn.mapToGlobal(self._cal_btn.rect().bottomLeft())
        screen = QApplication.desktop().availableGeometry(self)
        pw, ph = popup.sizeHint().width(), popup.sizeHint().height()
        if pos.x() + pw > screen.right():
            pos.setX(screen.right() - pw - 4)
        if pos.y() + ph > screen.bottom():
            pos.setY(pos.y() - ph - self._cal_btn.height())
        popup.move(pos)
        popup.exec_()

    def _jump_to_date(self, date_str: str) -> None:
        if not hasattr(self, '_date_row_map'):
            return
        if date_str in self._date_row_map:
            row = self._date_row_map[date_str]
            self._table.scrollTo(
                self._table.model().index(row, 1),
                QTableWidget.PositionAtTop,
            )
            self._table.selectRow(row)
        else:
            # 해당 날짜 데이터 없음 → 가장 가까운 날짜로 이동
            dates = sorted(self._date_row_map.keys(), reverse=True)
            closest = next((d for d in dates if d <= date_str), dates[-1] if dates else None)
            if closest:
                self._jump_to_date(closest)

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        id_item = self._table.item(row, 0)
        return int(id_item.text()) if id_item else None

    def _on_selection_changed(self) -> None:
        row = self._table.currentRow()
        # 날짜 헤더 행(span 설정된 행)은 선택해도 버튼 비활성
        id_item = self._table.item(row, 0) if row >= 0 else None
        has = bool(id_item and id_item.text())
        for btn in (self._btn_pending, self._btn_inprogress,
                    self._btn_completed, self._btn_edit, self._btn_delete):
            btn.setEnabled(has)
        if has:
            self._status_label.setText('선택된 예약에 작업을 실행합니다.')
            self._status_label.setStyleSheet('color:#374151;')
        else:
            self._status_label.setText('행을 선택하면 작업을 실행할 수 있습니다.')
            self._status_label.setStyleSheet('color:#9ca3af;')

    # ── CRUD 동작 ─────────────────────────────────────────────────────

    def _add(self) -> None:
        dlg = _ReservationDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.get_data()
        if not data.get('name') or not data.get('phone'):
            QMessageBox.warning(self, '입력 오류', '이름과 전화번호를 입력하세요.')
            return
        try:
            r = requests.post(f'{API_BASE}/reservations/', json=data, timeout=3)
            if r.status_code == 201:
                self._fetch()
            else:
                QMessageBox.warning(self, '추가 실패', r.json().get('detail', '오류 발생'))
        except Exception as e:
            QMessageBox.critical(self, '연결 오류', str(e))

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        row_data = next((d for d in self._all_data if d.get('id') == rid), None)
        if not row_data:
            return
        dlg = _ReservationDialog(self, data=row_data)
        if dlg.exec_() != QDialog.Accepted:
            return
        payload = dlg.get_data()
        try:
            r = requests.put(f'{API_BASE}/reservations/{rid}', json=payload, timeout=3)
            if r.ok:
                self._fetch()
            else:
                QMessageBox.warning(self, '수정 실패', r.json().get('detail', '오류 발생'))
        except Exception as e:
            QMessageBox.critical(self, '연결 오류', str(e))

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        row_data = next((d for d in self._all_data if d.get('id') == rid), None)
        name = row_data.get('name', '') if row_data else ''
        reply = QMessageBox.question(
            self, '삭제 확인',
            f'[{name}] 예약을 삭제하시겠습니까?\nPENDING 상태가 아니면 삭제되지 않습니다.',
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            r = requests.delete(f'{API_BASE}/reservations/{rid}', timeout=3)
            if r.status_code == 204:
                self._fetch()
            else:
                QMessageBox.warning(self, '삭제 실패', r.json().get('detail', '오류 발생'))
        except Exception as e:
            QMessageBox.critical(self, '연결 오류', str(e))

    def _change_status(self, status: str) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        try:
            r = requests.patch(
                f'{API_BASE}/reservations/{rid}',
                json={'status': status},
                timeout=3,
            )
            if r.ok:
                self._fetch()
            else:
                QMessageBox.warning(self, '상태 변경 실패', r.json().get('detail', '오류 발생'))
        except Exception as e:
            QMessageBox.critical(self, '연결 오류', str(e))
