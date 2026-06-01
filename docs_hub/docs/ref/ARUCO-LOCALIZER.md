# ArUco 마커 정밀 도킹 — (구 aruco_localizer 설계, 폐기)

> ⚠️ **이 문서가 설명하던 `aruco_localizer.py`(2-Phase lateral-only visual servoing) 방식은 전량 폐기되었습니다 (2026-05-11).**
> 노드 파일 `aruco_localizer.py`는 삭제됨. 마커 map 좌표 역산으로 `/initialpose`를 계산하던 방식도 폐기.

## 현재 구현 (정본)

홈 정밀 도킹은 **`wego_aruco/aruco_home_dock.py` — PBVS staged 제어**로 대체됨.

| 항목 | 현재 방식 | 참조 |
|------|----------|------|
| 도킹 제어 | 비홀로노믹 과소구동 진단 → (ρ,α,θ_g) 기하 통합 → **단계분리(staged)** turn→drive→turn 채택 (극좌표 A/B 비교) | DEC-038 |
| AMCL 리셋 | 마커 역산 폐기(단일 평면 마커 yaw 관측성 한계로 140° 오차) → **waypoints.yaml home 좌표 직접 발행** | DEC-041 |
| 실행 위치 | **로봇(LIMO 도메인 6/7)** — 카메라→cmd_vel 닫힌 루프 로컬화 | DEC-043 |
| 서비스 | `/aruco_home_dock` (`std_srvs/Trigger`), client = `wego_behaviour` ReturningState | NODE-TOPOLOGY.md |
| passive 주행 중 보정 | `pose_corrector.py` — **비활성**(캘리브레이션 도구로만 보존) | — |

현재 노드·토픽·서비스 구성은 [NODE-TOPOLOGY.md](NODE-TOPOLOGY.md)의 `wego_aruco` 섹션, 제어 설계 근거는 [archive/decisions-resolved.md](../archive/decisions-resolved.md)의 DEC-038/041/042 참조.

---

## (참고) 폐기된 2-Phase visual servoing 요약

초기 `aruco_localizer.py`는 Nav2로 홈 근처 이동 후 **Phase 1(전진 30cm + lateral 보정) → Phase 2(후진 정밀 정차)** 의 lateral-only P제어로 정차하고, 마커 map 좌표를 역산해 `/initialpose`를 발행하는 방식이었다. 제자리 회전 금지(FOV 유지)가 핵심 원칙이었으나, 곡선 접근으로 인한 축 이동·물리 정차 ~15cm 편차·역산 부호 버그 등이 확인되어 PBVS staged 방식으로 재설계되며 폐기되었다. 상세 수치는 git 히스토리 참고.
