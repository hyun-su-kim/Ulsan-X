# Confluence 정리 목차 (확정본)

> 목적: 프로젝트 **종합 기록**용 Confluence Space 구조. 본 파일은 작업 참조용 목차·매핑이며, 실제 본문은 각 Confluence 페이지에 작성한다.
> 범례: 🖼 = 완성품 스크린샷 소개 페이지 / 🔧 = 4단 템플릿 기술 서사 페이지

---

## 작업 방식

- **한 번에 다 하지 않고 페이지 단위로 하나씩** 진행한다(여러 세션에 걸쳐).
- 각 페이지 작성 시점에 **그 페이지에 필요한 다이어그램(토폴로지/시퀀스/상태도/ERD 등)을 그 자리에서 함께 그린다.** 다이어그램은 Confluence Mermaid/PlantUML로 작성.
- 본문 원본은 `docs/ref/*` 와 소스코드. 작성 전 해당 원본을 코드와 대조(문서-구현 일치 확인은 2026-06-06 1차 완료).

## 진행 현황 (페이지별)

> 상태: ⬜ 미작성 / 🟡 작성 중 / ✅ 완료

| 페이지 | 상태 |
|---|---|
| 1. 프로젝트 개요 | ⬜ |
| 2.1 사용자 요구사항 | ⬜ |
| 2.2 시스템 요구사항 | ⬜ |
| 3.1 시스템 아키텍처 | ⬜ |
| 3.2 하드웨어 아키텍처 | ⬜ |
| 3.3 노드·토픽 토폴로지 | ⬜ |
| 3.4 DB 스키마 (ERD) | ⬜ (본문 초안 대화에 있음) |
| 3.5 MAP 구성 🖼 | ⬜ (스크린샷 필요) |
| 3.6 관제 GUI 🖼 | ⬜ (스크린샷 필요) |
| 3.7 개발환경 | ⬜ |
| 3.8.1~3.8.13 상세문서 | ⬜ (13개) |
| 4.1 로봇 기능 리스트 | ⬜ |
| 4.2 시퀀스 다이어그램 | ⬜ (초안 6종 대화에 있음) |
| 5.1 향후 과제 & 회고 | ⬜ |
| 5.2 패키지 레퍼런스 | ⬜ |

---

## 상세문서(3.8) 작성 템플릿 — 4단 구성

모든 `3.8.x` 페이지는 동일한 4단으로 작성한다(일관성 + 면접 설명 최적화):

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

3. 시스템 설계
   3.1 시스템 아키텍처            기기·도메인(5/6/7) 큰 그림
   3.2 하드웨어 아키텍처
   3.3 노드·토픽 토폴로지         전체 ROS 노드/토픽 구성도
   3.4 DB 스키마 (ERD)
   3.5 MAP 구성              🖼
   3.6 관제 GUI              🖼
   3.7 개발환경
   3.8 상세문서 (세부 구현사항)   🔧 4단 템플릿
        3.8.1  Localization & SLAM
        3.8.2  AMCL 위치추정 & 튜닝
        3.8.3  센서 퓨전 (EKF)
        3.8.4  TF 프레임 구조
        3.8.5  Navigation (Nav2 + 커스텀 BT)
        3.8.6  유리구간 phantom 문제해결
        3.8.7  ArUco PBVS 홈 도킹
        3.8.8  미션 제어 FSM (실패처리·복구)
        3.8.9  멀티로봇 충돌회피
        3.8.10 사람 감지 정지 (Perception)
        3.8.11 음성 안내 (TTS)
        3.8.12 통신 (DDS / Domain Bridge)   ← 도메인 분리(5/6/7) + 도메인 브릿지 다이어그램
        3.8.13 예약 시스템 & 임무배정

4. 시연 시나리오
   4.1 로봇 기능 리스트
   4.2 시퀀스 다이어그램          예약안내 / 현장방문 / 실패-복구 / 충돌회피 (Mermaid/PlantUML)

5. 기타
   5.1 향후 과제 & 회고
   5.2 패키지 레퍼런스
```

---

## 페이지별 내용 + 원본 매핑

| 페이지 | 성격 | 내용 | 원본 |
|---|---|---|---|
| 1. 프로젝트 개요 | — | 한 줄 요약·배경·목적·데모 시나리오·기술스택·진행상태 | CLAUDE.md, PROJECT-STATUS |
| 2.1 사용자 요구사항 | — | 방문자/관리자 관점 "무엇을 할 수 있어야 하나" | UI-ARCHITECTURE, 신규 |
| 2.2 시스템 요구사항 | — | 기능(자율주행·멀티로봇·사람감지·음성·예약·관제) + 비기능 | 종합 |
| 3.1 시스템 아키텍처 | — | 도메인 5/6/7 역할분담, 데이터 흐름 | ARCHITECTURE |
| 3.2 하드웨어 아키텍처 | — | LIMO·Orin·YDLidar·Orbbec·스피커·Wi-Fi | ARCHITECTURE |
| 3.3 노드·토픽 토폴로지 | — | 전체 ROS 노드/토픽/타입/발행·구독 그래프 | NODE-TOPOLOGY |
| 3.4 DB 스키마 | — | reservations / missions / logs 3테이블 + ERD | models.py |
| 3.5 MAP 구성 | 🖼 | 완성 맵 스크린샷 + 짧은 소개 | NAVIGATION |
| 3.6 관제 GUI | 🖼 | ulsan_gui 실행 화면 스크린샷 + 캡션 | UI-ARCHITECTURE |
| 3.7 개발환경 | — | ROS2 Humble·DDS·빌드·apt 설치·워크스페이스 규칙·실행명령 | PROJECT-STATUS, COMMUNICATION |
| 3.8.1 Localization & SLAM | 🔧 | Cartographer 채택, SLAM Toolbox 비교는 설계만(ROI로 미실행) | NAVIGATION |
| 3.8.2 AMCL 튜닝 | 🔧 | do_beamskip, update_min 조정 | NAVIGATION |
| 3.8.3 센서 퓨전 (EKF) | 🔧 | robot_localization 휠odom+IMU 융합 | NODE-TOPOLOGY, 코드 |
| 3.8.4 TF 프레임 구조 | 🔧 | map→odom→base_link 분리(REP-105) | NODE-TOPOLOGY |
| 3.8.5 Navigation | 🔧 | navigate_through_poses + RemovePassedGoals + 커스텀 BT | NAVIGATION |
| 3.8.6 유리 phantom | 🔧 | costmap 진단 → Keepout+Denoise → 경로제외 | NAVIGATION |
| 3.8.7 ArUco PBVS | 🔧 | 비홀로노믹 과소구동 → staged 3단계 + AMCL 리셋 | ARUCO-LOCALIZER |
| 3.8.8 미션 FSM | 🔧 | 5상태 + 실패통합·관리자 복구(DEC-044) | ARCHITECTURE, 코드 |
| 3.8.9 멀티로봇 충돌회피 | 🔧 | PeerObstacleLayer 한계 → 우선순위 pause/resume | FLEET-COLLISION |
| 3.8.10 사람감지 정지 | 🔧 | YOLOv8+Depth 게이팅 → BT PersonClearCondition | NODE-TOPOLOGY |
| 3.8.11 음성 TTS | 🔧 | STT/NLU 폐기(예약DB) → TTS 전용 | VOICE-PIPELINE |
| 3.8.12 통신 | 🔧 | Wi-Fi 대용량토픽 → /map 로컬발행 + 도메인분리(5/6/7) + 도메인브릿지 | COMMUNICATION |
| 3.8.13 예약 시스템 | 🔧 | rosbridge 제거 → dispatcher 폴링배정, walk-in DB | UI-ARCHITECTURE |
| 4.1 로봇 기능 리스트 | — | 로봇이 제공하는 기능 목록 | 종합 |
| 4.2 시퀀스 다이어그램 | — | end-to-end 플로우(예약/현장/실패복구/충돌) | 종합 |
| 5.1 향후 과제 & 회고 | — | Phase 4 미구현·한계·개선점(대기열 자동배정 등) | PROJECT-STATUS Phase4 |
| 5.2 패키지 레퍼런스 | — | 13개 패키지 한눈 표 | CLAUDE.md, NODE-TOPOLOGY |

---

## 다이어그램 계획 (각 페이지 작성 시 그림)

| 다이어그램 | 종류 | 들어갈 페이지 | 초안 |
|---|---|---|---|
| 노드·토픽 토폴로지 구성도 | Mermaid flowchart | 3.3 | 예정 |
| DB ERD | (텍스트/Mermaid) | 3.4 | ✅ 초안(대화) |
| TF 트리 (map→odom→base_link→센서) | Mermaid flowchart | 3.8.4 | 예정 |
| FSM 상태 전이도 (IDLE/GUIDING/RETURNING/WAITING/FAILED) | Mermaid stateDiagram | 3.8.8 | ✅ 초안(대화) |
| 도메인 분리(5/6/7) + 브릿지 토픽 방향도 | Mermaid flowchart | 3.8.12 | 예정 |
| ① 전체 흐름 (예약/현장방문/강의실/만차 alt) | Mermaid sequence | 4.2 | ✅ 초안(대화) |
| ② 실패→관리자 복구 (DEC-044) | Mermaid sequence | 4.2 | ✅ 초안(대화) |
| ③ 멀티로봇 충돌회피 (pause/resume) | Mermaid sequence | 4.2 | ✅ 초안(대화) |
| ④ ArUco PBVS 홈 도킹 | Mermaid sequence | 4.2 | ✅ 초안(대화) |
| ⑤ 사람 감지 정지/재개 | Mermaid sequence | 4.2 | ✅ 초안(대화) |
| ⑥ 긴급 제어 (관리자 pause/resume/abort) | Mermaid sequence | 4.2 | 예정 |

> "✅ 초안(대화)"는 2026-06-06 세션에서 Mermaid 초안을 그려둔 것. 해당 페이지 작성 시 다듬어 확정.

---

## 작업 순서 제안 (열려 있음)

1. 1. 프로젝트 개요 → 2. 요구사항 (문서 골격부터)
2. 3.1~3.7 시스템 설계 (3.3 토폴로지·3.4 ERD 다이어그램 포함)
3. 3.8 상세문서 13개 (면접 핵심: 3.8.7 ArUco · 3.8.6 phantom · 3.8.1 Localization 우선 추천)
4. 4. 시연 시나리오 (시퀀스 6종 확정)
5. 5. 기타

> 순서는 고정 아님. 원하는 페이지부터 진행 가능.
