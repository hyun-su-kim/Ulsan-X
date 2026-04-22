# Resolved Decisions

> 해결된 결정을 여기에 보관. DECISION-LOG.md에서 이동됨.
> 형식: 원본 DEC-XXX 항목 + **Resolution** 줄 추가.

### DEC-009: Domain Bridge 실행 위치 및 구성 ~~(Superseded by DEC-010)~~
- **Options**:
  - A) 각 로봇에서 실행: 자신의 토픽을 다른 domain으로 직접 push
  - B) 노트북에서 실행: 노트북이 두 domain에서 pull
- **Decision**: B — 노트북에서 실행
- **Superseded by**: DEC-010 (2026-04-17) — 노트북 워크스페이스 구성 재검토 결과, domain bridge를 각 LIMO에서 push 방식으로 실행하는 것으로 전환. 노트북 의존성 제거 및 단일 launch 명령 통일.
- **Date**: 2026-04-17

---

### DEC-008: 멀티로봇 TF 프레임 ID 분리 방법 ~~(Superseded by DEC-011)~~
- **Options**:
  - A) 로봇에서 직접 수정: robot_state_publisher `frame_prefix` + EKF `odom_frame`/`base_link_frame` 변경
  - B) 노트북 relay 노드: domain_bridge로 `/tf`를 `/robot1/tf`로 수신 후 프레임 이름 변환
- **Decision**: A — 로봇에서 직접 수정
- **Superseded by**: DEC-011 (2026-04-21) — TF 브릿징 방식 전체를 폐기하고 amcl_pose 공유 방식으로 전환. 각 로봇은 표준 TF 프레임(`base_link`, `odom`, `map`) 그대로 유지. TF frame prefix 불필요.
- **Date**: 2026-04-17
