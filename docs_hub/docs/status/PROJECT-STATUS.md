# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**Phase 3 — 아키텍처 재설계 (2026-05-11)**
연산 오프로딩(DEC-021), 충돌 회피 재설계(DEC-022), 예약 기반 안내 시스템 도입(DEC-023), NLU 방식 변경(DEC-024) 확정. 기존 구현 일부 재작성 필요.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 시스템 아키텍처 설계 | **재설계** | — (DEC-021~024) |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **재설계** | wego_bridge |
| SLAM 지도 작성 | **완료** | wego |
| Nav2 경로 계획 & AMCL | **완료** | wego_2d_nav |
| Fleet 충돌 회피 (우선순위 기반 pause/resume) | **재설계** | wego_traffic + wego_behaviour |
| waypoints.yaml 목적지 좌표 작성 | **완료** | wego_behaviour/config |
| 행동 트리 최상단 관리 (FSM — WAITING 상태 추가) | **재설계** | wego_behaviour |
| ArUco 마커 홈 정차 보정 | **완료** | wego_aruco |
| 음성 파이프라인 (TTS 안내 멘트) | **구현 중** | wego_voice (TTS only — DEC-024) |
| 예약 웹 서비스 | planned | 신규 (웹 서비스) |
| LIMO 터치 UI | planned | wego_touch_ui (신규) |
| 멀티로봇 코디네이터 (충돌 회피 pause/resume) | planned | wego_traffic (신규) |
| 관제 UI (관리자 대시보드) | planned | wego_ui (재구현) |

---

## Execution Checklist

### 완료 — 환경 기반 구축
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
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
- [ ] Nav2 BT 커스텀 노드: `VoiceTriggerCondition`, `PeerRobotBusyCondition` (C++)

#### 음성 파이프라인
- [ ] `wego_voice` 패키지: TTS 안내 멘트 출력 (edge-tts, DEC-024)
  - 체크인 완료 시 "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다." 발화
  - `/speak_text` 구독 → TTS 출력 (wego_touch_ui 또는 wego_behaviour에서 발행)
- [ ] wego_voice → FSM 연결 확인 (`/goal_destination` 발행 흐름)

> STT/Wake-up/NLU/LLM 기반 자유 대화 안내는 추후 개발 사항 — VOICE-PIPELINE.md 참고

#### 멀티로봇 코디네이터
- [ ] `wego_traffic` 패키지 (노트북 전용): robot_status 구독 → on_duty 결정 — DEC-015
- [ ] `/limo_N/robot_status` 구독 + `/limo_N/on_duty` 발행
- [ ] wego_behaviour FSM과 on_duty 연동 확인

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
- [ ] markers.yaml ID 0, ID 1 map 좌표 재측정 — 마커 위치 변경으로 전체 재측정 필요
- [ ] **passive corrector 실기기 재검증** — 새 아키텍처(서버 노트북 Nav2) 기준으로 재검증 필요
- [ ] Orbbec 카메라 프로파일 고정 — done (2026-05-07) teleop_launch.py에 depth_height=400 명시

#### 데모용 관제 UI
- [ ] `wego_ui` Qt 기반 재구현 (현재는 임시 RViz 테스트용)
  - 지도 + 두 로봇 실시간 위치 마커
  - 각 로봇 상태 (IDLE / BUSY / RETURNING) 표시
  - on_duty 로봇 하이라이트
  - 목적지 선택 / 수동 명령 패널

#### 전체 통합 테스트
- [ ] LIMO 2대 + 노트북 전체 파이프라인 실기기 검증
  - 웨이크워드 → STT → NLU → FSM → navigate_to_pose → ArUco 보정 → TTS
  - on_duty 전환 (LIMO 1 BUSY 시 LIMO 2 응대)

---

### Phase 4 — 완성도
- [ ] 초음파 센서 → local costmap range_sensor_layer 연동 (유리문 닫힘 감지 + 음성 대기) — 유리문 닫힘 시 경로 생성 불가 → TTS "유리문을 열어주세요" + WAIT 상태
- [ ] YOLO 사람 감지 → 방향 회전 + 안내 멘트
- [ ] NLU 백업: Gemma-2B (Ollama) 로컬 폴백
- [ ] 목적지 도달 후 "추가 용무 확인" 대화 흐름
- [ ] GPU 메모리 프로파일링 (YOLO + faster-whisper 동시 가동)
- [ ] 다국어 안내 검토
- [ ] **유리 구간 주행 버벅임 개선** — Keepout+DenoiseLayer 적용 후에도 간헐적 버벅임 잔존. 추가 해결책 탐색 (local costmap phantom 근본 억제 또는 경로 설계 개선)
- [ ] **2대 충돌 회피 완성도 개선** — 운용 중 간헐적 충돌 발생. 유추 원인: ① 네트워크 지연으로 상대 위치 업데이트 늦음 ② 양 로봇이 대칭으로 같은 방향 회피 → 교착. 정확한 원인 실기기 진단 후 해결

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

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Orin Nano GPU 메모리: YOLO + faster-whisper 동시 가동 시 OOM 가능성 | High | P2에서 프로파일링 예정 |
| openWakeWord "헤이 리모" 커스텀 모델 학습 필요 여부 | Medium | 미결정 |
| 두 로봇이 동시에 호출될 때 충돌 시나리오 | Medium | DEC-017: wego_voice에서 on_duty 게이팅으로 해결 예정 |
| Gemini API 응답 지연이 대화 흐름에 미치는 영향 | Low | 모니터링 |
