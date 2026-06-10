# Jira 에픽 구조 (확정본)

> 목적: 프로젝트 **실행/이슈 추적**용 Jira Epic 구조. 본 파일은 작업 참조용 에픽 목록·매핑이며, 실제 이슈는 Jira에 등록한다.
> 짝 문서: 지식·설계 문서는 [CONFLUENCE-OUTLINE.md](CONFLUENCE-OUTLINE.md).

---

## Jira ↔ Confluence 역할 분리

| | Jira | Confluence |
|---|------|-----------|
| 성격 | **실행 추적** (무엇을, 언제, 누가, 상태) | **지식 정본** (왜·어떻게·결과 서사) |
| 단위 | Epic → Story → (Sub-task) | Space → Page (4단 템플릿) |
| 매핑 | Epic ≈ Confluence 3.8.x 상세문서 | 3.8.x ≈ Jira Epic |
| 채우는 법 | Story = 실제 작업/DEC 결정 1:1 | Page = ref/* + 코드 대조 |

> 한 줄 원칙: **"무엇을 했나"는 Jira Story, "왜·어떻게 했나"는 Confluence Page.** 같은 작업이 양쪽에 있되 관점이 다르다. Story 본문에서 대응 Confluence 페이지를 링크한다.

---

## 에픽 목록 (개발 흐름 순)

> 1·2는 생성 완료. 3 이후가 서브시스템 구현 → 통합 → 운영 순.

| # | Epic | 설명 | 패키지 | ↔ Confluence |
|---|------|------|--------|-------------|
| 1 | **Project Planning** | 기획·범위·일정·기술스택 선정 | — | 1. 개요 |
| 2 | **Project Designing** | 사용자/시스템 요구사항, 시스템·HW 아키텍처, 토폴로지, ERD | — | 2.x, 3.1~3.4 |
| 3 | **Environment & Communication** | ROS2 도메인 분리(5/6/7), CycloneDDS auto-discovery, Domain Bridge, 워크스페이스/기기 셋업 | `wego_bridge` | 3.7, 3.8.12 |
| 4 | **SLAM & Mapping** | Cartographer 지도 작성, 유리구간 매핑, 맵 후처리(Keepout/Denoise) | `wego` | 3.5, 3.8.1, 3.8.6 |
| 5 | **Autonomous Navigation (Nav2)** | AMCL 튜닝, planner/controller, 커스텀 BT XML, waypoints, EKF/TF, 유리구간 경유 | `wego_2d_nav` | 3.8.2~3.8.6 |
| 6 | **Mission Control / Behavior FSM** | Yasmin FSM(5상태), abort/failed/recover, 발화-주행 동기화 연동 | `wego_behaviour` | 3.8.8 |
| 7 | **Precision Home Docking** | ArUco PBVS staged 도킹, AMCL 리셋, 마커 캘리브레이션 | `wego_aruco` | 3.8.7 |
| 8 | **Human Detection & Safety Stop** | YOLOv8 사람감지 + depth 게이팅, BT PersonClearCondition, **person_leg 근거리 파인튜닝(데모 후)** | `ulsan_person_detect`, `ulsan_bt_plugins` | 3.8.10 |
| 9 | **Voice Guidance (TTS)** | edge-tts + mpg123, GuideGoal/Speak 발화-주행 동기화 | `wego_voice` | 3.8.11 |
| 10 | **Multi-Robot Coordination** | 우선순위 pause/resume 충돌회피, dispatcher 임무 배차 | `wego_traffic`, `wego_dispatcher` | 3.8.9 |
| 11 | **Reservation System & Backend** | FastAPI + MySQL 예약 CRUD, 임무 배정 API, 미션 로그, APScheduler | `ulsan_reservation` | 3.4, 3.8.13 |
| 12 | **Visitor UI** | 웹 예약 UI, 태블릿 방문자 UI(현장방문/안내) | `ulsan-web-ui`, `ulsan-visitor-ui` | 2.1, 3.8.13 |
| 13 | **Control & Monitoring GUI** | PyQt 관제 대시보드 — 지도·로봇카드·긴급제어·로그·진단 | `ulsan_gui` | 3.6 |
| 14 | **Real-Robot Testing** | 단일/2대 통합 실기기 검증, end-to-end 시나리오, 데모 | (전체) | 4.1, 4.2 |
| 15 | **Documentation** | Confluence 종합기록 작성(진행 중), 회고·향후과제 | docs_hub | 5.1, 5.2 |

---

## 스토리 작성 원칙

- **Story = 실제 작업/결정 단위.** DECISION-LOG(archive 포함)의 DEC 항목과 PROJECT-STATUS 체크리스트가 곧 Story 후보다. 예) "DEC-022 우선순위 충돌회피 채택" → Epic #10의 Story.
- **실기기 검증은 #14(Real-Robot Testing)에 모은다.** 우리 프로젝트의 성격(구현→실로봇 검증 반복)을 한 에픽에 부각. 단 구현 자체는 각 서브시스템 에픽에 둔다.
- Story 본문에 **대응 Confluence 3.8.x 페이지를 링크** → "무엇(Jira)"에서 "왜·어떻게(Confluence)"로 한 번에 이동.
- 폐기 결정(PeerObstacleLayer, STT/NLU 등)도 Story로 남겨 **"왜 버렸나"**를 추적 → 면접 어필 포인트.
