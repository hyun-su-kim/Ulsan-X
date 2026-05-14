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

### GuidingPage 폴링 로직

```
로봇 배정 성공
    ↓ 2초 대기 (BUSY 전환 여유)
    ↓ GET /robots/status 폴링 (0.5초 간격)
    ↓
WAITING_START: 로봇이 IDLE → non-IDLE 전환 감지
    ↓
WAITING_IDLE: 로봇이 non-IDLE → IDLE 전환 감지 (홈 복귀)
    ↓
COMPLETED: "안내 완료" 표시 → 4초 후 홈으로
    (10분 타임아웃: 네트워크 이상 대비 자동 홈 복귀)
```

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
    → 미션 있으면:
       /goal_destination 발행 (domain 5 → wego_bridge → domain 6 or 7)
       /speak_text       발행 (domain 5 → wego_bridge → domain 6 or 7)
    → 완료 시:
       PATCH /reservations/{id} → COMPLETED
```

### 임무 할당 규칙

| limo1 | limo2 | 배정 |
|---|---|---|
| IDLE | IDLE | limo1 (기본 우선순위) |
| IDLE | BUSY | limo1 |
| BUSY | IDLE | limo2 |
| BUSY | BUSY | 503 반환 → 태블릿 "잠시 후 다시 시도" |

---

## wego_bridge 변경 사항

기존 브릿징 항목에 아래 3가지 추가:

| 토픽 | 방향 | 용도 |
|---|---|---|
| `robot_status` | domain 6→5, 7→5 | wego_dispatcher가 로봇 상태 수신 |
| `goal_destination` | domain 5→6, 5→7 | wego_dispatcher가 목적지 전달 |
| `speak_text` | domain 5→6, 5→7 | wego_dispatcher가 TTS 트리거 |

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
| POST | `/walkin/assign` | 현장 방문 배정 + walk-in DB 삽입 + 로봇 배정 |
| POST | `/assign` | 예약 체크인 후 로봇 임무 배정 |
| POST | `/assign/classroom` | 강의실 안내 로봇 배정 (DB 기록 없음) |
| GET | `/assign/pending` | wego_dispatcher 폴링용 미결 미션 조회 |
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
