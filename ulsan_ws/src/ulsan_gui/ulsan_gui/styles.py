# GUI 시각 상수 — 단일 정본
#
# 이벤트/미션 로그 유형별 (배경색, 글자색).
# 의미: 파랑=진행, 초록=성공, 빨강=실패, 황갈=대기, 회색=일반, 주황=연결 끊김/중단.
LOG_TYPE_COLOR: dict[str, tuple[str, str]] = {
    'mission_start':    ('#dbeafe', '#1d4ed8'),
    'mission_complete': ('#d1fae5', '#047857'),
    'mission_fail':     ('#fee2e2', '#b91c1c'),
    'waiting':          ('#fef3c7', '#b45309'),
    'system':           ('#f3f4f6', '#374151'),
    'alert':            ('#ffedd5', '#9a3412'),   # 연결 끊김/서브시스템 중단 등 경고
}

# 로봇 FSM 상태별 색 — 단일 정본 (map_view·robot_view 공유).
# reservation_view의 STATUS_COLOR는 예약 상태라 별개.
STATUS_COLOR: dict[str, str] = {
    'IDLE':      '#16a34a', 'BUSY':      '#d97706',
    'RETURNING': '#2563eb', 'WAITING':   '#9333ea',
    'FAILED':    '#dc2626', 'UNKNOWN':   '#9ca3af',
}
STATUS_BG: dict[str, str] = {
    'IDLE':      '#f0fdf4', 'BUSY':      '#fffbeb',
    'RETURNING': '#eff6ff', 'WAITING':   '#faf5ff',
    'FAILED':    '#fef2f2', 'UNKNOWN':   '#f8fafc',
}
STATUS_BORDER: dict[str, str] = {
    'IDLE':      '#10b981', 'BUSY':      '#f59e0b',
    'RETURNING': '#3b82f6', 'WAITING':   '#9333ea',
    'FAILED':    '#ef4444', 'UNKNOWN':   '#9ca3af',
}

_DISCONNECTED_BADGE = ('미연결', '#9ca3af', '#f1f5f9')


def status_badge(connected: bool, status: str) -> tuple[str, str, str]:
    """상태 배지의 (텍스트, 글자색, 배경색).

    미연결이면 FSM 상태와 무관하게 '미연결'을 우선(전 화면 통일). 카드·상세패널·탭이 공유.
    """
    if not connected:
        return _DISCONNECTED_BADGE
    return (status,
            STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN']),
            STATUS_BG.get(status, STATUS_BG['UNKNOWN']))
