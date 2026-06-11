# UI 아키텍처

> 구 `ui-architecture.md` (2026-05-12) 대비 변경 사항: 터치 UI → 태블릿 방문자 UI 전환, wego_dispatcher 신설, rosbridge 제거

---

## UI 구성 (3개)

| UI | 기술 스택 | 실행 위치 | 역할 |
|---|---|---|---|
| 방문자 UI | React (HTTP only) | 태블릿 브라우저 | 예약 체크인 / 현장 방문 / 강의실 안내 |
| 관제 GUI | PyQt + rclpy | 관제 노트북 (domain 5) | 로봇 상태 모니터링, 노쇼 알림, 수동 예약 조작 |
| 웹 예약 UI | React | 관제 노트북 (외부 접근) | 학부모/학생 상담 예약/취소/변경 |

---

## 방문자 UI (ulsan-visitor-ui)

### 개요
- LIMO 탑재 디스플레이 방식 폐기. 태블릿에서 브라우저로 접속하는 웹앱으로 변경
- **rosbridge 없음**: 태블릿은 FastAPI에 HTTP 요청만 보낸다. ROS 연동은 wego_dispatcher가 담당
- 실행: 관제 노트북에서 `npm start` → 태블릿 Chrome에서 `http://192.168.0.115:3000` 접속

### 폐기 배경 (구 wego_touch_ui)
- LIMO가 낮아 방문자가 숙여서 입력해야 하는 UX 문제
- rosbridge를 통해 태블릿 JS가 직접 ROS 토픽을 발행하는 구조 → 핵심 로봇 제어 로직이 브라우저에 있는 잘못된 설계
- 태블릿 → FastAPI → wego_dispatcher(rclpy) 구조로 교체: 로봇 제어 로직을 ROS 노드 안으로 복귀

### 화면 흐름

```
홈
├── [예약 조회]
│   └── 이름 + 전화번호 끝 4자리 입력
│       └── 예약 확인 결과 (시간, 상담실)
│           └── [안내 시작] → 안내 중 화면 → 홈
│
└── [현장 방문]
    ├── [상담 예약 없이 방문]
    │   └── 빈 상담실 자동 표시
    │       └── [안내 시작] → 안내 중 화면 → 홈
    │
    └── [강의실 안내]
        └── 1~5강의실 버튼 선택
            └── [버튼 클릭] → 안내 중 화면 → 홈
```

### 페이지 구성

| 파일 | 경로 | 역할 |
|---|---|---|
| `HomePage.js` | `/` | 예약 조회 / 현장 방문 선택 |
| `CheckinPage.js` | `/checkin` | 이름 + 전화번호 입력 |
| `CheckinResultPage.js` | `/checkin/result` | 예약 확인 + 안내 시작 |
| `WalkinPage.js` | `/walkin` | 상담없이 방문 / 강의실 안내 선택 |
| `WalkinRoomPage.js` | `/walkin/room` | 빈 상담실 표시 + 안내 시작 |
| `ClassroomPage.js` | `/walkin/classroom` | 1~5강의실 버튼 |
| `GuidingPage.js` | `/guiding` | 안내 중 스피너 + 귀환 감지 |

### GuidingPage 폴링 로직 (DEC-049, 2026-06-11)

```
임무 생성 성공 (mission_id 수신 — 로봇은 아직 미정)
    ↓ GET /assign/{mission_id} 폴링 (0.5초 간격)
    ↓
PENDING:   "로봇 배정 중" 표시 (dispatcher가 선택 전)
    ↓
ACTIVE:    "안내 중" + robot_assigned 로봇명 표시
    ↓
COMPLETED: "안내 완료" 표시 → 4초 후 홈으로
    (10분 타임아웃: 네트워크 이상 대비 자동 홈 복귀)
```

> 구 방식(`GET /robots/status`로 로봇 상태 전환 추적 + 오감지 방지 2초 대기)은
> 폐기 — 임무 상태가 단일 정본이라 로봇이 어느 쪽으로 배정되든 정확하다.

---

## 관제 GUI (ulsan_gui)

### 구조
| 모듈 | 역할 |
|---|---|
| `ros_node.py` | ROS 노드 + `ROBOTS` 단일 정본 + `RobotState` dataclass + 통합 시그널 |
| `main_window.py` | 사이드바·헤더·뷰 전환 |
| `http_thread.py` | 공통 `HttpGetThread` 백그라운드 HTTP 클래스 |
| `styles.py` | `LOG_TYPE_COLOR` 단일 정본 |
| `views/login_view.py` | PIN 인증 |
| `views/map_view.py` | 지도 + 로봇 카드 + 긴급 제어 + 시스템 상태 + 통합 이벤트 로그 |
| `views/robot_view.py` | 로봇별 탭(카메라/수동조작/개별 이벤트 로그) |
| `views/reservation_view.py` | 예약 CRUD |
| `views/log_view.py` | 미션 로그 (DB 영구) |

### 확장성 (DEC-035)
`ros_node.ROBOTS: tuple[str, ...] = ('limo1', 'limo2')` 한 줄이 GUI 전체의 정본. 로봇 추가 시 이 튜플만 수정하면 탭/카드/시스템 상태/통계 칩/시그널 구독·발행 모두 자동 확장된다.

### 로그 아키텍처 (DEC-034)
| 위치 | 종류 | 데이터 소스 | 저장 정책 |
|---|---|---|---|
| 지도 뷰 미니 이벤트 로그 | 두 로봇 통합 이벤트 | `sig_gui_log` (메모리) | GUI 세션만 |
| 로봇 뷰 개별 이벤트 로그 | 해당 로봇 이벤트 | `sig_gui_log` 필터링 (메모리) | GUI 세션만 |
| 로그 뷰 미션 로그 | DB 영구 기록 | FastAPI `/logs` 폴링 | 영구 |

이벤트 로그 = 관제 GUI 조작(상태 전이/긴급 제어/수동조작 전환), 미션 로그 = 방문자 UI 임무(배정/완료/실패/노쇼). FAILED 미션은 `mission_fail` 타입으로 분리 기록 (DEC-036).

---

## wego_dispatcher (신규 rclpy 노드)

### 역할
태블릿과 ROS 사이의 브릿지. 임무 할당 로직을 ROS 생태계 안에 둔다.

### 실행 위치
서버 노트북 — domain 5 (관제 노트북과 동일 domain)

### 동작

```
구독:
  /limo1/robot_status (domain 6 → wego_bridge → domain 5)
  /limo2/robot_status (domain 7 → wego_bridge → domain 5)
    → 상태 변경 시 POST /robots/{id}/status → FastAPI 상태 캐시 업데이트

폴링:
  GET /assign/pending (0.5초 간격)
    → PENDING 미션 있으면:
       _pick_idle_robot()로 로봇 선택 (할당의 단일 주체, DEC-049)
       /goal_destination 에 GuideGoal{destination, tts_text} 발행
         (domain 5 → wego_bridge → domain 6 or 7, DEC-048)
       PATCH /assign/{id}/start?robot=limoN → FastAPI가 robot_assigned 기록
    → 로봇 IDLE 복귀 감지 시:
       PATCH /assign/{id}/complete (FAILED 경유 시 /fail)
```

### 임무 할당 규칙 (DEC-049: 선택은 dispatcher 단독)

| limo1 | limo2 | 배정 |
|---|---|---|
| IDLE | IDLE | limo1 (기본 우선순위) |
| IDLE | BUSY | limo1 |
| BUSY | IDLE | limo2 |
| BUSY | BUSY | 미션 대기 (다음 폴링에서 재시도) |

> **만차 503은 임무 생성 시점에 FastAPI가 즉답**한다(태블릿 "잠시 후 다시 시도"
> 동기 응답 필요). 단 이는 가용 여부 확인일 뿐, 어느 로봇이 맡을지는
> dispatcher가 디스패치 시점에 결정한다.

---

## wego_bridge 변경 사항

기존 브릿징 항목에 아래 3가지 추가:

| 토픽 | 방향 | 용도 |
|---|---|---|
| `robot_status` | domain 6→5, 7→5 | wego_dispatcher가 로봇 상태 수신 |
| `goal_destination` (`GuideGoal`) | domain 5→6, 5→7 | wego_dispatcher가 목적지+출발멘트 전달 (DEC-048) |
| ~~`speak_text` 5→6/7~~ | — | **폐지**(DEC-048): 출발멘트는 GuideGoal로 behaviour 경유, 도착·실패는 behaviour가 동일 도메인에서 발화 |

---

## FastAPI 엔드포인트 전체 목록

### 기존 (웹 예약 UI용)

| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/reservations/` | 예약 생성 |
| GET | `/reservations/slots` | 날짜별 만석 시간대 |
| GET | `/reservations/today` | 오늘 예약 전체 (관제 GUI) |
| GET | `/reservations/my` | 본인 예약 조회 |
| GET | `/reservations/check` | 체크인 조회 (방문자 UI) |
| PUT | `/reservations/{id}` | 예약 변경 |
| DELETE | `/reservations/{id}` | 예약 취소 |
| PATCH | `/reservations/{id}` | 상태 변경 |

### 신규 (방문자 UI + wego_dispatcher용)

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/walkin/rooms/available` | 현재 시간대 빈 상담실 조회 |
| POST | `/walkin/assign` | 현장 방문 배정 + walk-in DB 삽입 + 로봇 배정 (mission_start 로그) |
| POST | `/assign` | 예약 체크인 후 로봇 임무 배정 (mission_start 로그) |
| POST | `/assign/classroom` | 강의실 안내 로봇 배정 (mission_start 로그) |
| GET | `/assign/pending` | wego_dispatcher 폴링용 미결 미션 조회 |
| GET | `/assign/{id}` | 태블릿 GuidingPage 폴링 — 상태+배정 로봇 (DEC-049) |
| PATCH | `/assign/{id}/start` | wego_dispatcher PENDING → ACTIVE + robot_assigned 기록 (DEC-049) |
| PATCH | `/assign/{id}/complete` | wego_dispatcher 정상 복귀 (mission_complete 로그) |
| PATCH | `/assign/{id}/fail` | wego_dispatcher FAILED 거친 복귀 (mission_fail 로그, DEC-036) |
| GET | `/assign/today/by-robot` | 로봇별 오늘 임무/완료 카운트 (관제 GUI 로봇 뷰) |
| POST | `/robots/{id}/status` | wego_dispatcher → 로봇 상태 업데이트 |
| GET | `/robots/status` | 두 로봇 현재 상태 조회 (태블릿 폴링용) |
| GET | `/logs` | 관제 UI 알림 로그 목록 |

---

## 현장 방문 처리 규칙

### 빈 상담실 판단 기준
오늘 + 현재 시간대(hour)에 예약 행이 **존재하지 않는** 상담실.
상태값(PENDING/IN_PROGRESS) 무관 — 예약 행 자체가 없어야 빈 상담실.

### 배정 순서
`counseling_1` → `counseling_2` → `intensive_counseling_1` → `intensive_counseling_2`

### DB 기록 방식
현장 방문 상담 배정 시 `reservations` 테이블에 walk-in 행 삽입:
```
name      = "현장방문"
phone     = ""
date      = 오늘
time_slot = 현재 시간(hour)
room      = 배정된 상담실
status    = IN_PROGRESS
```
이 행이 삽입되어야 동일 시간대 두 번째 현장 방문자가 같은 상담실로 중복 배정되지 않는다.

### 강의실 안내
DB 기록 없음. 바로 로봇 임무 배정만 한다.

---

## 노쇼(No-show) 알림

APScheduler (FastAPI 내장) — 매시 10분 1회 실행:
```
오늘 PENDING 예약 중 time_slot == 현재 시각(hour) → 알림 로그 생성
  logs 테이블에 추가: "{name}({phone}) 14시 예약 미방문"
예약 상태는 PENDING 그대로 유지 (매니저가 연락 후 직접 처리)
```

---

## 실행 명령

```bash
# 관제 노트북 — FastAPI
cd /home/yechan/Ulsan-X/ulsan_ui/ulsan_reservation
uvicorn main:app --host 0.0.0.0 --port 8000

# 관제 노트북 — 방문자 UI (개발/데모)
cd /home/yechan/Ulsan-X/ulsan_ui/ulsan-visitor-ui
npm start   # http://192.168.0.115:3000

# 관제 노트북 — 방문자 UI (운용)
npm run build && npx serve -s build -l 3000

# 서버 노트북 (domain 5) — wego_dispatcher
export ROS_DOMAIN_ID=5
ros2 run wego_dispatcher dispatcher_node

# 태블릿 — Chrome 키오스크 모드
google-chrome --kiosk http://192.168.0.115:3000
```

---

## 웹 예약 UI (ulsan-web-ui)

변경 없음. `http://192.168.0.115:3000` 과 다른 포트(예: 3001)로 분리 필요.

---

## 기술 선택 근거 요약

| 결정 | 이유 |
|---|---|
| 태블릿 웹앱으로 전환 | LIMO가 낮아 방문자 UX 불량. 태블릿은 눈높이에서 사용 가능 |
| rosbridge 제거 | 로봇 제어 로직이 브라우저 JS에 있는 것은 잘못된 설계. ROS 노드(wego_dispatcher)로 이전 |
| HTTP only 태블릿 | 태블릿은 UI만 담당. 복잡한 ROS 의존성 제거 → 배포 단순화 |
| wego_dispatcher 신설 | 임무 할당 로직을 ROS 생태계 안에 둠. "어느 로봇에 배정할지" 판단이 ROS 노드에 있어야 함 |
| walk-in DB 삽입 | 현장 방문 배정도 reservations 테이블에 기록해야 중복 배정 방지 가능 |
