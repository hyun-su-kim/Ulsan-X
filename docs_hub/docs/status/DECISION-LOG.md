# Decision Log

## Pending

---

### DEC-030: 유리 구간 keepout 경계 hugging 해결 — NavigateThroughPoses + 경유 포인트 2개
- **Context**: Keepout Filter 적용 후에도 global planner가 keepout 경계 바깥의 cost가 0에 가까워 경계에 최대한 붙는 최단 경로를 생성. 경계 근처 주행 중 일부 진입하는 문제 발생.
- **Decision**: **NavigateThroughPoses + glass_entry / glass_exit 경유 포인트 삽입**
  - 통유리 사이 수직선의 양 끝에 경유 포인트 2개 측정·등록
  - 유리 구간 통과 목적지(상담실·카운터·멀티룸·회의실): `goThroughPoses([glass_entry, glass_exit, 목적지])`
  - classroom_1~5: 유리 구간 미통과 → 기존 `goToPose` 유지
  - 복귀 시 순서 반전: `goThroughPoses([glass_exit, glass_entry, home])`
  - 경유 포인트 yaw: 0.0 — 경유지는 goal checker 미적용, 위치만으로 방향 제약
- **NavigateThroughPoses 선택 이유**:
  - WaypointFollower: 내부적으로 NavigateToPose 반복 → 경유지마다 완전 정지. 유리 구간 한가운데 정지 발생
  - NavigateThroughPoses: 모든 경유지를 포함한 단일 전역 경로 생성 → 정지 없이 부드럽게 통과
  - 다른 BT XML(`navigate_through_poses_w_replanning_and_recovery.xml`) 로드
- **구현 위치**: `wego_behaviour/states.py` — `_needs_glass_via()`, GuidingState, ReturningState
- **Rationale**: "keepout 경계 hugging은 global planner의 cost 최소화 특성에서 비롯된 구조적 문제. 알려진 위험 구간에 강제 경유 포인트를 삽입해 경로를 명시적으로 제약하는 방식은 현업 AMR 표준 패턴."
- **면접 어필**: "keepout 경계에 붙어 주행하는 문제를 플래너 cost 구조로 진단하고, NavigateThroughPoses로 유리 구간 중앙 통과를 강제하는 경로 제약을 설계했습니다. WaypointFollower 대비 단일 전역 경로 생성으로 정지 없는 자연스러운 통과를 보장합니다."
- **미완료**: glass_entry / glass_exit 실측 좌표 입력 필요
- **Date**: 2026-05-19

---

### DEC-029: 홈 복귀 정밀 제어 방식 — 벽 마커 + IBVS (staging pose 방식)
- **Context**: 복도 구간 AMCL y drift로 인해 Nav2가 실제 홈 미도달 위치에서 false goal 판정하는 문제 확인. 로봇이 복도에서 홈 방향으로 주행 시 특징점 없는 복도만을 보고 y좌표를 홈에 도달했다고 추정. x,y가 tolerance(±10cm Euclidean) 안에 들어오면 Nav2가 goal 판정 후 yaw 회전 → 그제야 AMCL이 보정되지만 이미 틀린 위치에서 멈춘 상태.
- **Decision**: **벽 마커 + IBVS (Image-Based Visual Servoing) — staging pose 전환 방식**
  1. Nav2가 홈 전방 staging pose까지 주행 (xy_goal_tolerance 넓게 설정, AMCL 오차 흡수)
  2. Nav2 goal 완료(정지 상태) → 마커 기반 P제어로 전환
  3. 선속도 + 각속도 동시 발행: `angular = Kp_w × pixel_error_x`, `linear = Kp_v × (depth - target)`
  4. 로봇이 호(arc) 경로로 마커 정면에 수렴하며 접근 → 홈 정밀 정차
- **마커 위치**: 바닥 아님, **벽 부착** — 전방 카메라로 멀리서부터 감지 가능, FOV 유지
- **IBVS 선택 이유**:
  - 단순 이미지 P제어: x오프셋이 있으면 대각선 접근 문제
  - 제자리 회전 후 전진: 회전 중 마커 FOV 이탈 문제
  - 선속도+각속도 동시 제어: arc 경로로 마커가 항상 FOV 내 유지 + x오프셋 자동 수렴
- **staging 방식 선택 이유**: 마커 감지 즉시 전환(방법 1) vs staging pose 후 전환(방법 2)
  - 방법 1: Nav2 cancel 타이밍 불안정, 로봇 주행 중 P제어 초기 조건 불안정
  - 방법 2: Nav2 goal 완료 후 정지 상태에서 전환 → 안정적. opennav_docking 표준 패턴과 동일
- **구현 위치**: `wego_behaviour` ReturningState + 신규 `aruco_home_dock.py` 노드
- **구현 현황 (2026-05-19)**:
  - `wego_aruco/aruco_home_dock.py` 신규 작성 — `/aruco_home_dock` (std_srvs/Trigger) 서비스
  - `wego_behaviour` ReturningState: Nav2 staging 도착 후 `call_home_dock()` 호출
  - `aruco_corrector_launch.py`: aruco_home_dock 노드 추가
  - 미완료: target_dist 실측 (로봇을 home에 두고 `/aruco_debug` depth 값 확인), markers.yaml 재측정
- **Rationale**: "AMCL 기반 goal 판정의 구조적 한계를 실기기에서 확인. 마지막 구간만 절대 기준(마커 비전)으로 제어 전환하는 Coarse-to-Fine 패턴 적용. AMCL 정확도와 무관하게 홈 복귀 보장."
- **면접 어필**: "복도 AMCL drift로 인한 false goal 판정 문제를 실기기에서 진단. Nav2의 확률적 위치추정 한계를 마커 절대 기준으로 보완하는 계층적 제어 구조를 설계."
- **Date**: 2026-05-18

---

### DEC-028: domain bridge 실행 위치 — LIMO 도메인(6/7)에서 실행, 단일 템플릿 yaml
- **Context**: 기존 wego_bridge는 관제 노트북(domain 5)에서 bridge_limo1.yaml, bridge_limo2.yaml 2개를 실행하는 구조. 두 가지 문제 확인.
  1. **생명주기 불일치**: LIMO 시스템이 죽어도 domain 5의 브릿지 프로세스는 살아있어 domain 5에 stale 데이터 잔류 → 연결 끊김 감지 불가
  2. **yaml 중복**: bridge_limo1.yaml과 bridge_limo2.yaml이 도메인 번호와 토픽 prefix만 다른 중복 구조 → 로봇 추가 시 파일 증가
- **Decision**: **LIMO 도메인(6/7)에서 실행 + 단일 bridge_robot.yaml 템플릿**
  - `bridge_robot.yaml`: ROBOT_DOMAIN, ROBOT_NAME 플레이스홀더 템플릿
  - `bridge_launch.py`: OpaqueFunction으로 ROS_DOMAIN_ID 읽어 치환 후 tempfile 전달 (DEC-007 패턴)
  - robot_config.yaml에서 도메인→robot_name 매핑 참조 (단일 정본)
- **실행**:
  ```bash
  export ROS_DOMAIN_ID=6 && ros2 launch wego_bridge bridge_launch.py  # LIMO 1
  export ROS_DOMAIN_ID=7 && ros2 launch wego_bridge bridge_launch.py  # LIMO 2
  ```
- **Rationale**:
  - **생명주기 일치**: LIMO 도메인 시스템 종료 시 브릿지도 함께 종료 → domain 5가 연결 끊김 즉시 감지 (추후 관제 UI 연결 상태 모니터링에 활용 가능)
  - **단일 템플릿**: yaml 파일 1개로 모든 로봇 적용. 로봇 추가 시 robot_config.yaml + waypoints.yaml만 수정
  - **일관성**: localization_launch.py, behaviour_node.py와 동일한 ROS_DOMAIN_ID 기반 자동 결정 패턴
- **면접 어필**: "브릿지 생명주기를 LIMO 도메인과 일치시켜 연결 상태 감지를 구조적으로 보장. 단일 템플릿으로 확장성 확보."
- **Date**: 2026-05-14

---

### DEC-027: 방문자 UI 아키텍처 — 태블릿 웹앱 + wego_dispatcher (rosbridge 제거)
- **Context**: 기존 DEC-026에서 결정한 "LIMO 탑재 터치 UI + rosbridge" 방식의 두 가지 문제 발견.
  1. **UX 문제**: LIMO가 낮아(바닥에서 약 30cm) 방문자가 숙여서 입력해야 함.
  2. **설계 문제**: rosbridge를 통해 태블릿 JS가 직접 `/goal_destination`을 발행하는 구조 → 로봇 제어 로직이 브라우저에 있는 잘못된 설계.
- **Decision**: **태블릿(눈높이) 웹앱 + HTTP only + wego_dispatcher(rclpy 노드)**
  | UI | 스택 | 실행 위치 |
  |----|------|-----------|
  | 관제 GUI | PyQt + rclpy | 관제 노트북 (domain 5) |
  | 방문자 UI | React (HTTP only) | 태블릿 브라우저 → `http://192.168.0.115:3000` |
  | 웹 예약 UI | React | 관제 노트북 (포트 3001) |
  - `wego_dispatcher` (rclpy 노드, domain 5): FastAPI 폴링 → 로봇에 goal/speak 발행
  - 태블릿은 FastAPI HTTP만 사용. rosbridge 완전 제거.
- **Rationale**:
  - **rosbridge 제거**: 로봇 제어 로직(어느 로봇에 배정할지, goal 발행)이 ROS 노드(wego_dispatcher) 안에 있어야 함. 브라우저 JS에서 ROS 토픽을 직접 발행하는 것은 책임 분리 원칙 위반.
  - **태블릿**: 눈높이에서 사용 → UX 문제 해소. 같은 네트워크의 브라우저면 되므로 별도 HW 불필요.
  - **wego_dispatcher polling 방식**: 태블릿이 FastAPI에 HTTP POST → missions 테이블 PENDING 삽입 → wego_dispatcher가 0.5초 폴링으로 수락. 브라우저와 ROS 사이에 FastAPI가 버퍼 역할 → 네트워크 단절에도 안전.
  - **임무 할당 규칙**: limo1 우선, 둘 다 IDLE이면 limo1, 둘 다 BUSY면 503 반환.
  - **포트폴리오 가치**: "브라우저가 아닌 ROS 노드가 로봇을 제어한다"는 설계 원칙을 면접에서 설명 가능.
- **면접 어필**: "rosbridge 방식은 로봇 제어 로직이 브라우저에 있는 설계 결함. 태블릿은 UI만 담당하고, 임무 할당과 ROS 토픽 발행은 wego_dispatcher(rclpy 노드)가 전담하도록 책임을 분리했습니다."
- **Date**: 2026-05-13

---

### DEC-026: UI 기술 스택 선택 — PyQt(관제) / React(방문자/예약)
- **Context**: 3개의 UI가 필요. 각 UI의 핵심 요구사항이 달라 기술 스택을 별도로 결정.
- **Decision**:
  | UI | 스택 | 실행 위치 |
  |----|------|-----------|
  | 관제 GUI | PyQt + rclpy | 관제 노트북 (domain 5) |
  | 방문자 UI | React (HTTP only) | 태블릿 브라우저 (DEC-027로 최종 확정) |
  | 웹 예약 UI | React | 관제 노트북 (포트 3001) |
- **Rationale**:
  - **RQt 제외**: 고정 목적 운용 UI에 플러그인 호스트 구조는 불필요한 복잡성. 현업에서도 운용 UI는 PyQt 직접 작성이 표준.
  - **관제 GUI = PyQt**: amcl_pose, robot_status 실시간 ROS 토픽이 핵심. rclpy + QThread 직접 연결이 가장 안정적.
  - **방문자 UI = React (HTTP only)**: DEC-027에서 rosbridge 제거 결정. 태블릿 브라우저에서 FastAPI HTTP만 사용.
  - **웹 예약 UI = React**: 외부(학부모/학생) 접근 필요 → 웹 기반 필수.
- **면접 어필**: "UI 목적(ROS 실시간 vs DB 조회 vs 외부 접근)에 따라 기술 스택을 달리 선택."
- **Date**: 2026-05-12 (DEC-027로 터치 UI 방식 최종 확정: 2026-05-13)

---

### DEC-025: 예약 백엔드 스택 및 서버 위치 — FastAPI + MySQL + SQLAlchemy, 관제 노트북
- **Context**: 예약 시스템 백엔드 기술 스택과 서버 실행 위치 결정. 다중 클라이언트(웹 예약 UI, LIMO 터치 UI 2대, 관제 GUI) 동시 접근이 필요.
- **Decision**: **FastAPI + MySQL + SQLAlchemy ORM, 관제 노트북(192.168.0.115)에서 실행**
- **Rationale**:
  - **FastAPI**: Python 기반으로 ROS2 코드와 언어 통일. 자동 Swagger 문서(/docs). 비동기 지원. SQLite 대비 다중 클라이언트 동시 접근에 안정적.
  - **MySQL vs PostgreSQL**: 국내 기업 표준이 MySQL. 이 규모(상담 예약 수백 건)에서 두 DB의 실질적 차이 없음. MySQL 선택.
  - **SQLAlchemy ORM**: DB 추상화 → MySQL/PostgreSQL 전환 시 .env DATABASE_URL 한 줄만 변경. 쿼리를 Python으로 표현하여 SQL injection 방지.
  - **관제 노트북 선택**: 서버 노트북은 Nav2 × 2, wego_behaviour × 2 등 ROS 연산 부하가 이미 큼. 관제 노트북은 wego_ui, wego_bridge만 실행 → 여유 있음. 예약 서버(FastAPI)는 ROS와 무관하므로 ulsan_ws 외부에 독립 배치.
  - **포트**: FastAPI 8000, MySQL 3306 (로컬). 외부 클라이언트는 http://192.168.0.115:8000 으로 접근.
  - **CORS**: React(3000) → FastAPI(8000) 크로스오리진 요청을 위해 CORSMiddleware allow_origins=["*"] 설정.
- **패키지 위치**: `/home/yechan/Ulsan-X/ulsan_ui/ulsan_reservation/` (ulsan_ws 외부)
- **면접 어필**: "FastAPI + SQLAlchemy 조합은 Python 생태계 표준 스택. ORM 추상화로 DB 교체 비용을 최소화하고, ROS 연산 부하를 고려해 서버 위치를 관제 노트북으로 결정."
- **Date**: 2026-05-12

---

### DEC-024: NLU 방식 변경 — LLM API 폐기, 터치 UI + DB 조회로 대체
- **Context**: 기존 음성 파이프라인에서 발화("1강의실 안내해줘") → LLM API → waypoint 매핑 방식으로 목적지를 결정했으나, 예약 기반 안내 시스템 도입으로 목적지가 DB에서 결정됨.
- **Decision**: **LLM API 기반 NLU 폐기 → 터치 UI + DB 조회로 완전 대체**
  - 방문자가 LIMO 터치 화면에서 이름 + 생년월일 또는 전화번호 끝자리 입력
  - DB 조회 → 오늘 날짜 + 현재 시간대 예약 확인 → 배정 상담실 반환
  - TTS: "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다."
  - Nav2 goal 전달 → 안내 시작
- **Rationale**:
  - 목적지가 예약 DB에서 결정되므로 NLU 불필요
  - LLM API 응답 지연(DEC-004) 문제 원천 해소
  - 음성 인식 오류(발화 인식 실패, 목적지 매핑 오류) 없이 정확한 목적지 안내
  - wego_voice 패키지에서 NLU 모듈 제거, STT/wakeword도 터치 UI 방식에서는 불필요
  - 면접 어필: "음성 NLU의 불확실성을 예약 시스템 도입으로 구조적으로 제거. 목적지 결정을 DB 조회로 확정하여 안내 정확도 100% 보장."
- **Date**: 2026-05-11

---

### DEC-023: 예약 기반 안내 시스템 도입
- **Context**: 기존 설계는 방문자가 현장에서 음성으로 목적지를 말하면 로봇이 안내하는 방식. 학원 상담 예약 서비스와 연동하여 사전 예약자를 정확하게 안내하는 시스템으로 변경.
- **Decision**: **웹 예약 서비스 + LIMO 터치 UI + 공유 DB** 구조 채택
- **예약 서비스 스펙**:
  - 예약 기간: 당일 ~ 최대 2주 이내, 평일 09:00~17:00, 1시간 단위
  - 예약 정보: 이름 + 전화번호
  - 상담실 4개(counseling_1~2, intensive_counseling_1~2) → 동일 시간대 최대 4명 예약 가능
  - 상담실 자동 배정 (예약자가 선택 불필요)
  - 중복 예약 방지 (4개 상담실 모두 차면 해당 시간대 예약 불가)
- **예약 DB 상태 관리**:
  - `PENDING`: 예약됨, 미방문
  - `IN_PROGRESS`: LIMO 안내 시작 시 전환
  - `COMPLETED`: LIMO 홈 복귀 시 전환
  - 안내 시작 시 즉시 IN_PROGRESS로 업데이트 → 중복 체크인 방지
- **LIMO 터치 UI 흐름**:
  1. 방문자가 홈에 있는 LIMO 터치 화면에서 예약 서비스 선택
  2. 이름 + 생년월일 또는 전화번호 끝자리 입력
  3. DB 조회 → 오늘 날짜 + 현재 시간대 예약 확인
  4. TTS: "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다."
  5. Nav2 goal 전달 → 안내 시작 → DB IN_PROGRESS
- **임무 할당**: 별도 로직 불필요. 안내 중인 LIMO는 물리적으로 홈에 없으므로 방문자가 자연스럽게 홈에 있는 LIMO 사용
- **미결정**:
  - 워크인 방문자(예약 없이 방문) 처리 방식
  - 웹 서비스 호스팅 위치
- **확정**:
  - DB: **MySQL (서버 노트북 로컬)** — 2026-05-12
    - 다중 클라이언트(웹 + LIMO 2대) 동시 접근을 고려해 SQLite 대신 MySQL 선택
    - FastAPI + SQLAlchemy + MySQL 조합 (실무 표준 스택)
    - 서버 노트북에서 MySQL 서버 프로세스 실행 (`sudo apt install mysql-server`)
- **Rationale**:
  - 목적지 결정의 불확실성 제거 (음성 → DB 조회로 확정)
  - 학원 상담 예약이라는 실제 서비스 시나리오와 일치
  - 면접 어필: "실제 서비스 요구사항(예약 시스템)과 로봇 안내를 통합한 end-to-end 시스템 설계."
- **Date**: 2026-05-11

---

### DEC-022: 멀티로봇 충돌 회피 방식 — 우선순위 기반 FSM pause/resume
- **Context**: 기존 `ulsan_obstacle_layer`(PeerObstacleLayer)는 상대 amcl_pose를 global costmap에 LETHAL 장애물로 주입하는 방식. global costmap은 planner가 경로 계획 시에만 참고하므로, 경로 계획 후 이동 중 상대 로봇이 움직여도 controller는 이를 인식하지 못해 실질적 충돌 회피 불가.
- **문제 분석**:
  - global costmap 반영 주기 + planner 재계획 지연 → 충돌 직전에도 반응 불가
  - "경로는 피해서 계획했으나 실행 중에 만나면 충돌"하는 구조적 한계
  - local costmap에 반영해도 Wi-Fi 지연으로 amcl_pose 업데이트가 느려 실시간 회피 불충분
- **Decision**: **우선순위 기반 FSM pause/resume**
  - GUIDING 상태가 RETURNING 상태보다 높은 우선순위
  - 두 로봇이 일정 거리 이내 진입 시 낮은 우선순위 로봇이 Nav2 goal cancel → WAITING 상태 진입
  - 높은 우선순위 로봇이 통과(거리 벌어짐) 후 WAITING 로봇이 goal 재제출 → 주행 재개
- **우선순위 규칙**:
  | LIMO 1 | LIMO 2 | 정지 대상 |
  |--------|--------|-----------|
  | GUIDING | RETURNING | LIMO 2 |
  | RETURNING | GUIDING | LIMO 1 |
  | RETURNING | RETURNING | LIMO 2 (LIMO 1 기본 우선순위) |
- **구현 위치**: `wego_traffic` (중간 노트북)
  - 두 amcl_pose 구독 → 거리 계산 → threshold 이하 시 우선순위 판정
  - `/limo_N/pause`, `/limo_N/resume` 토픽 발행
  - `wego_behaviour` FSM에 `WAITING` 상태 추가: pause 수신 → goal cancel, resume 수신 → goal 재제출
- **Rationale**:
  - 한 로봇이 물리적으로 멈추므로 충돌이 구조적으로 불가능
  - 네트워크 지연 영향 최소화: pause/resume은 단순 토픽 신호로 충분
  - Nav2 lifecycle manager pause는 AMCL까지 멈추는 부작용 → FSM goal cancel 방식 채택
  - 기존 `ulsan_obstacle_layer` (PeerObstacleLayer) 폐기
  - 면접 어필: "동적 장애물에 대한 costmap 기반 회피의 한계를 실기기에서 확인하고, 상태 기반 우선순위 제어로 전환. 충돌 회피를 확률적 회피가 아닌 결정론적 방식으로 보장."
- **Date**: 2026-05-11

---

### DEC-021: 연산 오프로딩 아키텍처 — LIMO 드라이버 전용, 중간 노트북이 Nav2/상위 로직 담당
- **Context**: Jetson Orin Nano의 부하가 과중하여 Nav2 주행 중 control loop missed 경고 및 주행 불안정 발생. LIMO에서 Nav2, AMCL, behaviour, aruco, voice를 모두 실행하는 현재 구조에서는 실용적 운용 불가.
- **Decision**: **LIMO는 하드웨어 드라이버만, 중간 노트북이 모든 연산 담당**
  - LIMO: `limo_base`, `ydlidar`, `orbbec`, `robot_state_publisher`, EKF
  - 중간 노트북: Nav2(AMCL + planner + controller), `wego_behaviour`, `wego_aruco`, `wego_voice`, `wego_traffic`
  - 관제 UI 노트북: `wego_ui`
- **Domain 재할당**:
  | 기기 | 도메인 |
  |------|--------|
  | LIMO 1 | 5 |
  | LIMO 2 | 6 |
  | 중간 노트북 | 5 + 6 (터미널 분리) |
  | 관제 UI 노트북 | 7 |
  - 중간 노트북은 별도 domain 불필요: 터미널마다 `ROS_DOMAIN_ID=5` / `ROS_DOMAIN_ID=6` 설정으로 각 LIMO domain에 직접 참여
  - LIMO와 중간 노트북이 같은 domain → domain bridge 없이 `/scan`, `/odom`, `/tf` 공유
  - 관제 UI 노트북(domain 7)은 기존 wego_bridge로 amcl_pose 수신
- **Rationale**:
  - LIMO는 드라이버만 실행 → CPU/GPU 부하 최소화, 주행 안정성 확보
  - 중간 노트북의 강력한 CPU로 Nav2, STT, NLU 등 연산 집약적 작업 처리
  - 같은 domain에서 DDS로 토픽 자동 공유 → 추가 브릿지 불필요
  - cmd_vel은 중간 노트북 controller_server → LIMO로 직접 전달 (같은 domain)
  - 면접 어필: "Jetson 부하 문제를 실기기에서 확인하고, ROS2 DDS domain 공유 특성을 활용해 별도 브릿지 없이 연산을 노트북으로 오프로딩하는 아키텍처를 설계."
- **기존 구조 대비 변경점**:
  - 기존: 노트북=5, LIMO1=6, LIMO2=7 → 신규: LIMO1=5, LIMO2=6, 중간 노트북=5+6, UI 노트북=7
  - wego_bridge: LIMO에서 실행 → 중간 노트북에서 실행 (amcl_pose를 domain 5,6 → domain 7 브릿징)
  - ulsan_obstacle_layer: 폐기 (DEC-022로 대체)
- **Date**: 2026-05-11

---

### DEC-020: 복도 AMCL drift 해결 방식 — passive ArUco pose corrector
- **Context**: 복도 주행 중 AMCL이 y 방향으로 ~0.29m drift 발생. Nav2 goal checker는 TF(`map→base_link`) 기반 판정 = AMCL 추정값 기반이므로, drift된 상태에서 실제 홈에 도착하기 전에 goal 판정이 내려지는 문제 발생. 복도(긴 직선, 특징점 없음)에서 AMCL symmetric ambiguity로 위치가 당겨지는 현상.
- **문제 분석**:
  - y좌표 모니터링 결과: 복도 진행 중 0.292m 오추정 → goal 판정 → 제자리 회전 후 AMCL 재수렴(0.52). 실제 홈 도착 전에 멈추는 패턴 반복.
  - 복도 벽 마커: 로봇이 복도를 가로질러 홈 방향으로 이동하므로 카메라가 벽을 바라보지 않아 감지 불가.
  - visual servoing: 홈 도착 후 1회 보정에는 적합하나 주행 중 drift 누적을 막지 못함.
- **Options**:
  - A) Nav2 time-based goal checker (일정 시간 머물러야 판정) — Nav2 플러그인 커스텀 필요, 복잡
  - B) goal tolerance 완화 → 이미 0.10m, 더 완화하면 반대로 정밀도 저하
  - C) update_min_d/a 낮춰 AMCL 업데이트 빈도 증가 → 부분 완화
  - D) **passive ArUco pose corrector** — 바닥 마커를 웨이포인트마다 설치, 주행 중 감지 시 /initialpose 자동 발행
- **Decision**: **C + D 병행**
  - `update_min_d: 0.25→0.1`, `update_min_a: 0.2→0.1` (즉시 적용)
  - `aruco_pose_corrector` 노드: 주행 중 바닥/벽 마커 감지 → full 3D transform → /initialpose 발행
- **Rationale**:
  - 바닥 마커(카메라 하향 약 15°, 높이 20cm → 75cm 앞 바닥 인식): 로봇 진행 방향 앞에 두면 이동 경로에서 반드시 감지됨.
  - TF lookup(`base_link←camera_optical`)으로 camera tilt 자동 반영 → 마커 위치 부정확한 수동 계산 불필요.
  - MIN_CONSISTENT=3, COOLDOWN=10s: 단일 프레임 노이즈 방지 + 과도한 AMCL 리셋 방지.
  - 변환 체인: `T_map_base = T_map_marker × inv(T_cam_marker) × inv(T_base_cam)` (full 3D, 카메라 tilt 반영)
  - 면접 어필: "AMCL만으로 해결 불가한 복도 drift를 마커 절대 좌표로 주기적 리셋하는 구조. 상용 AGV의 QR 바닥 마커 체크포인트와 동일한 원리."
- **구현 현황 (2026-05-07)**:
  - `wego_aruco/pose_corrector.py` 신규 작성 (aruco_pose_corrector 노드)
  - `setup.py` entry point 추가
  - markers.yaml 확장: map 좌표 미측정(map_x=0, map_y=0)이면 자동 건너뜀
- **실기기 검증 완료 (2026-05-08)**:
  - home1 바닥 마커(ID 0) 방향 캘리브레이션: 시계방향 90° 회전으로 map_yaw=π/2 확정
  - classroom_1 → home1 왕복 주행 중 AMCL 자동 보정 확인 (10s cooldown 간격)
  - Nav2 home1 goal 성공 확인
- **Date**: 2026-05-07 → 2026-05-08 검증 완료

---

### DEC-019: SLAM 알고리즘 선택 — Cartographer (SLAM Toolbox 제외)
- **Context**: 학원 복도(긴 직선 + 유리 환경)에서 SLAM 맵 빌딩 필요. ROS2 표준인 SLAM Toolbox를 먼저 시도했으나 맵 빌딩 실패 반복.
- **문제 분석**:
  - SLAM Toolbox(karto 백엔드)는 스캔-스캔 매칭 방식 → 복도처럼 양쪽 벽 패턴이 동일한 환경에서 현재 스캔을 이전 위치의 스캔으로 오인 (Symmetric Ambiguity)
  - 결과: 로봇이 전진해도 TF가 계속 당겨져 맵에서 제자리걸음 현상 발생
  - 추가 문제: YDLiDAR Tmini Plus의 드라이버가 매 스캔 포인트 수를 250↔251로 흔들림 → SLAM Toolbox karto가 첫 스캔 기준 포인트 수와 다른 스캔을 전부 reject → 맵 업데이트 없음
- **Decision**: **Cartographer로 SLAM 전환**
  - SLAM: Cartographer → `.pgm` + `.yaml` 맵 저장
  - 위치추정: AMCL (Cartographer 맵 호환)
  - 주행: Nav2
- **Rationale**:
  - Cartographer는 서브맵(submap) 단위로 스캔을 누적 후 매칭 → 단일 스캔 오매칭에 강함
  - CSM(Correlative Scan Matcher) + Ceres 최적화로 복도 환경에서 더 안정적
  - 스캔 포인트 수 변동에 관대 (karto처럼 reject 없음)
  - 유리 환경에서의 난반사 강건성은 두 알고리즘 동일 (센서 레벨 문제)
  - Cartographer 맵(.pgm)은 AMCL과 완전 호환 → 기존 Nav2 스택 재사용 가능
- **트레이드오프**:
  - SLAM Toolbox localization 모드(posegraph 기반) 사용 불가 → AMCL로 대체
  - Cartographer는 SLAM Toolbox보다 무거움 (실시간 주행 중 CPU 부하 높음)
- **면접 어필**: "복도 환경의 Symmetric Ambiguity 문제를 실험적으로 확인하고, 서브맵 기반 CSM을 사용하는 Cartographer로 전환했습니다. 스캔-스캔 매칭 방식의 한계를 직접 경험하고 알고리즘 특성을 비교 분석하여 선택했습니다."
- **Date**: 2026-05-05

---

### DEC-018: ArUco 홈 도킹 방식 — 2-Phase Lateral-Only Visual Servoing + AMCL 리셋
- **Context**: 홈 복귀 시 ArUco 마커 활용 방식을 결정. 초기 설계는 /initialpose 발행(AMCL 교정)만 수행하는 방식이었으나, visual servoing(물리 정밀 정차)으로 전환 논의 후 두 방식을 결합하는 방향으로 최종 확정. 이후 실기기 검증 과정에서 2-Phase 설계로 구체화.
- **Decision**: **Coarse-to-Fine 패턴** — Nav2 대략 이동 → 2-Phase ArUco visual servoing → 마커 역산 /initialpose 발행
  - Phase 1: 전진 접근 (2m → 30cm) + lateral-only 보정
  - Phase 2: 후진 정밀 정차 (30cm → 2.007m) + lateral-only 보정
- **Rationale**:
  - visual servoing만: 물리 위치는 정밀하나 AMCL drift 미보정 → 다음 안내에서 오차 누적
  - /initialpose만: AMCL 보정되나 물리 위치는 Nav2 허용 오차(±10~30cm) 그대로
  - 두 방식 결합: 물리 정밀 정차 + AMCL 리셋 동시 달성
  - MiR, Fetch 등 상용 AMR 및 Nav2 opennav_docking과 동일한 산업 표준 패턴
  - **2-Phase 설계 이유**: 단순 전진 접근(dist→target_dist)은 30cm에서 lateral 미수렴으로 타임아웃 발생. 30cm까지 전진 정렬 후 후진하면 Phase 1의 정밀 정렬이 Phase 2 시작점으로 활용됨.
  - **lateral-only 제어 이유**: 제자리 yaw 보정 시 로봇 회전으로 마커가 카메라 FOV 이탈 → 미감지. lateral만 보정해도 전진 중 기하학적으로 yaw가 수렴함.
  - 면접 어필: "Coarse-to-Fine Localization 패턴을 적용했으며, 정밀 정차 후 알려진 절대 좌표로 AMCL을 리셋하는 방식은 상용 AMR과 동일한 구조. 카메라 FOV 유지를 위한 lateral-only 제어는 실기기 반복 검증을 통해 도출."
- **구현 현황 (2026-05-04)**:
  - `wego_aruco/aruco_localizer.py`: 2-Phase 구조, lateral-only P제어, /aruco_correct 서비스
  - `wego_behaviour/states.py` ReturningState: /aruco_correct 호출만 수행
  - /initialpose 발행 주체: `wego_aruco` (마커 map 좌표 역산)
    - 역산 공식: `robot_x = marker_x + total_dist × cos(marker_yaw)` (**+ 부호**)
    - cam_offset: 0.23m (base_link → camera_link)
  - 실기기 검증 결과: Phase 1 lat=0.001m, Phase 2 lat=0.008m 수렴
- **마커 구성**: ID 0 (LIMO1), ID 1 (LIMO2) — 각 로봇 홈 정면 벽 부착, 크기 20cm × 20cm
- **markers.yaml 현황 (2026-05-08 업데이트)**:
  - ID 0: target_dist=0.946, map_x=0.0, map_y=-0.196, map_yaw=1.5708, calibrated=true
    - home_robot1 (0.0, 0.98, -π/2) 기준 역산: camera_y=0.75, marker_y=0.75-0.946=-0.196
    - 마커 방향: 시계방향 90° 회전으로 map_yaw=π/2 확정 (캘리브레이션)
  - ID 1: 미측정.
- **미완료**: _publish_initialpose 부호 버그 수정 + /initialpose 주석 해제, markers.yaml ID 1 측정
- **Date**: 2026-05-01 → 2026-05-04 → 2026-05-08 업데이트

---

### ~~DEC-017: wego_voice on_duty 게이팅 위치~~ — **폐기 (2026-05-11)**
- **폐기 이유**: DEC-024로 wakeword/STT/NLU가 제거되고 터치 UI + DB 조회 방식으로 전환됨. on_duty 개념 자체가 불필요해져 게이팅 로직도 함께 폐기.
- **Date**: 2026-04-30 → 폐기 2026-05-11

---

### DEC-016: 유리 구간 주행 불안정 해결 방식 + ArUco 마커 운용 전략 ✅
- **Context**: 유리 회전 통과 구간에서 로봇이 빙글빙글 돌며 통과 지연. 초기 원인으로 AMCL 파티클 수렴 문제를 의심했으나, RViz 실기기 분석(2026-04-29) 결과 파티클은 정상 수렴 확인. 실제 원인은 **유리 난반사에 의한 유령 장애물(phantom obstacle)**로 재확인.
- **확인된 사실**:
  - LiDAR는 유리를 투과하거나 난반사 → 없는 위치에 장애물이 global costmap에 찍힘
  - 난반사 빔은 raytrace 경로와 달라 자동 소거 불가 → 유령 장애물 지속
  - 유령 장애물이 경로를 막음 → 반복 리플래닝 → 빙글빙글
  - AMCL 파티클은 정상 → ArUco로 유리 구간 AMCL 보정은 불필요
  - 유리문 닫힘 시 경로 생성 불가 → **운용 정책: 유리문은 항상 열린 상태 유지 가정**
- **시도한 해결 방법 및 결과**:
  - `obstacle_max_range` 축소 → phantom이 2m 이내라 효과 없음
  - Keepout Filter 센서 무시 구역 → phantom이 폴리곤 밖에도 찍혀 효과 없음
  - 맵 유리 연장 (GIMP) → 로봇 통과 경로 차단
  - `laser_filters` 각도 필터 → 회전 중 방향 변화로 완벽 해결 불가
  - `observation_persistence` 단축 → 매 스캔 동일 위치 phantom 재생성으로 효과 없음
  - VoxelLayer + Orbbec 카메라 → IR 구조광이 유리 투과, depth 값 없음. 유리 감지 불가로 부적합
  - **Keepout Filter (금지구역) + DenoiseLayer 적용** → 목적지·홈 구간 주행 정상화. 유리 회전문 통과는 여전히 불가.
- **최종 결론 (2026-04-29 실기기 검증)**:
  - Keepout Filter는 global costmap에만 적용 → global 경로는 우회. 그러나 유리 근처를 지나는 경로에서 local costmap phantom으로 인해 `controller_server: Failed to make progress` 발생.
  - **유리 회전문 통과는 LiDAR 물리 한계 — 소프트웨어로 완전 해결 불가** 확정
  - **운용 정책: 유리 회전문 통과 구간은 경로에서 영구 제외**
  - 목적지·홈 안내 주행에는 유리 회전문 통과가 불필요 → 서비스 요구사항 내에서 완전 동작
  - 면접 어필: "LiDAR 물리적 한계를 실기기 검증으로 확인하고, 운용 요구사항 내에서 완전 동작하는 현실적 판단을 내렸다"
- **ArUco 마커 용도 재정의 (DEC-016 핵심 결정, 2026-04-30 최종 확정)**:
  - 유리 구간 보정 목적 → **폐기**
  - 각 목적지 마커 부착 방식 → **폐기** (Nav2 정밀도로 목적지 도착은 충분)
  - **홈 복귀 시 1회 보정**으로 최종 확정: 로봇이 목적지 안내 후 홈으로 복귀할 때 ArUco로 정밀 정차
  - 마커는 **홈 위치에만 2개** (로봇1 홈, 로봇2 홈 — 각 로봇이 자신의 마커만 탐색)
  - drift 리셋 타이밍: 홈 복귀 시 1회로 충분 (편도 주행 누적 오차 리셋)
  - 산업용 AMR 도킹 마커와 동일 원리
  - 면접 어필: "목적지는 Nav2 정밀도로 충분하고, 장시간 운영 시 누적되는 AMCL drift는 홈 복귀 시 ArUco 1회 보정으로 리셋하는 구조를 설계했다. 마커 수를 최소화(2개)하면서 정밀도를 보장하는 현실적 설계."
- **마커 사양**: ArUco DICT_4X4_50, 10cm × 10cm, 종이 인쇄, 각 로봇 홈 위치 벽 부착
- **구현 패키지**: `wego_aruco` (신규, ament_python) — 상세 설계는 `docs/ref/ARUCO-LOCALIZER.md`
- **Date**: 2026-04-28 (재확정: 2026-04-29, 최종 결론: 2026-04-30)

---

### ~~DEC-015: 멀티로봇 임무 할당 — on_duty 코디네이터~~ — **폐기 (2026-05-11)**
- **폐기 이유**: DEC-023으로 터치 UI 방식 도입. 방문자가 물리적으로 홈에 있는 LIMO를 직접 선택하므로 on_duty 개념이 불필요. 안내 중인 LIMO는 홈에 없어 자연스럽게 분리됨.
- **wego_traffic 역할 재정의**: on_duty 결정 제거 → **충돌 회피(pause/resume)만 담당** (DEC-022)
- **Date**: 2026-04-27 → 폐기 2026-05-11

---

### DEC-014: wego_behaviour 구현 방식 — BT vs FSM
- **Context**: 미션 레벨 제어(대기→호출→안내→복귀)를 BehaviorTree.CPP로 구현하려 했으나, 이 레이어에서 BT의 필요성이 불명확함. 동시에 "BT 설계 경험"을 면접에서 어필하려면 어느 레이어의 BT를 구현해야 하는지 검토 필요.
- **Decision**:
  - `wego_behaviour`: **Yasmin FSM** (Python, ament_python)으로 구현 — 미션 모드 전환 (대기 / 안내 중 / 복귀 중)
  - **Nav2 BT 커스터마이징**: 커스텀 BT 조건·액션 노드 C++ 작성 + XML 트리 수정 — 이것이 면접 어필 포인트
- **Rationale**:
  - Nav2 공식 문서 및 업계 표준: BT는 복구 동작·병렬 행동·복잡한 조건 분기에 적합. 상태 5개 이하의 선형 흐름(우리 미션)에는 FSM이 적절.
  - 자율주행 분야 면접에서 "BT 커스터마이징 경험"은 Nav2 내부 BT(커스텀 노드 작성, XML 설계)를 의미함. wego_behaviour를 BT로 짜는 것은 포트폴리오 가치가 낮음.
  - Yasmin: ROS2 전용 경량 Python FSM 라이브러리. SMACH 후계. 상태 전환이 코드로 명확히 표현됨.
  - 하이브리드 구조(고수준 FSM + 실행 레이어 BT)가 실제 서비스 로봇 업계 트렌드.
- **Nav2 BT 커스텀 노드 후보**:
  - ~~`VoiceTriggerCondition`~~: **폐기** — 웨이크워드 제거(DEC-024)로 불필요
  - ~~`PeerRobotBusyCondition`~~: **폐기** — on_duty 개념 제거(DEC-015 폐기)로 불필요
- **Date**: 2026-04-27

---

### DEC-013: wego_fleet 패키지 분리 — wego_bridge (Python) + wego_fleet (C++)
- **Context**: 현재 `wego_fleet`(Python, ament_python)에 domain bridge launch 파일과 FleetObstacleLayer C++ 플러그인을 함께 넣으려 했으나, C++ Nav2 플러그인은 ament_cmake 패키지여야 하므로 같은 패키지에 공존 불가.
- **Decision**: 패키지를 역할과 빌드 시스템 기준으로 분리
  - `wego_bridge` (Python, ament_python): 현재 `wego_fleet` rename. domain bridge launch 파일만 담당.
  - `wego_fleet` (C++, ament_cmake): FleetObstacleLayer Nav2 costmap 플러그인 전용. 신규 작성.
- **Rationale**:
  - Python launch 파일과 C++ 공유 라이브러리는 빌드 시스템(ament_python vs ament_cmake)이 달라 같은 패키지에 공존 불가.
  - 역할도 분리됨: `wego_bridge`는 통신 인프라(domain bridge), `wego_fleet`은 Nav2 플러그인(장애물 회피 로직).
  - 취업용 프로젝트 관점에서 "각 패키지의 책임이 단일하다"는 설명 가능.
- **실행 예정 작업**: `ulsan_ws/src/wego_fleet/` 디렉토리 및 내부 파일 rename → `wego_bridge/`
- **Date**: 2026-04-22

---

### DEC-012: 맵 배포 방식 — domain bridge 스트리밍 vs 파일 사전 배포
- **Context**: 관제 노트북과 각 로봇이 동일한 맵을 사용해야 함. /map 토픽을 domain bridge로 스트리밍할 것인지, 파일로 미리 배포할 것인지 결정 필요.
- **Options**:
  - A) domain bridge로 `/map` 스트리밍: 리더 로봇이 /map을 domain 5로 실시간 전송
  - B) 맵 파일 사전 배포: SLAM으로 생성한 map.pgm + map.yaml을 scp로 배포, 각 기기가 로컬 map_server 실행
- **Decision**: **B — 맵 파일 사전 배포**
- **Rationale**:
  - `/map`은 OccupancyGrid 메시지로 수십~수백 KB. Wi-Fi 브릿징 시 TS-001 재현 위험.
  - 학원 환경은 정적(맵 변경 없음). 매 부팅마다 스트리밍할 이유 없음.
  - 각 기기가 자체 map_server 실행 → AMCL, Nav2, 관제 UI 모두 로컬 /map 구독 → 네트워크 의존성 제거.
  - domain bridge 설정 단순화: /map 제거, /amcl_pose만 브릿징.
  - `leader:=true` 구분 불필요 → 모든 로봇 동일한 launch 명령.
- **운용 절차**:
  1. LIMO 1에서 Cartographer SLAM 실행 → `ros2 run nav2_map_server map_saver_cli -f ~/map`
  2. `scp map.pgm map.yaml` → LIMO 2, 노트북으로 배포
  3. 각 기기 부팅 시 map_server 노드가 로컬 파일 읽어 /map 발행
- **Date**: 2026-04-21

---

### DEC-011: 멀티로봇 fleet 통신 방식 — TF 공유 vs amcl_pose 공유
- **Context**: 기존 구현에서 TF frame prefix(robot1/base_link 등)로 두 로봇 TF를 분리하고 `/tf` 를 노트북으로 브릿징했음. 이 방식을 폐기하고 amcl_pose 공유 방식으로 전환.
- **Options**:
  - A) TF frame prefix 방식: robot_state_publisher frame_prefix + EKF odom_frame 치환 → `/tf` 브릿징
  - B) amcl_pose 공유 방식: 각 로봇이 표준 TF 유지, `/amcl_pose`만 브릿징
- **Decision**: **B — amcl_pose 공유**
- **Rationale**:
  - Open-RMF(ROS2 공식 fleet 관제 표준)와 동일한 설계 원칙. fleet 경계에서 전달하는 것은 TF 트리가 아니라 pose(위치).
  - TF는 단일 로봇 내부 센서 좌표 변환 도구. domain 경계를 넘어 TF 트리를 브릿징하는 것은 과설계.
  - `/amcl_pose`(PoseWithCovarianceStamped)는 단일 메시지로 위치를 표현. 가볍고 브릿징 신뢰성 높음.
  - `/tf`는 많은 노드가 퍼블리시하는 복합 스트림 → 브릿징 시 타이밍, 중복, 프레임 충돌 위험.
  - 각 로봇의 TF 트리는 독립적으로 완결. 노트북은 pose만 받아 마커로 시각화.
  - Robot 간 회피: 상대 amcl_pose → FleetObstacleLayer → costmap 가상 장애물. Nav2 플래너 변경 없이 적용 가능.
- **폐기된 구현**:
  - `wego/config/limo_ekf_robot.yaml` (ROBOT_NAME 템플릿)
  - teleop_launch.py의 robot_name + frame_prefix 로직
  - wego_fleet domain_bridge 설정 파일들 (TF 브릿징 버전)
- **새 구현 대상**:
  - `wego_fleet/config/domain_bridge_robot.yaml`: amcl_pose → domain5, amcl_pose → peer domain
  - `wego_fleet/launch/robot_bridge_launch.py`: 환경변수로 ROBOT_DOMAIN/PEER_DOMAIN 자동 결정
  - `wego_fleet/fleet_obstacle_layer/`: C++ costmap plugin (FleetObstacleLayer)
- **Date**: 2026-04-21

---

### DEC-010: Domain Bridge 실행 위치 및 노트북 워크스페이스 구성
- **Context**: domain_bridge를 어디서 실행하고, 노트북에 어떤 워크스페이스가 필요한가.
- **Domain Bridge 실행 위치**:
  - **각 LIMO 로봇에서 실행 (push 방식)**
  - 노트북은 domain 5에서 amcl_pose를 수동으로 수신만 함. 브릿지 프로세스 불필요.
  - 단일 템플릿 YAML + `ROS_DOMAIN_ID` 환경변수 → 로봇 1, 2 동일한 launch 명령
- **노트북 워크스페이스 구성**:
  - `wego_fleet` 패키지 불필요: domain_bridge와 FleetObstacleLayer 모두 LIMO에서만 실행
  - `map_server`: `nav2_map_server` apt 패키지만 설치하면 실행 가능. 워크스페이스 불필요.
  - Qt 관제 GUI: `wego_ui` 패키지 신규 작성 → 노트북 워크스페이스에만 존재
  ```
  laptop_ws/src/
  └── wego_ui/    # Qt 관제 GUI (map_server 기동 + 위치 마커 시각화)
  ```
- **구현 (LIMO용)**:
  - `wego_fleet/config/domain_bridge_robot.yaml`: `ROBOT_DOMAIN`, `PEER_DOMAIN`, `ROBOT_NAME` 플레이스홀더 템플릿
  - `wego_fleet/launch/robot_bridge_launch.py`: OpaqueFunction으로 `ROS_DOMAIN_ID` 읽어 치환, tempfile 전달
- **실행**:
  ```bash
  # LIMO 1, LIMO 2 동일한 명령
  ros2 launch wego_fleet robot_bridge_launch.py
  ```
- **Date**: 2026-04-17 (수정: 2026-04-21)

---

### DEC-005: 멀티로봇 분리 방법 — ROS2 namespace vs TF frame 이름 변경
- **Context**: 두 로봇의 TF를 노트북에서 동시에 수신할 때 `base_link`, `odom` 프레임이 충돌. 이를 해결하는 방법 선택 필요.
- **Options**:
  - A) ROS2 namespace 적용 (`/robot1/scan`, `/robot1/odom` 등 모든 토픽에 prefix)
  - B) TF frame ID만 변경 (`robot1/base_link`, `robot1/odom`), 토픽 이름은 유지
- **Decision**: **B — TF frame ID만 변경**
- **Rationale**: 각 로봇이 서로 다른 ROS domain(LIMO1=6, LIMO2=7)에서 동작하므로 `/scan`, `/amcl_pose` 등 토픽 이름이 같아도 도메인이 달라 충돌 없음. 충돌이 발생하는 건 노트북(domain 5)에서 두 로봇의 `/tf`를 머지할 때뿐 → frame ID만 구분하면 충분. namespace 적용 시 `teleop_launch.py`의 모든 드라이버(limo_base, ydlidar, EKF)까지 수정해야 해서 변경 범위가 과대함.
- **Date**: 2026-04-16

---

### DEC-006: Nav2 파라미터 다중 로봇 관리 방법
- **Context**: AMCL, costmap 등 Nav2 파라미터에서 TF frame ID(`base_link`, `odom`)를 로봇별로 다르게 설정해야 함. yaml을 어떻게 관리할 것인가.
- **Options**:
  - A) 로봇별 yaml 2벌 (`diff_navigation_params_robot1.yaml`, `_robot2.yaml`)
  - B) `RewrittenYaml` (Nav2 제공) — 키 이름으로 치환
  - C) Template yaml + Python `str.replace()` — 값 안의 문자열로 치환
- **Decision**: **C — Template yaml + Python str.replace()**
- **Rationale**:
  - A: 로봇 추가 시 파일도 늘어남. 수정 시 두 파일 모두 고쳐야 해 관리 부담.
  - B: `global_frame` 키가 `global_costmap`(값: `map`)과 `local_costmap`(값: `odom`) 두 곳에 존재. RewrittenYaml은 키 이름 기준으로 전체 치환하므로 `map`까지 덮어써버림.
  - C: yaml 값 안에 `ROBOT_NAME` 문자열 플레이스홀더를 삽입. Python `str.replace('ROBOT_NAME', 'robot1')`은 텍스트 전체에서 해당 문자열만 찾아 바꾸므로, `global_frame: map`은 영향 없고 `global_frame: ROBOT_NAME/odom`만 `robot1/odom`으로 치환됨. 로봇 추가 시 yaml 수정 없이 인자만 바꾸면 됨.
- **구현 위치**:
  - `wego_2d_nav/params/diff_navigation_params.yaml` — ROBOT_NAME 플레이스홀더 적용
  - `wego/launch/navigation_diff_launch.py` — OpaqueFunction 내 Python 치환 로직
- **Date**: 2026-04-16

---

### DEC-007: launch 파일에서 OpaqueFunction + tempfile 사용
- **Context**: `robot_name` 인자를 받아 yaml 내용을 치환한 뒤 Nav2에 넘겨야 함. 어떻게 동적으로 파라미터를 전달할 것인가.
- **Decision**: **OpaqueFunction + tempfile**
- **Rationale**:
  - `LaunchConfiguration`은 지연 평가(lazy evaluation) 객체라 Python f-string/str.replace 등 일반 문자열 연산 불가. `perform(context)`로 실행 시점에 실제 문자열로 변환해야 함.
  - `OpaqueFunction`은 launch 실행 시점에 `context`를 받아 Python 함수를 실행하므로, 이 시점에서 `LaunchConfiguration.perform(context)`로 실제 값 추출 가능.
  - Nav2는 파라미터를 파일 경로(`ParameterFile`)로 받음. 치환된 내용을 `tempfile`에 저장 후 그 경로를 전달.
- **Date**: 2026-04-16

---

### DEC-001: openWakeWord 커스텀 모델 필요 여부
- **Context**: "헤이 리모"는 기존 openWakeWord에 없는 커스텀 호출어. 사전 학습된 모델이 없으면 직접 학습 데이터 수집 및 파인튜닝 필요.
- **Options**:
  - A) openWakeWord 커스텀 모델 학습 ("헤이 리모" 샘플 수집 → 학습)
  - B) 기존 영어 호출어로 변경 (예: "hey robot") — 사용자 경험 저하
  - C) 호출어 없이 VAD 후 바로 STT — 오작동 가능성 증가
- **Decision**: 미결정
- **Rationale**: 학습 데이터 수집 공수, 인식률 목표치 확인 후 결정
- **Date**: 2026-04-16

---

### DEC-002: Orin Nano GPU 메모리 — YOLO + faster-whisper 동시 가동
- **Context**: Orin Nano의 GPU 메모리는 제한적. YOLO(상시)와 faster-whisper(호출 시)가 동시에 CUDA를 사용할 경우 OOM(Out of Memory) 발생 가능.
- **Options**:
  - A) 시간 분할: 호출어 감지 시 YOLO 일시 정지 → STT 완료 후 YOLO 재개
  - B) YOLO 모델 경량화 (nano 버전 사용) + faster-whisper tiny 모델 조합
  - C) STT는 CPU fallback (속도 저하 감수)
  - D) 실측 후 결정 (실제 메모리 사용량 프로파일링)
- **Decision**: 미결정 → 실측 우선
- **Rationale**: Orin Nano 실제 VRAM 공유 구조 파악 필요. 프로파일링 없이 결정 불가.
- **Date**: 2026-04-16

---

### DEC-003: wego_behaviour BT 프레임워크 선택
- **Context**: ROS 2에서 BehaviorTree.CPP v3 vs v4, 또는 py_trees 사용 가능. Nav2는 BehaviorTree.CPP 기반.
- **Options**:
  - A) BehaviorTree.CPP v4 (Nav2와 동일 프레임워크 — 연동 용이)
  - B) py_trees (Python 기반 — 프로토타이핑 빠름, 성능 낮음)
- **Decision**: BehaviorTree.CPP v4 방향 (Nav2 연동 일관성)
- **Rationale**: Nav2 BT 액션 노드를 그대로 재사용 가능. 최상단 BT도 동일 프레임워크로 통일.
- **Status**: 결정됨, 구현 전 최종 확인 필요
- **Date**: 2026-04-16

---

### DEC-004: Gemini API 폴백 전략 — 응답 지연 허용 한계
- **Context**: Gemini API는 네트워크 왕복 지연 발생. 안내 로봇 맥락에서 사용자가 기다리는 시간의 UX 한계 정의 필요.
- **Options**:
  - A) 타임아웃 3초 → Gemma-2B 폴백
  - B) 타임아웃 5초 → Gemma-2B 폴백
  - C) Gemini API 먼저 비동기 호출, 동시에 Gemma-2B도 실행 → 먼저 온 결과 사용
- **Decision**: 미결정
- **Rationale**: 실제 학원 환경 네트워크 지연 측정 후 결정
- **Date**: 2026-04-16

## Resolved

> 해결된 결정은 [docs/archive/decisions-resolved.md](../archive/decisions-resolved.md)로 이동

### DEC-016 → 최종 결론 확정 (2026-04-29)
Pending 섹션 상단에 기록. 실기기 검증으로 유리 구간 소프트웨어 완전 해결 불가 확정. 운용 정책으로 수용.
