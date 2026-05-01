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

## 동작 흐름

```
Nav2로 홈 근처 이동 (±10~30cm)
    ↓
/aruco_correct 서비스 호출
    ↓ [wego_aruco 내부]
    마커 ID 감지
    solvePnP → tvec (거리/측면), rvec (법선 벡터)
    dist_err = tvec[2] - target_dist
    lat_err  = tvec[0]
    yaw_err  = atan2(R[0,2], R[2,2])  ← rvec 법선 벡터
    P제어 → cmd_vel 발행 (loop)
    3축 오차 threshold 이내 → 정차
    ↓
마커 map 좌표 역산
    robot_x = marker_x - (target_dist + cam_offset) × cos(marker_yaw)
    robot_y = marker_y - (target_dist + cam_offset) × sin(marker_yaw)
    ↓
/initialpose 발행 (AMCL 리셋) ← wego_aruco가 직접 발행
    ↓
정차 완료 응답 → wego_behaviour IDLE 전환
```

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

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `KP_LINEAR` | 0.4 | 전진/후진 게인 |
| `KP_ANGULAR` | 0.8 | 측면 편차 회전 게인 |
| `KP_YAW` | — | 법선 yaw 오차 게인 (rvec 추가 후 설정) |
| `MAX_LINEAR` | 0.15 m/s | 최대 전진 속도 |
| `MAX_ANGULAR` | 0.4 rad/s | 최대 회전 속도 |
| `DIST_TOL` | 0.03 m | 거리 허용 오차 |
| `LAT_TOL` | 0.03 m | 측면 허용 오차 |
| `YAW_TOL` | — | 법선 yaw 허용 오차 (rvec 추가 후 설정) |
| `TIMEOUT_SEC` | 30.0 s | 수렴 타임아웃 |

## markers.yaml 형식

```yaml
markers:
  0:                   # LIMO1 홈 마커
    size: 0.20         # 마커 한 변 길이 (m)
    target_dist: ???   # 정차 목표 거리 (m) — 20cm 마커 교체 후 재측정 필요
    cam_offset: 0.23   # base_link → camera_link 전방 오프셋 (m)
    map_x: ???         # 마커 map 좌표 — 측정 대기
    map_y: ???
    map_yaw: ???       # 마커가 바라보는 방향 (로봇 접근 방향의 반대)
  1:                   # LIMO2 홈 마커
    size: 0.20
    target_dist: 0.30  # 재측정 필요
    cam_offset: 0.23
    map_x: ???
    map_y: ???
    map_yaw: ???

home_marker:
  home_robot1: 0
  home_robot2: 1
```

> `cam_offset` 출처: `wego/launch/camera_tilt_launch.py` — base_link→camera_mount(0.20m) + camera_rotate→camera_link(0.03m) = 0.23m

## 실행 방법

```bash
# LIMO1
ros2 launch wego_aruco aruco_localizer_launch.py home_key:=home_robot1

# LIMO2
ros2 launch wego_aruco aruco_localizer_launch.py home_key:=home_robot2
```

## 구현 현황 (2026-05-01)

| 항목 | 상태 |
|------|------|
| solvePnP 기반 pose 추정 | 완료 |
| tvec 기반 dist/lateral P제어 | 완료 |
| rvec 법선 벡터 yaw 보정 | 완료 |
| /initialpose 발행 (wego_aruco) | 완료 |
| markers.yaml ID 0 map 좌표 입력 | 완료 (AMCL 역산, 2차 검증 예정) |
| target_dist 재측정 (20cm 마커) | 완료 (0.976m) |
| markers.yaml ID 1 map 좌표 입력 | **미완료** (LIMO 2 측정 필요) |
| **Nav2 홈 복귀 방향 오류** | **미해결** — 마커 카메라 시야 밖 |
| 실기기 통합 검증 | **미완료** (방향 오류 해결 후) |

## 미해결 이슈 (2026-05-01)

**Nav2 홈 복귀 시 방향 오류**
- 현상: Nav2 goal succeeded 후 로봇이 마커 반대 방향으로 정차 → 카메라에 마커 미감지
- 원인: AMCL drift로 실제 도착 yaw가 home_robot1 waypoint yaw(1.475)와 불일치
- 시도: `yaw_goal_tolerance 0.25 → 0.15` 축소 — 여전히 발생
- 후보 해결책:
  1. tolerance 추가 축소 (수렴 실패 위험)
  2. 홈 도착 후 마커 방향으로 강제 회전 스텝 추가 (ReturningState)

## 주의사항

- `target_dist`는 20cm 마커 부착 후 `/aruco_debug` 토픽으로 재측정 필요
- 카메라 실제 토픽명은 Orbbec 드라이버 기동 후 `ros2 topic list`로 확인
- visual servoing 중 Nav2와 cmd_vel 충돌 없음 — Nav2가 1차 이동 완료 후 서비스 호출
- 마커 map 좌표는 AMCL + aruco_debug 역산(1차) → RViz 직접 측정(2차 검증) 순서로 정밀화
