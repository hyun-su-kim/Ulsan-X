# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**환경 구성 진행 중**
Domain Bridge 실기기 통신 검증 완료 (2026-04-22). LIMO 1 ↔ 노트북 간 `/limo_1/amcl_pose` 수신 확인.
다음 단계: SLAM 지도 작성 → FleetObstacleLayer 구현.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 트랙 | 상태 | 담당 패키지 |
| 시스템 아키텍처 설계 | **완료** | — |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **완료** | wego_bridge |
| SLAM 지도 작성 | planned | wego (cartographer) |
| Nav2 경로 계획 & AMCL | planned | wego_2d_nav |
| Fleet 충돌 회피 (PeerObstacleLayer) | planned | ulsan_obstacle_layer |
| 음성 파이프라인 (VAD→Wake→STT→NLU→TTS) | planned | wego_voice (신규) |
| 행동 트리 최상단 관리 | planned | wego_behaviour (신규) |
| 관제 UI | not started | wego_ui (신규, 노트북 전용) |

---

## Execution Checklist

### P0 — 환경 기반 구축 (Immediate)
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
- [x] DOMAIN_ID 확정 — done (2026-04-16): 노트북=5, LIMO 1=6, LIMO 2=7
- [x] cyclonedds_peers.xml 실제 IP 입력 — done (2026-04-22): LIMO1=192.168.0.100, LIMO2=192.168.0.101, 노트북1=192.168.0.115, 노트북2=192.168.0.116
- [x] 멀티로봇 통신 설계 확정 — done (2026-04-21): DEC-011, DEC-012
  - **amcl_pose 공유 방식** 채택 (TF frame prefix 방식 폐기)
  - **맵 파일 사전 배포** 방식 채택 (domain bridge로 /map 스트리밍 방식 폐기)
  - 각 기기가 로컬 map_server로 /map 발행, domain bridge는 amcl_pose만 전달
- [x] `wego_bridge` 패키지 구현 완료 — done (2026-04-22): TS-002, TS-003 수정 포함
  - `config/domain_bridge_robot.yaml`: ROBOT_DOMAIN, DEST_DOMAIN, ROBOT_NAME 플레이스홀더 템플릿 (맵 형식)
  - `launch/robot_bridge_launch.py`: OpaqueFunction → bridge 인스턴스 2개 생성 (laptop/peer)
  - 동작: `/amcl_pose` (domain N) → `/limo_1(2)/amcl_pose` (domain 5, domain PEER) 동시 브릿징
- [x] 실기기 Domain Bridge 통신 검증 — done (2026-04-22)
  - LIMO 1(domain 6) → 노트북(domain 5): `/limo_1/amcl_pose` 수신 확인
  - TS-002, TS-003 발생 및 해결 (COMMUNICATION.md 참고)
- [ ] Cartographer SLAM으로 학원 지도 작성 (LIMO 1 기준)
- [ ] 맵 파일(`map.pgm`, `map.yaml`) scp로 LIMO 2 및 노트북에 배포
  ```bash
  scp map.pgm map.yaml wego@192.168.0.101:~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/
  scp map.pgm map.yaml user@192.168.0.115:~/maps/
  scp map.pgm map.yaml user@192.168.0.116:~/maps/
  ```
- [ ] 노트북에서 맵 + 두 로봇 위치 마커 확인

### P1 — 핵심 기능 구현 (Core)
- [ ] `ulsan_obstacle_layer` 패키지: PeerObstacleLayer 빌드 및 실기기 검증
  - `/limo_1/amcl_pose` 또는 `/limo_2/amcl_pose` 구독 (ROS_DOMAIN_ID로 자동 결정)
  - 상대 로봇 위치 → 원형 가상 장애물 → global costmap LETHAL_OBSTACLE 주입
- [ ] `waypoints.yaml` 작성: 강의실, 상담실, 회의실 등 목적지 좌표 정의
- [ ] Nav2 BT 목적지 연동 (waypoint → navigate_to_pose action)
- [ ] `wego_behaviour` 패키지: 최상단 BT 설계 (대기 → 호출 → 안내 → 복귀)
- [ ] 우선순위 기반 임무 할당: 리더 busy → 서브 활성화 로직
- [ ] 음성 파이프라인 Level 1~3 구현 (VAD + openWakeWord + faster-whisper CUDA)
- [ ] 음성 파이프라인 Level 4~6 구현 (NLU if-else + Gemini API + Piper TTS)
- [ ] YOLO 사람 감지 → 방향 회전 + 10~20s 안내 멘트 발화

### P2 — 고도화 (Enhancement)
- [ ] NLU 백업: Gemma-2B (Ollama) 네트워크 단절 시 로컬 폴백
- [ ] 목적지 도달 후 "추가 용무 확인" 대화 흐름
- [ ] 관제 UI (기술 구현 완료 후 착수)
- [ ] 전력 최적화: 대기 상태 CPU/GPU 사용량 프로파일링
- [ ] 다국어 안내 검토 (영어권 방문자 대응)

---

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Orin Nano GPU 메모리: YOLO + faster-whisper 동시 가동 시 OOM 가능성 | High | 검토 필요 |
| openWakeWord "헤이 리모" 커스텀 모델 학습 필요 여부 | Medium | 미결정 |
| 두 로봇이 동시에 호출될 때 충돌 시나리오 | Medium | BT 설계 시 처리 예정 |
| Gemini API 응답 지연이 대화 흐름에 미치는 영향 | Low | 모니터링 |
