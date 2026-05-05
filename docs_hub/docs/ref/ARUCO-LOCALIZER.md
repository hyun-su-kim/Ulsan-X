# ArUco 마커 기반 정밀 도킹 설계 문서

> 관련 결정: DEC-016, DEC-018 | 담당 패키지: `wego_aruco`

## 적용 목적

홈 복귀 시 ArUco 마커를 이용한 visual servoing으로 정밀 정차 후 AMCL drift를 리셋한다.

- Nav2(AMCL)의 누적 drift를 매 안내 사이클마다 홈 복귀 시 보정
- **Coarse-to-Fine 패턴**: Nav2 대략 이동 → ArUco visual servoing 정밀 정차 → /initialpose 리셋
- MiR, Fetch 등 상용 AMR 및 Nav2 opennav_docking과 동일한 산업 표준 패턴

## 마커 구성

- 마커 수: **2개** (LIMO1용 ID 0, LIMO2용 ID 1)
- 부착 위치: 각 로봇 홈 위치 **정면** 벽 (로봇이 홈에 서면 카메라 정면에 마커)
- 각 로봇은 자신의 마커 ID만 추적

## 동작 흐름 (2-Phase Visual Servoing)

```
Nav2로 홈 근처 이동 (±10~30cm)
    ↓
/aruco_correct 서비스 호출
    ↓ [wego_aruco 내부]

    ── Phase 1: 전진 접근 ──────────────────────────────
    마커 ID 감지 → solvePnP → tvec
    dist_err = tvec[2] - INTERMEDIATE_DIST (0.30m 목표)
    lat_err  = tvec[0]
    linear  = clip(KP_LINEAR × dist_err,  ±MAX_LINEAR)
    angular = clip(-KP_ANGULAR × lat_err, ±MAX_ANGULAR)  ← lateral만, yaw 제외
    수렴 조건: |dist_err| < 0.03m AND |lat_err| < 0.03m → Phase 2 진입
    미감지 시: 저속 전진(0.05 m/s)으로 마커 재감지 시도

    ── Phase 2: 후진 정밀 정차 ─────────────────────────
    dist_err = tvec[2] - target_dist (2.007m 목표, 음수 → 후진)
    lat_err  = tvec[0]
    linear  = clip(KP_LINEAR × dist_err,  ±MAX_LINEAR)
    angular = clip(-KP_ANGULAR × lat_err, ±MAX_ANGULAR)  ← lateral만, yaw 제외
    수렴 조건: |dist_err| < 0.03m → 정차
    미감지 시: 정지 후 재감지 대기

    ↓
마커 map 좌표 역산 (부호 주의: +)
    total_dist = target_dist + cam_offset  (2.007 + 0.23 = 2.237m)
    robot_x = marker_x + total_dist × cos(marker_yaw)   ← + (marker_yaw는 마커→로봇 방향)
    robot_y = marker_y + total_dist × sin(marker_yaw)
    robot_yaw = marker_yaw + π
    ↓
/initialpose 발행 (AMCL 리셋) ← wego_aruco가 직접 발행
    ↓
정차 완료 응답 → wego_behaviour IDLE 전환
```

### 설계 원칙: 제자리 회전 금지

Phase 1/2 모두 **lateral(좌우) 오차만 보정하고 yaw 보정(제자리 회전)은 수행하지 않는다.**

- 제자리 yaw 보정을 하면 로봇이 회전하면서 마커가 카메라 FOV를 벗어나 미감지 발생
- 전진하면서 lateral만 보정해도 yaw가 기하학적으로 수렴:
  - 2m 거리에서 마커를 이미지 중앙에 맞추면 로봇이 마커 정면을 향하게 됨
  - 마커에 가까워질수록 픽셀 해상도 증가 → 정밀도 향상
- Phase 1 실기기 검증 결과: lat=0.001m 수렴 확인 (2026-05-04)

## 패키지 구조

```
ulsan_ws/src/wego_aruco/
├── wego_aruco/
│   ├── __init__.py
│   └── aruco_localizer.py      # visual servoing 노드
├── config/
│   └── markers.yaml            # 마커 ID / size / target_dist
├── launch/
│   └── aruco_localizer_launch.py
├── package.xml
└── setup.py
```

## 마커 사양

| 항목 | 값 |
|------|-----|
| 딕셔너리 | `DICT_4X4_50` |
| 크기 | **20cm × 20cm** |
| 재질 | 종이 인쇄 (A4) |
| 부착 위치 | 각 로봇 홈 정면 벽 (카메라 정면) |

> 크기 선정 근거: 마커-로봇 거리 1.8m 기준 `size/distance = 0.20/1.8 = 0.11 > 0.1` — solvePnP 정확도 기준치 충족

## 노드 인터페이스

| 방향 | 토픽/서비스 | 타입 | 설명 |
|------|------------|------|------|
| Subscribe | `/camera/color/image_raw` | `sensor_msgs/Image` | 컬러 이미지 |
| Subscribe | `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 카메라 내부 파라미터 |
| Publish | `/cmd_vel` | `geometry_msgs/Twist` | visual servoing 제어 |
| Publish | `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | 정차 완료 후 AMCL 리셋 |
| Publish | `/aruco_debug` | `std_msgs/String` | 마커 감지 거리 (측정용) |
| Service | `/aruco_correct` | `std_srvs/Trigger` | 정밀 정차 요청 |

> `/initialpose`는 `wego_aruco`가 직접 발행 — 마커 map 좌표 역산으로 정확한 위치 계산. `wego_behaviour`는 정차 완료 응답만 수신.

## P 제어 파라미터 (aruco_localizer.py 클래스 상수)

> 2026-05-04 실기기 튜닝 완료 기준값

| 상수 | 값 | 설명 | 변경 이력 |
|------|-----|------|----------|
| `KP_LINEAR` | 0.3 | 거리 오차 → 선속도 게인 | — |
| `KP_ANGULAR` | 1.2 | lateral 오차 → 각속도 게인 | 0.8 → 1.2 (lateral 보정 강도 상향) |
| `KP_YAW` | 0.5 | yaw 오차 게인 (현재 미사용) | — |
| `MAX_LINEAR` | 0.08 m/s | 최대 선속도 | 0.15 → 0.08 (저속 정밀도 향상) |
| `MAX_ANGULAR` | 0.3 rad/s | 최대 각속도 | 0.4 → 0.3 (과보정 방지) |
| `DIST_TOL` | 0.03 m | 거리 수렴 허용 오차 | — |
| `LAT_TOL` | 0.03 m | lateral 수렴 허용 오차 | — |
| `YAW_TOL` | 0.05 rad | yaw 허용 오차 (현재 미사용) | — |
| `CONTROL_RATE` | 10 Hz | 제어 루프 주기 | — |
| `TIMEOUT_SEC` | 60.0 s | Phase 1+2 합산 타임아웃 | 30 → 60 |
| `INTERMEDIATE_DIST` | 0.30 m | Phase 1 목표 거리 (30cm 근접) | — |

## markers.yaml 형식

```yaml
markers:
  0:                   # LIMO1 홈 마커
    size: 0.20         # 마커 한 변 길이 (m)
    target_dist: 2.007 # 정차 목표 거리 (m) — home_robot1 위치에서 실측 (2026-05-04)
    cam_offset: 0.23   # base_link → camera_link 전방 오프셋 (m)
    map_x: 12.712      # 마커 map 좌표 (home_robot1 + total_dist × cos(1.475))
    map_y: -1.393      # 마커 map 좌표 (home_robot1 + total_dist × sin(1.475))
    map_yaw: -1.667    # home_robot1 yaw(1.475) - π  ← 마커→로봇 방향각
  1:                   # LIMO2 홈 마커
    size: 0.20
    target_dist: 0.30  # 미측정
    cam_offset: 0.23
    map_x: 0.0         # 미측정
    map_y: 0.0
    map_yaw: 0.0

home_marker:
  home_robot1: 0
  home_robot2: 1
```

### map_x/y 계산 방법

```
# 로봇이 home_robot1(rx, ry, ryaw)에서 마커를 바라볼 때:
total_dist = target_dist + cam_offset
map_x = rx + total_dist × cos(ryaw)
map_y = ry + total_dist × sin(ryaw)
map_yaw = ryaw - π   ← 마커→로봇 방향 (로봇 접근 방향의 반대)

# 예: home_robot1 (12.498, -3.619, 1.475), total_dist=2.237
# map_x = 12.498 + 2.237 × cos(1.475) = 12.498 + 0.219 = 12.717
# map_y = -3.619 + 2.237 × sin(1.475) = -3.619 + 2.226 = -1.393
```

### _publish_initialpose 역산 공식 (부호 주의)

`map_yaw`는 마커→로봇 방향각이므로 역산 시 **더하기(+)** 를 사용한다.

```python
# 올바른 공식
robot_x = marker_x + total_dist * cos(marker_yaw)   # ← + (틀리기 쉬운 부분)
robot_y = marker_y + total_dist * sin(marker_yaw)
robot_yaw = marker_yaw + π

# 검증 (home_robot1 재현):
# 12.712 + 2.237 × cos(-1.667) = 12.712 - 0.214 = 12.498 ✓
# -1.393 + 2.237 × sin(-1.667) = -1.393 - 2.226 = -3.619 ✓
```

> `cam_offset` 출처: `wego/launch/camera_tilt_launch.py` — base_link→camera_mount(0.20m) + camera_rotate→camera_link(0.03m) = 0.23m

## 실행 방법

```bash
# LIMO1
ros2 launch wego_aruco aruco_localizer_launch.py home_key:=home_robot1

# LIMO2
ros2 launch wego_aruco aruco_localizer_launch.py home_key:=home_robot2
```

## 구현 현황 (2026-05-04)

| 항목 | 상태 |
|------|------|
| solvePnP 기반 pose 추정 | 완료 |
| 2-Phase lateral-only P제어 | 완료 (2026-05-04) |
| Phase 1: 전진 30cm + lateral 보정 | 완료 — lat=0.001m 수렴 확인 |
| Phase 2: 후진 2.007m + lateral 보정 | 완료 — lat=0.008m 수렴 확인 |
| target_dist = 2.007m 확정 | 완료 (home_robot1 위치 실측) |
| ArUco 기본 감지 파라미터 복원 | 완료 (원거리 특화 불필요) |
| home_robot1 waypoint 갱신 | 완료 (x=12.498, y=-3.619, yaw=1.475) |
| markers.yaml ID 0 map 좌표 | 완료 (12.712, -1.393, -1.667) |
| markers.yaml ID 1 map 좌표 | **미완료** (LIMO 2 측정 필요) |
| _publish_initialpose 공식 버그 수정 | **미완료** — 부호 오류 확인, 수정 대기 |
| /initialpose 활성화 | **미완료** — 공식 수정 후 주석 해제 예정 |
| 물리 위치 15cm 편차 원인 규명 | **진행 중** — /initialpose 활성화 후 재측정 예정 |
| markers.yaml ID 1 map 좌표 입력 | **미완료** (LIMO 2 측정 필요) |

## 미해결 이슈 (2026-05-04)

### _publish_initialpose 부호 버그

- 현상: 주석 해제 시 AMCL이 (12.828, -0.193)으로 리셋 — 실제 위치(12.498, -3.619)와 크게 다름
- 원인: 역산 공식에서 `-` 를 사용했으나 `+` 가 맞음 (map_yaw는 마커→로봇 방향이므로)
  ```python
  # 버그: robot_x = map_x - total_dist * cos(map_yaw)
  # 수정: robot_x = map_x + total_dist * cos(map_yaw)
  ```
- 상태: 확인 완료, 수정 + /initialpose 주석 해제 예정

### 물리 위치 ~15cm 편차

- 현상: Phase 2 완료 후 물리 정차 위치가 home_robot1(12.498, -3.619)에서 약 15cm 벗어남
- 현재 제어 정밀도: Phase 1 lat=0.001m, Phase 2 lat=0.008m (제어 자체는 정상)
- 추정 원인:
  1. Phase 1 곡선 접근으로 인한 축 이동 → Phase 2 후진 축이 home_robot1과 다름
  2. AMCL drift (누적 오차) — /initialpose 활성화 후 개선 여부 확인 필요
  3. 주행 거리(3.4m 왕복) 대비 odometry 기계적 오차
- 다음 단계: _publish_initialpose 버그 수정 → /initialpose 활성화 → 재측정

## 주의사항

- `target_dist`는 20cm 마커 부착 후 `/aruco_debug` 토픽으로 재측정 필요
- 카메라 실제 토픽명은 Orbbec 드라이버 기동 후 `ros2 topic list`로 확인
- visual servoing 중 Nav2와 cmd_vel 충돌 없음 — Nav2가 1차 이동 완료 후 서비스 호출
- 마커 map 좌표는 AMCL + aruco_debug 역산(1차) → RViz 직접 측정(2차 검증) 순서로 정밀화
