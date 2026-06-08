# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**Phase 3 — 1차 데모 준비 (2026-05-29)**
핵심 기능 구현 완료. 실기기 검증 진행 중. 잔여: FSM 통합 테스트 + LIMO 2 검증 + 사람 감지 정지 기능.

---

## 1차 데모 완성 체크리스트 (2026-05-28 기준)

| # | 작업 | 상태 | 비고 |
|---|------|------|------|
| 1 | **TTS(wego_voice) 재작업** | `done (2026-05-18)` | mpg123 오디오 장치 미지정 문제. `-a plughw:1,3` (HDMI 0) 고정, `audio_device` 파라미터화 |
| 2 | **마커 기반 홈 정밀 복귀 구현** | `done (2026-05-26)` | 단계분리(staged) 도킹 제어기 실기기 검증 완료 — lateral ~1cm 정밀 정차. DEC-038 참고 |
| 3 | **Nav2 BT 커스텀** | `done (2026-06-01)` | XML 2개 커스텀(DEC-039) + PersonClearCondition C++ 노드 + ReactiveSequence 래핑 완료(DEC-041) |
| 4 | **유리문 구간 중앙 웨이포인트 경유** | `done (2026-05-19)` | NavigateThroughPoses + glass_entry/glass_exit 경유 포인트 2개. DEC-030 참고 |
| 5 | **관제 UI (wego_ui, PyQt + rclpy)** | `done (2026-05-22)` | 지도·로봇 상태·카드·긴급 제어·이벤트 로그·미션 로그·확장성 리팩토링 완료. DEC-034~036 참고 |
| 6 | **사람 발견 시 정지 기능** | `in-progress (2026-06-01)` | 구현 완료(ulsan_person_detect + ulsan_bt_plugins + BT XML). 실기기 검증 남음. DEC-041 참고 |

---

## 1차 데모 완성을 위한 실기기 검증 계획 (2026-05-28)

### 1단계 — LIMO 1 단독 주행

| # | 항목 | 상태 |
|---|------|------|
| 1-1 | 유리 구간 경유지 통과 주행 | `done (2026-05-29)` |
| 1-2 | FSM 각 상태 동작 (IDLE/GUIDING/RETURNING/WAITING/FAILED) | `todo` |
| 1-3 | BT 수정 사항 동작 (BackUp+ClearCostmap 복구, RemovePassedGoals) | `todo` |
| 1-4 | PBVS 홈 도킹 | `done (2026-05-26)` |

### 2단계 — LIMO 2 단독 주행

| # | 항목 | 상태 |
|---|------|------|
| 2-1 | 유리 구간 경유지 통과 주행 | `todo` |
| 2-2 | FSM 각 상태 동작 | `todo` |
| 2-3 | BT 수정 사항 동작 | `todo` |
| 2-4 | PBVS 홈 도킹 (markers.yaml ID 1 측정 완료 2026-05-28) | `todo` |

### 3단계 — 2대 통합

| # | 항목 | 상태 |
|---|------|------|
| 3-1 | 협동 임무 할당 (dispatcher → 두 로봇 순차 배정) | `todo` |
| 3-2 | 충돌 회피 (wego_traffic pause/resume) | `todo` |

### 4단계 — 관제 UI 전체 테스트

| # | 항목 | 상태 |
|---|------|------|
| 4-1 | 지도 + 두 로봇 실시간 위치 | `todo` |
| 4-2 | 긴급 제어 (pause/resume/abort) | `todo` |
| 4-3 | 이벤트·미션 로그 | `todo` |
| 4-4 | 시스템 상태 모니터링 | `todo` |

### 5단계 — 사람 감지 정지

| # | 항목 | 상태 |
|---|------|------|
| 5-1 | YOLOv8n(COCO 사전학습) + Depth 거리 게이팅(0.7m) 노드 — `ulsan_person_detect` | `done (2026-06-01)` |
| 5-2 | PersonClearCondition C++ BT 노드 — `ulsan_bt_plugins` | `done (2026-06-01)` |
| 5-3 | BT XML 수정 (ReactiveSequence 삽입, navigate_to_pose + navigate_through_poses) | `done (2026-06-01)` |
| 5-4 | 실기기 검증 (사람 0.7m 진입 → 정지 → 이탈 → 재개) | `todo` |

> **5단계(실기기 검증 포함) 완료 = 1차 데모 완성**
> 구현 3종 완료(2026-06-01). person_detect_node는 노드 1개라 launch 없이 `ros2 run`으로 실행(DEC-043). 실행 위치: **로봇(LIMO 도메인 6/7) — perception 엣지 배치(DEC-043)**. wego_aruco도 로봇에서 실행.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 시스템 아키텍처 설계 | **완료** | — (DEC-021~027) |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **완료** | wego_bridge |
| SLAM 지도 작성 | **완료** | wego |
| Nav2 경로 계획 & AMCL | **완료** | wego_2d_nav |
| Fleet 충돌 회피 (우선순위 기반 pause/resume) | **완료** | wego_traffic + wego_behaviour |
| waypoints.yaml 목적지 좌표 작성 | **완료** | wego_behaviour/config |
| 행동 트리 최상단 관리 (FSM — WAITING 상태 포함) | **완료** | wego_behaviour |
| ArUco 마커 홈 정차 보정 | **완료** | wego_aruco |
| 음성 파이프라인 (TTS only, DEC-024) | **완료** | wego_voice |
| 예약 백엔드 (FastAPI + MySQL + APScheduler) | **완료** | ulsan_reservation |
| 웹 예약 UI (React) | **완료** | ulsan-web-ui |
| 태블릿 방문자 UI (React, HTTP only) | **완료** | ulsan-visitor-ui (DEC-027) |
| 로봇 임무 중계 (wego_dispatcher) | **완료** | wego_dispatcher (DEC-027) |
| 관제 UI (관리자 대시보드) | planned | wego_ui (재구현) |

---

## Execution Checklist

### 완료 — 환경 기반 구축
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
  - ※ **이후 폐기 (2026-05-25)**: `/map` 로컬 발행 전환으로 unicast 불필요 → cyclone_peers.xml 삭제, **도메인 분리(5/6/7) + 기본 멀티캐스트 auto-discovery**로 단순화. 상세 COMMUNICATION.md
- [x] DOMAIN_ID 확정 — done (2026-04-16): 노트북=5, LIMO 1=6, LIMO 2=7
- [x] cyclonedds_peers.xml 실제 IP 입력 — done (2026-04-22): LIMO1=192.168.0.101, LIMO2=192.168.0.102, 노트북1=192.168.0.115, 노트북2=192.168.0.116
- [x] 멀티로봇 통신 설계 확정 — done (2026-04-21): DEC-011, DEC-012
- [x] `wego_bridge` 패키지 구현 + 실기기 통신 검증 — done (2026-04-22)
- [x] Cartographer SLAM 지도 작성 완료 — done (2026-04-28~29)
  - 유리 구간: 종이 부착으로 LiDAR 특징점 확보 (매핑 후 제거)
  - 복도 drift: 임시 장애물 배치 + 루프 주행(왕복) + `/constraint_list` loop closure 확인
  - 후처리: GIMP 노이즈 제거 + 유리문 구간 가상 벽 처리
- [x] 맵 파일 git 커밋 — 각 기기 `git pull`로 배포

---

### Phase 1 — 단일 LIMO 자율주행 완성 (재진행 중)

> LIMO 1대가 학원을 완벽하게 자율주행하는 것이 목표

- [x] `ulsan_obstacle_layer` 빌드 완료 — **폐기 결정 (DEC-022)**: global costmap 기반 동적 충돌 회피 한계 확인. 우선순위 기반 FSM pause/resume 방식으로 대체.
- [x] Nav2 전체 스택 실기기 테스트 — 목적지·홈 구간 정상 주행 확인 (2026-04-29)
- [x] AMCL 파라미터 튜닝 — `do_beamskip: true` 단일 수정. 파티클 수렴 정상 확인 (2026-04-29)
- [x] **유리 구간 유령 장애물** — Keepout Filter + DenoiseLayer 적용 완료 (2026-04-29)
  - 목적지·홈 구간 주행에 문제 없음 → 운용상 수용
  - 유리 회전문 통과는 LiDAR 물리 한계로 소프트웨어 완전 해결 불가 → **운용 정책: 유리 회전문 구간은 경로에서 제외**
- [x] **재매핑 완료** — 홈 위치 원점(0,0,0) 기준 새 맵으로 교체 (2026-05-07)
  - AMCL 위치추정: Cartographer 맵 기반 AMCL 유지 (SLAM Toolbox 비교 실험 계획 → 실용성 우선으로 건너뜀)
  - 새 map origin: [-7.1, -12.2, 0]
  - `filter_map.yaml` 재생성 (새 origin 반영)
- [x] **waypoints.yaml 재측정 완료** — 새 맵 기준 실기기 recorder로 재기록 (2026-05-07)
  - home_robot1: x=0.0, y=0.98, yaw=-1.5708 (2026-05-08 재측정: 마커 시야 확보 위해 98cm 이동)
  - classroom_1~5, counseling_1~2, counter, intensive_counseling_1~2, multi, vice_principal 전부 재측정
- [x] `waypoints.yaml` 완료 — 새 맵 기준 좌표 확정 (2026-05-07)

---

### Phase 2 — 2대 Fleet 구성

> LIMO 2대가 서로를 인식하고 회피하며 독립적으로 주행

- [x] `ulsan_obstacle_layer` 실기기 검증 완료 (2026-04-29) — **폐기 (DEC-022)**: 동적 충돌 회피 구조적 한계 확인
- [x] `wego_bridge` 실운용 — 두 로봇 amcl_pose 노트북(domain 5) 수신 확인 (2026-04-29)
- [x] `wego_ui` 관제 GUI — 노트북 domain 5에서 지도 + 두 로봇 실시간 위치 마커 정상 시각화 (2026-04-29)

---

### Phase 3 — 핵심 기능 구현

#### 사전 작업
- [x] `waypoints.yaml` 좌표 입력 — 완료 (2026-04-30)

#### 미션 제어
- [x] `wego_behaviour` 패키지 뼈대: **Yasmin FSM** (IDLE / GUIDING / RETURNING) + `navigate_to_pose` 연동 — done (2026-04-30)
- [x] `goal_test_node` 추가 — wego_voice 완성 전 FSM 검증용 임시 노드 (2026-04-30)
- [x] **behaviour FSM 실기기 웨이포인트 주행 검증** — done (2026-05-08)
  - classroom_1 → home1 왕복 주행 성공 (IDLE→GUIDING→RETURNING→IDLE)
  - goal_test_node로 목적지 수동 발행 → FSM 전환 정상 확인
- [x] **abort(임무 중단) 기능 구현** — done (2026-05-21). DEC-032 참고
  - `/abort` 토픽 구독 → GUIDING: cancelTask()+'aborted'→RETURNING, WAITING: return_to 변경(GUIDING→RETURNING)
  - wego_bridge `/ROBOT_NAME/abort` 브릿지 추가 (domain 5→LIMO)
  - ulsan_gui `publish_abort()` 추가, 🛑 임무중단 버튼 연동
- [x] **메시지 패키지 정리 — limo_msgs 유지** — 정정 (2026-06-01)
  - ※ 2026-05-21 `wego_msgs`로 마이그레이션 시도했으나 이후 **되돌림**: `wego_msgs`는 삭제되었고 현재 코드는 `limo_msgs/msg/LimoStatus.msg`를 사용 (`from limo_msgs.msg import LimoStatus`)
  - `Chalkak.srv`는 현재 미존재. 메시지 정본 = `limo_msgs`
- [x] **BT navigator XML 경로 오류 수정** — done (2026-05-21)
  - `navigation_only_launch.py` 파라미터 오버라이드로 커스텀 XML 경로 명시
- [x] **WaypointCRUD 서비스 제거** — done (2026-05-21)
  - 예약 DB 기반 아키텍처로 waypoint 동적 수정 불필요 확정, CMakeLists + behaviour_node 정리
- [x] **GUIDING 실패 처리 — FAILED 상태 추가** — done (2026-05-21). DEC-033 참고
  - GUIDING failed → FAILED(TTS "관리자를 기다려 주세요" + 10초 대기) → RETURNING
  - 관제 UI FAILED 빨간 색상 추가. 실기기 검증 필요.
  - ※ **2026-06-05 전면 재설계 (DEC-044)**: 자동 복귀 폐지 → 아래 항목으로 대체
- [x] **FSM 실패 처리 통합 — 모든 주행/도킹 실패 → FAILED + 관리자 물리 복구** — done (2026-06-05). DEC-044 참고
  - GUIDING/RETURNING 주행 실패 + DOCKING(PBVS) 실패 3종을 모두 FAILED로 통합. `failed_from`별 TTS 발화
  - 자동 재주행 일절 없음(주행 능력 손상으로 자가복구 모순 + FAILED↔RETURNING 무한루프 차단)
  - 관리자가 로봇을 home에 물리 배치 → `/recover` 수신 → behaviour_node가 home 좌표 `/initialpose` 발행(AMCL 리셋) → IDLE
  - `RETURNING failed: IDLE→FAILED` 수정, `call_home_dock()` 반환값 표면화(기존 무시). wego_bridge `/recover` 브릿지 추가
  - **관제 GUI [복구완료] 버튼은 미구현** — FSM 관제 GUI 작업 시 진행(`/limo{N}/recover` Empty 발행). 실기기 검증 남음
- [x] **PoseProgressChecker 교체** — done (2026-05-21), **Spin 방식으로 대체 (2026-05-25)**. DEC-031·DEC-037 참고
  - SimpleProgressChecker → PoseProgressChecker: 선형+각도 변화 모두 진행으로 인정
  - required_movement_angle: 0.5rad(~28°) 추가 — 홈 출발 180° 회전 시 recovery 루프 해결
  - ※ 2026-05-25: 주행 중 stuck 감지 정확도 저하 문제로 Spin 방식 전환, SimpleProgressChecker 복원 (DEC-037)
- [x] **홈 출발 Spin 선실행 + SimpleProgressChecker 복원** — done (2026-05-25). DEC-037 참고
  - `GuidingState`: 홈 출발(`from_home=True`) 시 `navigator.spin(math.pi)` 선실행 → AMCL 파티클 수렴 + 출발 방향 전환
  - `SimpleProgressChecker` 복원 → 주행 중 제자리 회전 stuck 정확히 감지. 실기기 검증 필요.
- [x] **RemovePassedGoals radius 0.5 → 0.2** — done (2026-05-21)
  - 유리 구간 경유 포인트 통과 판정 범위 축소 — 경유지 근처를 실제로 통과해야 판정
- [x] **robot_status 1초 주기 재발행** — done (2026-05-21)
  - 모든 FSM 상태 루프에서 10틱(1초)마다 `publish_status` 재발행
  - 기존: 상태 진입 시 1회만 발행 → GUI 늦게 켜지면 연결 감지 불가
- [x] **관제 GUI 종합 점검 — 이벤트/미션 로그 분리** — done (2026-05-22). DEC-034 참고
  - 이벤트 로그: 관제 GUI 조작(상태 전이/긴급 제어/수동조작 전환) — 지도 뷰 통합 + 로봇 뷰 개별. 메모리 전용
  - 미션 로그: 방문자 UI 임무(배정/완료/실패/노쇼) — FastAPI logs 테이블 영구 저장
  - robot_view `_on_status`의 1초 중복 `_add_event` 호출 제거
  - `sig_gui_log` 필터링 기반 개별 이벤트 로그
  - FastAPI `assign.py` 3곳(reservation/classroom/complete), `walkin.py` 1곳에 `create_log` 추가
- [x] **관제 GUI 정합성 버그 수정** — done (2026-05-22)
  - `_STATUS_LOG_TYPE`의 `'ERROR'` → `'FAILED'` (mission_fail 로그가 정상 발화)
  - `robot_view` STATUS_COLOR/STATUS_BG에 FAILED 색상 누락 추가
  - LOG_TYPE_COLOR를 `ulsan_gui/styles.py` 단일 정본으로 통합 (3개 파일 중복 제거, map_view 팔레트 채택)
- [x] **관제 GUI 확장성 리팩토링** — done (2026-05-22). DEC-035 참고
  - `ros_node.py`에 `ROBOTS` 튜플 단일 정본 + `RobotState` dataclass 도입
  - `GuiSignals` 분리 시그널 8개(`sig_status_1/2` 등) → 통합 시그널 5개(`sig_status(robot, status)` 등)
  - 5개 분산 dict (`latest_status`, `_prev_status`, `latest_pose`, `latest_dest`, `_last_recv`)를 `self.robots: dict[str, RobotState]` 단일 dict로 통합
  - 모든 뷰의 하드코딩 `'limo1'`/`'limo2'` 제거. 탭/카드/시스템 상태/통계 칩 모두 ROBOTS 기반 동적 생성
  - 공통 `HttpGetThread` 클래스(`http_thread.py`) 신규 — 3개 HTTP 스레드 클래스 중복 제거
  - `_FastApiChecker` 단일 인스턴스 재사용 (2초마다 객체 재생성 → 1회 생성)
- [x] **today_tasks 로봇별 카운트 분리** — done (2026-05-22)
  - `crud.count_today_missions_by_robot` + `GET /assign/today/by-robot` 신규
  - 기존: 두 로봇 패널에 동일한 학원 전체 카운트 → 각 로봇별 실제 임무/완료 카운트
- [x] **FAILED 미션 통계 분리** — done (2026-05-22). DEC-036 참고
  - 기존: FAILED → RETURNING → IDLE 시퀀스도 `/complete`로 일괄 처리 → mission_fail 로그 누락
  - `dispatcher_node`에 `_failed` set 추가, FAILED 상태 진입 시 미션 ID 추적
  - IDLE 복귀 시 `_failed`에 있으면 `PATCH /assign/{id}/fail` 호출
  - FastAPI `fail_mission` 엔드포인트 신규 → `mission_fail` 로그 기록
- [x] ~~Nav2 BT 커스텀 노드: `VoiceTriggerCondition`, `PeerRobotBusyCondition`~~ — **폐기** (음성 트리거·on_duty 게이팅은 예약+dispatcher 아키텍처 DEC-027로 대체). 실제 구현된 커스텀 BT 노드는 `PersonClearCondition` (DEC-041)
- [ ] **백엔드 확장성 정리 (데모 후)** — FastAPI/wego_dispatcher의 `ROBOTS` 상수화 + `wego_traffic` N-pair 거리 비교 일반화

#### 음성 파이프라인
- [x] `wego_voice` 패키지: TTS 전용으로 단순화 — done (2026-05-13)
  - wakeword / VAD / STT / NLU 파이프라인 전체 제거 (DEC-024)
  - `/speak_text` 구독 → edge-tts + mpg123으로 출력
  - wego_dispatcher가 발행, wego_bridge가 domain 5→6/7 브릿징

#### 예약 시스템 (DEC-023, DEC-024, DEC-027)
- [x] `ulsan_reservation` FastAPI 서버 구현 — done (2026-05-12)
  - FastAPI + MySQL + SQLAlchemy, 관제 노트북(192.168.0.115:8000) 실행
  - 엔드포인트: 예약 생성/조회/변경/취소/상태변경/만석조회
  - 상담실 자동 배정: counseling_1 → counseling_2 → intensive_1 → intensive_2
  - CORS 미들웨어 적용
- [x] `ulsan_reservation` 신규 엔드포인트 추가 — done (2026-05-13)
  - `GET /walkin/rooms/available` — 현재 시간대 빈 상담실 조회
  - `POST /walkin/assign` — 현장방문 배정 + walk-in DB 삽입
  - `POST /assign` — 예약 체크인 로봇 임무 배정
  - `POST /assign/classroom` — 강의실 안내 배정 (DB 기록 없음)
  - `GET /assign/pending` — wego_dispatcher 폴링용
  - `PATCH /assign/{id}/start`, `PATCH /assign/{id}/complete`
  - `POST /robots/{id}/status`, `GET /robots/status`
  - `GET /logs` — 관제 GUI 알림 로그
  - APScheduler: 매시 10분 노쇼(No-show) 감지 → logs 테이블 삽입
- [x] `ulsan_reservation` 미션 로그 통합 — done (2026-05-22). DEC-034 참고
  - `POST /assign`, `POST /assign/classroom`, `POST /walkin/assign` → `mission_start` 로그
  - `PATCH /assign/{id}/complete` → `mission_complete` 로그
  - `PATCH /assign/{id}/fail` 신규 — FAILED 미션 전용 (DEC-036)
  - `GET /assign/today/by-robot` 신규 — 로봇별 오늘 임무 카운트
- [x] `ulsan-web-ui` React 웹 예약 UI 구현 — done (2026-05-12)
  - 예약 폼: 이름/전화번호/날짜(react-datepicker)/시간 선택
  - 만석 시간대 자동 회색 비활성화 + "(마감)" 표시
  - 내 예약 조회/취소/변경 (이름 + 전화번호 끝 4자리 인증)
  - 예약 완료 확인 페이지 (배정 상담실/시간 표시)
- [x] `ulsan-visitor-ui` 태블릿 방문자 React UI — done (2026-05-13)
  - 예약 조회: 이름 + 전화번호 끝 4자리 → 예약 확인 → [안내 시작]
  - 현장방문: 빈 상담실 자동 표시 → [안내 시작] / 강의실 버튼 선택
  - GuidingPage: GET /robots/status 폴링 → 로봇 귀환 감지 → 완료 화면
  - rosbridge 없음. HTTP only. (DEC-027)

#### 멀티로봇 코디네이터
- [x] `wego_traffic` 패키지: 두 로봇 거리 감지 → pause/resume 발행 (DEC-022) — done (2026-05-13)
- [x] `wego_behaviour` WAITING 상태 추가 및 연동 — done (2026-05-13)
- [x] `wego_bridge` goal_destination + speak_text 브릿지 추가 — done (2026-05-13)
  - `/limo1/goal_destination` (domain 5→6), `/limo1/speak_text` (domain 5→6)
  - `/limo2/goal_destination` (domain 5→7), `/limo2/speak_text` (domain 5→7)
- [x] `wego_dispatcher` 신규 패키지 — done (2026-05-13)
  - domain 5에서 실행. /limo1(2)/robot_status 구독 → FastAPI 상태 동기화
  - GET /assign/pending 0.5초 폴링 → IDLE 로봇에 goal/speak 발행
  - 로봇 귀환 감지(IDLE 복귀) → PATCH /assign/{id}/complete

#### ArUco 보정
- [x] `wego_aruco` 패키지 구현 — done (2026-05-01)
  - OpenCV 4.7+: `estimatePoseSingleMarkers` → `solvePnP` 교체
  - `/initialpose` 발행 주체를 `wego_aruco`로 이전 — 마커 map 좌표 역산
  - `wego_behaviour` ReturningState `publish_initial_pose()` 제거
  - 마커 크기 20cm 확정
  - `markers.yaml` ID 0 재측정 완료 (2026-05-08):
    - target_dist=0.946, map_x=0.0, map_y=-0.196, map_yaw=1.5708, calibrated=true
    - home_robot1 위치 기준 역산: camera_y=0.75, marker_y=0.75-0.946=-0.196
- [x] Nav2 goal tolerance 조정 — done (2026-05-01)
  - `xy_goal_tolerance: 0.10`, `yaw_goal_tolerance: 0.10` (2026-05-04 재조정)
- [x] AMCL 업데이트 빈도 조정 (2026-05-08)
  - `update_min_d: 0.1 → 0.2`, `update_min_a: 0.1 → 0.2`
  - CPU 부하 절감 목적 (Control loop missed rate 경고 대응)
- [x] **2-Phase visual servoing 설계 및 실기기 검증** — done (2026-05-04)
  - Phase 1: 전진 접근 → 30cm + lateral 보정 (lat=0.001m 수렴)
  - Phase 2: 후진 → 1.974m + lateral 보정 (lat=0.008m 수렴)
  - 설계 원칙: 제자리 회전 금지 (lateral-only 보정) — 마커 FOV 유지
- [x] **passive ArUco pose corrector 구현** — done (2026-05-07), DEC-020
  - `wego_aruco/pose_corrector.py` 신규 작성
  - 전략: 웨이포인트 바닥/벽 마커 감지 → 주행 중 /initialpose 자동 발행 (visual servoing 없음)
  - 조건: MIN_CONSISTENT=3회, COOLDOWN=10초
  - 변환 체인: `T_map_base = T_map_marker × inv(T_cam_marker) × inv(T_base_cam)`
  - TF lookup으로 camera tilt 자동 반영
- [x] **passive corrector 물리 마커 설치 + 실기기 검증** — done (2026-05-08)
  - home1 바닥 마커(ID 0) 방향 캘리브레이션 완료 (시계방향 90° 회전으로 map_yaw=π/2 확정)
  - classroom_1 → home1 왕복 주행 중 AMCL 보정 확인 (10초 cooldown 간격 정상 동작)
  - 보정값 수렴: x≈0.15, y≈1.22, yaw≈-1.52 (home1 기준 ~0.25m 오차, Nav2 goal 성공)
- [x] `aruco_localizer.py` 삭제 — visual servoing 폐기 (정밀 주차 불필요, 2026-05-11)
- [x] markers.yaml ID 0 map 좌표 재측정 완료 (2026-05-19)
  - home_robot1 yaw +90° → -90° 수정 후 재캘리브레이션
  - map_x=-0.0463, map_y=-0.4014, map_z=0.0518, qx=0.0161, qy=0.7426, qz=0.6695, qw=0.0009
- [x] AMCL 보정 거리 임계값 추가 (2026-05-19) — max_correction_depth=0.40m
  - 주행 중 원거리 마커 감지 오보정 방지. PBVS 도킹 구간(근거리)에서만 보정
- [x] **aruco_home_dock 3DOF PBVS 재설계** (2026-05-20)
  - 기존 2DOF(depth+lateral) → 3DOF(depth+lateral+yaw) P 제어
  - yaw_error = atan2(R_cm[0][2], -R_cm[2][2]) — 마커 법선 기반 비틀림 추출
  - 수렴 조건: depth_tol=0.03m, lateral_tol=0.01m, yaw_tol=0.05rad
  - 후진 시 angular=0 (FOV 이탈 방지), 마커 미감지 즉시 정지
  - 수렴 완료 즉시 Twist() → sleep(0.1) → _publish_initialpose() (AMCL 리셋)
- [x] **home_robot1_staging 웨이포인트 추가** (2026-05-20) — x=0.0, y=0.5, yaw=-1.5708
  - Nav2는 staging까지만 이동. 나머지 0.5m는 PBVS 정밀 주행
  - states.py ReturningState: staging_key 있으면 staging, 없으면 home 직접 (fallback)
- [x] **pose_corrector passive 보정 비활성화** (2026-05-20)
  - aruco_corrector_launch.py에서 aruco_pose_corrector 노드 제거
  - AMCL 보정을 PBVS 정밀 정차 완료 후 1회로 통합
  - 이유: idle 중 마커 감지 → /initialpose 발행 → Nav2 경로 재계획 → 출발 타임아웃(DEC-031)
  - pose_corrector.py 파일은 캘리브레이션 도구로 보존 (end-to-end 완료 후 삭제 예정)
- [x] markers.yaml ID 1 map 좌표 측정 — done (2026-05-28)
- [x] **마커 0 재캘리브레이션** — done (2026-05-26): 마커 이동 후 재측정 (map_y=-0.662 등, std 0.0002). target_dist 0.271→0.432 동기화
- [x] **PBVS 홈 도킹 제어기 재설계 + 실기기 검증** — done (2026-05-26): staged(단계분리) 채택, lateral ~1cm 정밀 정차. DEC-038 참고
  - 비홀로노믹 과소구동 진단 → ρ/α/θ_g 통합 기하 + 극좌표(A)/단계분리(B) A/B 비교 → staged 채택
  - 목표 근처 α(atan2) 폭발 → steer_freeze(0.15m) 구간 조향 정지로 마지막 급조향 제거
  - 단일 평면 마커 법선 관측성 한계 확인 → 더 높은 정밀도 필요 시 마커 2개 자세 삼각측량 (향후)
- [x] **home_robot1 좌표 재측정 + 관련 파라미터 전체 동기화** — done (2026-05-29). DEC-041 참고
  - home_robot1: x=-0.1111, y=0.0123, yaw=-1.5708 (AMCL 실측)
  - home_robot1_staging: x=-0.1111, y=0.5123, yaw=-1.5708 (home 기준 +0.5m)
  - markers.yaml ID 0 재캘리브레이션: map_x=-0.0949, map_y=-0.7307 등
  - target_dist 0.432 → 0.513 (실측 camera depth 0.513m)
  - aruco_home_dock AMCL 리셋: 마커 역산 → home 좌표 직접 발행 (단일 마커 yaw 관측성 한계로 140° 오차 확인)
- [x] **유리 구간 경유지 좌표 재조정 + RemovePassedGoals 튜닝** — done (2026-05-29). DEC-041 참고
  - glass_entry: x=-0.2, y=2.65 (로봇 복도 경로에 맞게 조정)
  - glass_exit: x=2.2158, y=2.7579 (재측정)
  - RemovePassedGoals radius: 0.2 → 0.7 (경유지 미제거로 로봇 되돌아가는 문제 해결)
  - BackUp dist: 0.30 → 0.10m (유리 구간 맵 경계 이탈 방지)
  - 유리 구간 경유지 통과 실기기 검증 완료
- [x] **PBVS 도킹 A/B 실험 종료 — polar 제어기 제거, staged 단독 채택** — done (2026-06-01). DEC-042 참고
  - `_ctrl_polar`·`dock_mode`·polar 게인(k_rho/k_alpha/k_beta) 코드·런치에서 제거
  - `dock_mode` 인자 누락 시 기각된 polar로 도킹되던 운영 리스크 제거
- [x] **markers.yaml map_pose 트림** — done (2026-06-01). DEC-041 후속
  - `map_x/y/z`·`map_q*`·`calibrated` 제거 (size + home_marker만 유지). 마커 역산 폐기로 운영 미사용 → 죽은 데이터 정리
  - aruco_home_dock은 size/home_marker만 읽음 / pose_corrector calibration_mode는 영향 없음(보존)
- [x] **IBVS → PBVS 용어 정정 + ARUCO-LOCALIZER 문서 갱신** — done (2026-06-01)
  - 구현은 solvePnP 포즈 복원 → SE(2) 작업공간 제어 = PBVS(IBVS 아님). 코드/문서 전반의 IBVS 표기 정정
  - ARUCO-LOCALIZER.md를 옛 설계(2-Phase P제어/마커 역산/aruco_localizer_launch)에서 현재 PBVS staged 기준으로 전면 재작성
- [x] **aruco_measure 신규 + pose_corrector.py 삭제** — done (2026-06-01)
  - `aruco_measure`: 마커 상대 포즈(depth/lateral/yaw) 실시간 콘솔 출력 측정 도구 신규. target_dist 실측·튜닝용(`ros2 run`, 운영 비포함)
  - `pose_corrector.py`: map_pose 트림(DEC-041)으로 비기능 상태였던 캘리브레이션 도구 삭제 + setup.py 진입점 제거. 측정 용도는 aruco_measure가 대체
- [x] **정밀 정차 톨러런스 튜닝 — LIMO1 정밀주차 확인** — done (2026-06-01)
  - aruco_measure로 home1 마커 실측 → `target_dist` 0.513 → 0.505 (이상적 정차 위치 depth)
  - `yaw_tol` 0.10 → 0.02rad(≈1.15°): 차체 ~4° 틀어짐 → phase2 정렬 끝까지 수행. 측정 노이즈 ±0.5° 위 한계값
  - `rho_tol` 0.03 → 0.01m: 위치 1cm 정밀. 실기기 정밀주차 완료 확인
  - waypoints: home_robot1_staging x -0.1111→-0.18·y 0.5123→0.9123, counter y→3.0 (현장 조정)
- [ ] Orbbec 카메라 프로파일 고정 — done (2026-05-07) teleop_launch.py에 depth_height=400 명시

#### 데모용 관제 UI
- [x] `wego_ui` Qt 기반 재구현 — done (2026-05-21)
  - 지도(OccupancyGrid) + 두 로봇 실시간 위치 마커, 줌/패닝
  - 각 로봇 상태 카드 (IDLE/BUSY/RETURNING/WAITING/FAILED 색상)
  - 긴급 제어 카드: 로봇 선택 토글 + 일시정지/재개/임무중단 버튼
  - 이벤트 로그: 상태 전이/버튼 조작 실시간 기록
  - 시스템 상태 패널: 연결·맵서버·FastAPI·dispatcher·traffic 모니터링
- [x] **관제 GUI 코드 정리** — done (2026-05-29)
  - 죽은 코드 제거: `RobotState.last_recv/last_status_recv` (diagnostics 전환으로 미사용), `publish_goal()` (호출처 없음)
  - `LogView`: 불필요한 `ros_node` 의존성 제거, `_fetch` 스레드 중복 실행 방지, `noshow` 필터 추가 (기존 누락)
- [x] **시스템 상태 패널 연결 판단 방식 교체 — ROS2 Diagnostics 표준 채택** — done (2026-05-29). DEC-038 참고
  - 기존: 토픽 존재 여부(`get_topic_names_and_types()`) → GUI 자신이 퍼블리셔를 생성해 항상 연결됨으로 표시되는 버그
  - 수정: `diagnostic_updater` 추가(wego_behaviour/dispatcher/traffic) + `/diagnostics` 수신 시간 기반 판단
  - `bridge_robot.yaml`: `/diagnostics` → `/ROBOT_NAME/diagnostics` 브릿징 추가 (wego_behaviour domain 6/7→5)
- [x] **로봇 연결 판정 단일화 + 미연결 표시 전 화면 통일** — done (2026-06-08). DEC-045 참고
  - `is_robot_connected`(behaviour 생존 AND Nav2 lifecycle 전부 active) 단일 판정 → 시스템 패널·지도 마커·상태 카드·요약 칩·상세 탭이 공유. lifecycle_manager가 맺은 bond 결과를 diagnostics로 받아 판정(도메인 브릿지 너머 생사 반영 — bond 직접 사용 불가 이유는 DEC-045)
  - `sig_connection` 시그널 신규, 변화 시에만 발행. 재연결 시 마지막 pose로 마커 복원. 요약 칩 집계에서 미연결 로봇 제외. 지도 마커 시각 정리(크기·화살표·범례 색-로봇 매핑 키)
  - ※ 코드 머지 완료(미커밋 아님). **실기기 검증 남음**

#### 전체 통합 테스트
- [ ] LIMO 2대 + 노트북 전체 파이프라인 실기기 검증
  - 방문자 UI(예약 조회) → FastAPI → dispatcher 배정 → FSM → navigate → TTS 안내 → ArUco 홈 도킹
  - 협동 임무 배정 (dispatcher: LIMO1 우선, 둘 다 BUSY면 503) + 충돌 회피(wego_traffic pause/resume)

---

### Phase 4 — 완성도
- [ ] 초음파 센서 → local costmap range_sensor_layer 연동 (유리문 닫힘 감지) — 유리문 닫힘 시 경로 생성 불가 → TTS "유리문을 열어주세요" + WAIT 상태
- [ ] YOLO 사람 감지 → 방향 회전 + 안내 멘트
- [ ] 다국어 안내 검토
- [x] **유리 구간 주행 버벅임 개선** — done (2026-05-29). 2026-04-30 미결 항목(Keepout+Denoise 후 잔존 버벅임)을 **경로 설계 개선**으로 해결: NavigateThroughPoses + glass_entry/exit 경유(DEC-030) → 중간 정지 제거, 경유지 재측정 + RemovePassedGoals 매틱 체크 + BackUp 튜닝(DEC-041). LIMO 1 검증 완료(1-1), LIMO 2 검증(2-1) 남음
> ※ 음성 STT/NLU 관련 Phase 4 항목(NLU 백업 Gemma-2B, "추가 용무 확인" 대화, YOLO+faster-whisper GPU 프로파일링)은 **음성 인식 파이프라인 폐기(DEC-024)로 전량 제거**.
- [x] **2대 충돌 회피 — 방식 재설계 완료** — done (2026-05-13, 구현). 2026-04-30에 기록된 "운용 중 간헐적 충돌"은 **폐기된 PeerObstacleLayer(global costmap 주입) 시절 현상**. 그 두 원인(① 네트워크 지연 ② 대칭 회피 교착)을 **DEC-022 우선순위 기반 pause/resume**으로 정조준 해결 — pause/resume은 단순 토픽이라 지연 영향 최소, 우선순위(GUIDING>RETURNING, 동순위 LIMO1)로 한 대가 물리 정지 → 충돌 구조적 불가. wego_traffic 구현 완료. **단, 2대 실기기 검증(3-2)은 미실시** → 최종 확인 필요

---

## Nav2 단독 주행 현황 (2026-04-29 기준)

### 정상 동작
- 복도·강의실 등 일반 구간 자율주행 정상
- AMCL 위치추정 정상 (RViz `/particlecloud` 파티클 수렴 확인)
- **목적지·홈 위치 주행 정상 — 운용 목적 달성**
- Keepout Filter (금지구역) + DenoiseLayer 적용 완료

### 확정된 한계 및 운용 정책

| 항목 | 내용 |
|------|------|
| 유리 회전문 통과 | LiDAR 물리 한계. 소프트웨어 완전 해결 불가. **경로에서 영구 제외** |
| Keepout Filter 적용 범위 | global costmap만 적용. local costmap phantom은 소거 불가. |
| 운용 전제 | 유리문은 항상 열린 상태 유지. 안내 주행 목적에 유리 회전문 통과 불필요. |

### 미해결 과제

| 문제 | 상태 |
|------|------|
| `waypoints.yaml` 미작성 | 완료 (2026-04-30) |
| AMCL 파라미터 미최적화 | 장시간 운영 시 drift 가능성 — 진행 중 |

> 상세 엔지니어링 판단 기록: `docs/ref/NAVIGATION.md` — "Nav2 주행 문제 해결 과정" 섹션

---

## 환경 설정 — 신규 기기 apt 설치 목록

새 기기에 환경 구성 시 설치 필요한 패키지 목록.

### 데스크탑 (server)
```bash
# Nav2 전체 스택
sudo apt install ros-humble-nav2-bringup ros-humble-nav2-common

# wego_behaviour 의존성
sudo apt install ros-humble-yasmin ros-humble-nav2-simple-commander

# 관제 GUI (노트북에서 실행 시)
sudo apt install ros-humble-nav2-map-server ros-humble-nav2-lifecycle-manager ros-humble-nav2-rviz-plugins
```

---

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| **홈 출발 시 Failed to make progress** | High | **해결 (2026-05-21)** — Spin 선실행 + SimpleProgressChecker 복원. DEC-031/037 참고 |
| Orin Nano GPU 메모리 (로봇 로컬 YOLO 추론) | Medium | faster-whisper 폐기(DEC-024)로 OOM 리스크 해소. 드라이버+YOLOv8n 동시 가동 프로파일링은 DEC-043 후속 |
| 두 로봇이 동시에 호출될 때 배정 | — | **해결**: wego_dispatcher LIMO1 우선, 둘 다 BUSY면 503 (DEC-027). on_duty 방식 폐기 |
| 2대 충돌 회피 완성도 | Low | 폐기된 PeerObstacleLayer 시절 간헐 충돌 → DEC-022 pause/resume 재설계로 구조적 해결·구현 완료(2026-05-13). 2대 실기기 검증(3-2)에서 최종 확인 |
> ※ openWakeWord 커스텀 모델 / Gemini API 지연 리스크는 음성 인식 파이프라인 폐기(DEC-024)로 무효.
