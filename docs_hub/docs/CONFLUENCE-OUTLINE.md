# Confluence 정리 목차 (확정본)

> 목적: 프로젝트 **종합 기록**용 Confluence Space 구조. 본 파일은 작업 참조용 목차·매핑이며, 실제 본문은 각 Confluence 페이지에 작성한다.
> 범례: 🖼 = 완성품 스크린샷 소개 페이지 / 🔧 = 4단 템플릿 기술 서사 페이지

---

## 작업 방식

- **한 번에 다 하지 않고 페이지 단위로 하나씩** 진행한다(여러 세션에 걸쳐).
- 각 페이지 작성 시점에 **그 페이지에 필요한 다이어그램(토폴로지/시퀀스/상태도/ERD 등)을 그 자리에서 함께 그린다.** 다이어그램은 Confluence Mermaid/PlantUML 또는 draw.io로 작성.
- 본문 원본은 `docs/ref/*` 와 소스코드. 작성 전 해당 원본을 코드와 대조(문서-구현 일치 확인은 2026-06-06 1차 완료).

### 설계 단계 흐름 (2026-06-14 정리)

문서는 **설계 단계 = 요구사항 → 아키텍처(정적 구조) → 동작 설계(동적 행위)** 순으로 읽히도록 구성한다(2·3·4장). 4장은 **DFD · 시퀀스 · 상태도**로 시스템 동작을 표현한다(시나리오 서술 페이지는 폐지). 그 뒤 5장 **상세 구현**이 "어떻게 만들었나"를 4단 템플릿으로 받친다.

> 단, 본 프로젝트의 시퀀스·상태도는 사전 설계 산출물이 아니라 **이미 구현·검증된 시스템을 반영한 동작 흐름**이다(reverse-documentation). 그래서 추정이 아니라 실제 코드(토픽/서비스/FSM)와 1:1로 일치한다 — 각 시퀀스·상태도 페이지 머리말에 "실제 구현 반영"임을 명시.

## 진행 현황 (페이지별)

> 상태: ⬜ 미작성 / 🟡 작성 중 / ✅ 완료

| 페이지 | 상태 |
|---|---|
| 1. 프로젝트 개요 | 🟡 본문 확정(2026-06-11, ~/limo/1-프로젝트-개요.txt) — Confluence 등록만 남음 |
| 2.1 사용자 요구사항 | 🟡 본문 확정(2026-06-11, ~/limo/2.1-사용자-요구사항.txt) — Confluence 등록만 남음 |
| 2.2 시스템 요구사항 | 🟡 본문 확정(2026-06-11, ~/limo/2.2-시스템-요구사항.txt) — Confluence 등록만 남음 |
| 3.1 시스템 아키텍처 | 🟡 사용자 구상 → draw.io 작도 예정 |
| 3.2 노드·토픽 토폴로지 | ⬜ |
| 3.3 DB 테이블 & 관계 (ERD) | ⬜ (본문 초안 대화에 있음) |
| 3.4 Map 구성 및 소개 🖼 | ⬜ (스크린샷 필요) |
| 3.5 방문자 UI 소개 🖼 | ⬜ (스크린샷 필요) |
| 3.6 예약 UI 소개 🖼 | ⬜ (스크린샷 필요) |
| 3.7 관제 GUI 소개 🖼 | ⬜ (스크린샷 필요) |
| 3.8 개발환경 & 기술스택 (HW 스펙 포함) | ⬜ |
| 4.1 로봇 기능 (데이터 흐름도, DFD) | ⬜ |
| 4.2 시퀀스 다이어그램 (4개) | ⬜ |
| 4.3 상태 다이어그램 (미션 FSM) | ⬜ (본문 초안 대화에 있음) |
| 5.1~5.13 상세구현 | ⬜ (13개) |
| 6.1 향후 과제 & 회고 | ⬜ |
| 6.2 패키지 레퍼런스 | ⬜ |

---

## 상세구현(5장) 작성 템플릿 — 4단 구성

모든 `5.x` 페이지는 동일한 4단으로 작성한다(일관성 + 면접 설명 최적화):

1. **왜 개발했나** — 요구·문제 정의 + **그 기술/설계를 택한 의사결정 근거(왜 이걸 선택했나)**
2. **어떻게 개발했나** — 설계·구현 상세
3. **문제 상황과 해결** — 개발 중 마주친 문제와 트러블슈팅(이런 문제가 있어 이렇게 해결)
4. **결과·파라미터** — 검증값·확정 파라미터

> 의사결정 기록(왜)·트러블슈팅(문제해결)은 별도 섹션을 두지 않고 **각 상세문서의 ①·③에 통합**한다.

---

## 목차 트리

```
1. 프로젝트 개요

2. 요구사항
   2.1 사용자 요구사항
   2.2 시스템 요구사항

3. 아키텍처 (정적 구조 — 무엇으로 구성되고 어떻게 연결되나)
   3.1 시스템 아키텍처            기기·도메인(5/6/7) 큰 그림 + 데이터 흐름
   3.2 노드·토픽 토폴로지         전체 ROS 노드/토픽 구성도
   3.3 DB 테이블 & 관계 (ERD)
   3.4 Map 구성 및 소개       🖼
   3.5 방문자 UI 소개         🖼
   3.6 예약 UI 소개           🖼
   3.7 관제 GUI 소개          🖼
   3.8 개발환경 & 기술스택        스택 표(버전) 정본 + HW 스펙 표 + 설치·빌드·실행
                              (HW 아키텍처 독립 페이지 폐지 → 스펙 표를 이 페이지에 흡수)

4. 동작 설계 (동적 행위 — 시스템이 어떻게 움직이나)   ← 설계의 마무리(구조를 행동으로)
   4.1 로봇 기능 (데이터 흐름도, DFD)   기능을 데이터 흐름으로(센서→인지→판단→구동, 예약→배정→안내)
   4.2 시퀀스 다이어그램 (4개)          ① 임무생성 ② 작업스케줄링 ③ 안내임무수행 ④ 로봇주행 (실제 구현 반영)
   4.3 상태 다이어그램 (미션 FSM)       IDLE/GUIDING/RETURNING/WAITING/FAILED

5. 상세 구현 (세부 구현사항)        🔧 4단 템플릿
   5.1  Localization & SLAM
   5.2  AMCL 위치추정 & 튜닝
   5.3  센서 퓨전 (EKF)
   5.4  TF 프레임 구조
   5.5  Navigation (Nav2 + 커스텀 BT)
   5.6  유리구간 phantom 문제해결
   5.7  ArUco PBVS 홈 도킹          (+ staged 3단계 상태도)
   5.8  미션 제어 FSM (실패처리·복구)  (상태 전이도는 4.3)
   5.9  멀티로봇 충돌회피
   5.10 사람 감지 정지 (Perception)
   5.11 음성 안내 (TTS)
   5.12 통신 (DDS / Domain Bridge)   ← 도메인 분리(5/6/7) + 도메인 브릿지 다이어그램
   5.13 예약 시스템 & 임무배정         (+ 임무 status 상태도)

6. 기타
   6.1 향후 과제 & 회고
   6.2 패키지 레퍼런스
```

---

## 시퀀스 다이어그램 4종 (4.2) — 2026-06-14 확정

시나리오(서술) 페이지는 **폐지**하고, 동작은 **시퀀스 다이어그램으로 직접** 표현한다.
4개는 추상화 레벨이 단계적으로 좁아지는 **zoom-in 구조** — 앞 시퀀스의 한 단계를 뒤 시퀀스가 확대한다.

| # | 시퀀스 | 범위 | 핸드오프 / 확대 |
|---|--------|------|----------------|
| ① 안내 임무 생성 | 방문자 UI(안내버튼) → FastAPI → `missions` PENDING **생성까지** | → ② |
| ② 작업 스케줄링 | (PENDING 이후) dispatcher 폴링 → 가용 로봇 선정 → **로봇에 작업 지시(GuideGoal)하고 끝** | ② "로봇 지시" ⇄ ③ "로봇 수신" |
| ③ 안내 임무 수행 | **로봇이 작업 지시 받은 시점부터** → 안내 수행(출발멘트→주행→도착→복귀→도킹→IDLE) → **임무 시작/종료 DB 반영** | ③ "주행" ──확대──▶ ④ |
| ④ 로봇 주행 | Nav2 경로계획·주행·(장애물/복구)·도착 — ③의 "주행" 단계 상세 | — |

> **③의 "임무 시작/종료 DB 반영" 표기 선택**: 실제 코드상 `PATCH /start`는 dispatcher가 GuideGoal 발행 직후(② 끝자락), `PATCH /complete`는 로봇 IDLE 복귀 시(③ 끝). 그릴 때 (A) ③에 start·complete 둘 다 묶기(가독성) / (B) start는 ②·complete는 ③(코드 시점 충실) 중 택.
> **PBVS 도킹 내부 3단계 상세**는 ④가 아니라 **5.7 상태도/시퀀스**에 둔다(시퀀스에선 `/aruco_home_dock` 요청→성공 한 줄).

---

## 페이지별 내용 + 원본 매핑

| 페이지 | 성격 | 내용 | 원본 |
|---|---|---|---|
| 1. 프로젝트 개요 | — | 한 줄 요약·배경·목적·데모 시나리오·기술스택·진행상태 | CLAUDE.md, PROJECT-STATUS |
| 2.1 사용자 요구사항 | — | 방문자/관리자 관점 "무엇을 할 수 있어야 하나" | UI-ARCHITECTURE, 신규 |
| 2.2 시스템 요구사항 | — | 기능(자율주행·멀티로봇·사람감지·음성·예약·관제) + 비기능 | 종합 |
| 3.1 시스템 아키텍처 | — | 도메인 5/6/7 역할분담, 데이터 흐름 (로봇 2대 ↔ 중앙 서버 협업 서비스) | ARCHITECTURE |
| 3.2 노드·토픽 토폴로지 | — | 전체 ROS 노드/토픽/타입/발행·구독 그래프 | NODE-TOPOLOGY |
| 3.3 DB 테이블 & 관계 | — | reservations / missions / logs 3테이블 + ERD (로봇 status는 in-memory, DB 아님) | models.py |
| 3.4 Map 구성 및 소개 | 🖼 | 완성 맵 스크린샷 + 짧은 소개 | NAVIGATION |
| 3.5 방문자 UI 소개 | 🖼 | 방문자 태블릿 UI 화면 + 캡션 | UI-ARCHITECTURE |
| 3.6 예약 UI 소개 | 🖼 | 웹 예약 UI 화면 + 캡션 | UI-ARCHITECTURE |
| 3.7 관제 GUI 소개 | 🖼 | ulsan_gui 실행 화면 + 캡션 | UI-ARCHITECTURE |
| 3.8 개발환경 & 기술스택 | — | **기술스택 표(버전, 정본)** + **HW 스펙 표**(LIMO·Orin Nano·YDLIDAR T-mini Plus·Orbbec Dabai DCW·스피커·Wi-Fi) + ROS2 Humble·DDS·빌드·apt·워크스페이스 규칙·실행명령 | PROJECT-STATUS, COMMUNICATION, CLAUDE.md, ARCHITECTURE |
| 4.1 로봇 기능 (데이터 흐름도) | — | 기능을 데이터 흐름으로 표현(센서→인지→판단→구동, 예약→배정→안내) | NODE-TOPOLOGY, ARCHITECTURE |
| 4.2 시퀀스 다이어그램 (4개) | — | ① 안내임무생성 ② 작업스케줄링 ③ 안내임무수행 ④ 로봇주행 (zoom-in 구조) | 종합 |
| 4.3 상태 다이어그램 (미션 FSM) | — | IDLE/GUIDING/RETURNING/WAITING/FAILED 전이 + 트리거(outcome) | 코드(states.py) |
| 5.1 Localization & SLAM | 🔧 | Cartographer 채택, SLAM Toolbox 비교는 설계만(ROI로 미실행) | NAVIGATION |
| 5.2 AMCL 튜닝 | 🔧 | do_beamskip, update_min 조정. **①왜: 긴 복도 특징점 부족 → Y좌표(횡방향) 오차·누적오차 → 보완책 = 마커 도킹 리셋(5.7) + Spin 선실행(DEC-037). Spin 발단: 도킹이 마커 정면 자세라 출발은 180° 회전 필수인데, 복도에서 회전 중 AMCL 오업데이트 → 엉뚱한 위치 기준 재계획·출발 실패 → 주행 전 명시적 Spin(회전 해결 + 파티클 수렴 부수효과)** | NAVIGATION |
| 5.3 센서 퓨전 (EKF) | 🔧 | robot_localization 휠odom+IMU 융합 | NODE-TOPOLOGY, 코드 |
| 5.4 TF 프레임 구조 | 🔧 | map→odom→base_link 분리(REP-105) | NODE-TOPOLOGY |
| 5.5 Navigation | 🔧 | navigate_through_poses + RemovePassedGoals + 커스텀 BT | NAVIGATION |
| 5.6 유리 phantom | 🔧 | costmap 진단 → Keepout+Denoise → 경로제외 | NAVIGATION |
| 5.7 ArUco PBVS | 🔧 | 비홀로노믹 과소구동 → staged 3단계 + AMCL 리셋 + **staged 상태도(조준→직진→정렬)**. **①왜: 단순 정밀주차가 아니라 복도발 AMCL Y오차·누적오차를 임무마다 초기화하는 구조적 보완(매 임무=리셋 1회). 단안 solvePnP(깊이토픽 미사용 — 마커 크기 기지라 yaw까지 한 번에). ③파생문제: 마커 정면 도킹 자세 → 출발 180° 회전 필요 → Spin 선실행으로 해결(5.2 메모·DEC-037)** | ARUCO-LOCALIZER |
| 5.8 미션 FSM | 🔧 | 5상태 + 실패통합·관리자 복구(DEC-044). 상태 전이도 정본은 4.3 | ARCHITECTURE, 코드 |
| 5.9 멀티로봇 충돌회피 | 🔧 | PeerObstacleLayer 한계 → 우선순위 pause/resume | FLEET-COLLISION |
| 5.10 사람감지 정지 | 🔧 | YOLOv8+Depth 게이팅 → behaviour 게이트 → WAITING → BT MotionHoldCondition halt (DEC-050) | NODE-TOPOLOGY |
| 5.11 음성 TTS | 🔧 | STT/NLU 폐기(예약DB) → TTS 전용 | VOICE-PIPELINE |
| 5.12 통신 | 🔧 | Wi-Fi 대용량토픽 → /map 로컬발행 + 도메인분리(5/6/7) + 도메인브릿지 | COMMUNICATION |
| 5.13 예약 시스템 | 🔧 | rosbridge 제거 → dispatcher 폴링배정, walk-in DB + **임무 status 상태도(PENDING→ACTIVE→COMPLETED)** | UI-ARCHITECTURE |
| 6.1 향후 과제 & 회고 | — | Phase 4 미구현·한계·개선점(대기열 자동배정 등) | PROJECT-STATUS Phase4 |
| 6.2 패키지 레퍼런스 | — | 13개 패키지 한눈 표 | CLAUDE.md, NODE-TOPOLOGY |

---

## 다이어그램 계획 (각 페이지 작성 시 그림)

| 다이어그램 | 종류 | 들어갈 페이지 | 초안 |
|---|---|---|---|
| 시스템 아키텍처 구성도 (로봇 2대 ↔ 중앙 서버) | draw.io | 3.1 | 🟡 사용자 구상 (작도 예정) |
| 노드·토픽 토폴로지 구성도 | Mermaid flowchart | 3.2 | 예정 |
| DB ERD (reservations/missions/logs) | Mermaid / draw.io | 3.3 | ✅ 초안(대화) |
| 로봇 기능 데이터 흐름도 (센서→인지→판단→구동, 예약→배정→안내) | Mermaid flowchart | 4.1 | 예정 |
| ① 안내 임무 생성 | Mermaid sequence | 4.2 | 예정 |
| ② 작업 스케줄링 | Mermaid sequence | 4.2 | 예정 |
| ③ 안내 임무 수행 | Mermaid sequence | 4.2 | 예정 |
| ④ 로봇 주행 | Mermaid sequence | 4.2 | 예정 |
| 미션 FSM 상태 전이도 (IDLE/GUIDING/RETURNING/WAITING/FAILED) | Mermaid stateDiagram | 4.3 | ✅ 초안(대화) |
| TF 트리 (map→odom→base_link→센서) | Mermaid flowchart | 5.4 | 예정 |
| PBVS 도킹 staged 3단계 상태도 (조준→직진→정렬) | Mermaid stateDiagram | 5.7 | ✅ 초안(대화) |
| 임무 status lifecycle 상태도 (PENDING→ACTIVE→COMPLETED) | Mermaid stateDiagram | 5.13 | 예정 |
| 도메인 분리(5/6/7) + 브릿지 토픽 방향도 | Mermaid flowchart | 5.12 | 예정 |

> "✅ 초안(대화)"는 이전 세션에서 Mermaid 초안을 그려둔 것. 해당 페이지 작성 시 다듬어 확정.
> **시각화 자료(시퀀스 4종 + 로봇기능 DFD + 상태도 3종[미션 FSM·도킹 staged·임무 status] + 토폴로지/ERD/TF/도메인브릿지)는 Confluence 보관 후 취업 포트폴리오에 재사용한다.**

---

## 작업 순서 제안 (열려 있음)

1. 1. 프로젝트 개요 → 2. 요구사항 (문서 골격부터)
2. 3. 아키텍처 (3.1 시스템 아키텍처·3.2 토폴로지·3.3 ERD 다이어그램 포함)
3. 4. 동작 설계 (4.1 DFD + 4.2 시퀀스 4개 + 4.3 미션 FSM 상태도)
4. 5. 상세구현 13개 (면접 핵심: 5.7 ArUco · 5.6 phantom · 5.1 Localization 우선 추천)
5. 6. 기타

> 순서는 고정 아님. 원하는 페이지부터 진행 가능.
