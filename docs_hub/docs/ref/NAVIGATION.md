# NAVIGATION — SLAM & Nav2 설정

## 지도 작성 (Cartographer SLAM)

- **사용 패키지**: `wego` (내장 cartographer 설정)
- **작성 주체**: LIMO 1으로만 SLAM 수행. LIMO 2는 완성된 맵 파일 복사해서 사용.
- **지도 공유**: 완성된 `.pgm` + `.yaml`을 LIMO 2와 노트북의 `wego_2d_nav/maps/`에 복사
- **재작성 조건**: 학원 내부 구조 변경 시

```bash
# LIMO 1에서 실행

# Terminal 1: 드라이버 전체 기동 (limo_base, ydlidar, EKF, 카메라)
ros2 launch wego teleop_launch.py

# Terminal 2: Cartographer SLAM 시작 (RViz 자동 실행됨)
ros2 launch wego cartographer_launch.py

# Terminal 3: 키보드 텔레op으로 공간 주행
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# 공간 전체 맵핑 완료 후 — Terminal 4: 맵 저장
ros2 run nav2_map_server map_saver_cli -f ~/map_result/map

# 저장된 맵을 프로젝트로 복사 (노트북에서 scp)
scp wego@<LIMO1_IP>:~/map_result/map.* \
  /home/wego/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/
```

---

## 멀티로봇 위치 추정 구조

### TF frame 분리 방식 (DEC-005 참고)

각 로봇이 서로 다른 ROS domain(LIMO1=6, LIMO2=7)에서 동작하므로 토픽 이름은 그대로 둠.
노트북(domain 5)에서 두 로봇의 `/tf`를 머지할 때만 frame 이름이 충돌 → **frame ID만 다르게 설정**.

```
LIMO 1 (domain 6):  map → robot1/odom → robot1/base_link
LIMO 2 (domain 7):  map → robot2/odom → robot2/base_link

노트북 (domain 5, domain bridge 수신 후):
  map
  ├── robot1/odom → robot1/base_link
  └── robot2/odom → robot2/base_link
```

### 실행 방법

```bash
# LIMO 1 (domain 6)에서
ros2 launch wego navigation_diff_launch.py robot_name:=robot1

# LIMO 2 (domain 7)에서
ros2 launch wego navigation_diff_launch.py robot_name:=robot2
```

`robot_name` 인자가 `diff_navigation_params.yaml`의 `ROBOT_NAME` 플레이스홀더를 치환.
→ AMCL의 `base_frame_id`, `odom_frame_id`, costmap의 `robot_base_frame` 등 자동 적용.

### 변경된 파라미터 항목 (`diff_navigation_params.yaml`)

| 파라미터 | 원래 값 | robot1 실행 시 | robot2 실행 시 |
|---------|---------|--------------|--------------|
| `amcl.base_frame_id` | `base_link` | `robot1/base_link` | `robot2/base_link` |
| `amcl.odom_frame_id` | `odom` | `robot1/odom` | `robot2/odom` |
| `bt_navigator.robot_base_frame` | `base_link` | `robot1/base_link` | `robot2/base_link` |
| `global_costmap.robot_base_frame` | `base_link` | `robot1/base_link` | `robot2/base_link` |
| `global_costmap.global_frame` | `map` | `map` (변경 없음) | `map` (변경 없음) |
| `local_costmap.global_frame` | `odom` | `robot1/odom` | `robot2/odom` |
| `local_costmap.robot_base_frame` | `base_link` | `robot1/base_link` | `robot2/base_link` |
| `behavior_server.local_frame` | `odom` | `robot1/odom` | `robot2/odom` |
| `behavior_server.robot_base_frame` | `base_link` | `robot1/base_link` | `robot2/base_link` |
| `fleet_obstacle_layer.pose_topic` | — | `robot2/amcl_pose` | `robot1/amcl_pose` |

---

## 위치 추정 (AMCL)

- **방식**: Nav2 내장 AMCL (Adaptive Monte Carlo Localization)
- **사용 센서**: LiDAR 스캔 (`/scan`)
- **초기 위치**: Home 위치에서 초기 pose estimate 설정
- **파티클 필터**: 기본 설정 사용 → 필요 시 튜닝

---

## 목적지 관리 (waypoints.yaml)

목적지 좌표는 `waypoints.yaml`에서 중앙 관리. Nav2 BT에 이름으로 전달.

```yaml
# waypoints.yaml 예시 구조
waypoints:
  home_robot1:
    x: 0.0
    y: 0.0
    yaw: 0.0
  home_robot2:
    x: 0.5
    y: 0.0
    yaw: 0.0
  room_1:         # 1강의실
    x: 5.2
    y: 3.1
    yaw: 1.57
  room_2:         # 2강의실
    x: 8.4
    y: 3.1
    yaw: 1.57
  counseling_room: # 상담실
    x: 12.0
    y: 1.5
    yaw: 3.14
  meeting_room:   # 회의실
    x: 10.5
    y: 5.0
    yaw: 0.0
  restroom:       # 화장실
    x: 3.0
    y: 7.2
    yaw: -1.57
```

> 실제 좌표는 지도 작성 후 RViz에서 측정하여 채워야 함.

---

## Nav2 행동 트리 연동

`wego_behaviour` BT에서 목적지 결정 → Nav2 `navigate_to_pose` action으로 전달.

```
wego_behaviour BT
  → NLU에서 destination 추출 (예: "room_1")
  → waypoints.yaml에서 좌표 조회
  → Nav2 /navigate_to_pose action goal 전송
    → Nav2 BT 실행 (경로 계획 + 장애물 회피 + 제어)
      → 도달 시 결과 반환
  → wego_behaviour BT 다음 단계 진행 (추가 용무 확인)
```

---

## Fleet 충돌 회피 (wego_fleet)

상대 로봇을 동적 장애물로 인식시키는 방식.

```
/robot2/amcl_pose 수신 (Domain Bridge 경유)
  → wego_fleet: 해당 좌표에 반경 R의 원형 가상 장애물 생성
  → Nav2 costmap에 obstacle layer로 주입
  → Nav2 플래너가 자동으로 우회 경로 생성
```

**장점**: Nav2 기존 플래너 수정 없이 충돌 회피 가능.
**고려사항**: 로봇 실제 크기 + 안전 마진을 반경 R에 반영할 것.

---

## 로봇 복귀 흐름

```
목적지 도달 (Nav2 action 성공)
  → TTS: "다른 도움이 필요하시면 말씀해 주세요"
  → STT 짧게 대기 (타임아웃: ~10s)
    ├── 추가 요청 있음 → 새 목적지로 안내
    └── 없음 / 타임아웃 → Home 좌표로 navigate_to_pose
        → 도착 후 대기 상태 복귀
```
