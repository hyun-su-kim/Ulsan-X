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

## SLAM 품질 향상 절차 (학원 환경 — 유리+복도)

실기기 SLAM 시 발생한 문제와 해결 순서.

### 문제
- 유리 구간: LiDAR가 유리를 투과 → 특징점 없음 → 맵에 구멍
- 복도 구간: 양쪽 벽만 있는 긴 직선 → loop closure 실패 → 복도 휨(drift)

### 해결 절차

1. **유리에 종이 부착** — LiDAR 반사 특징점 확보. 매핑 완료 후 제거.
2. **복도 중간에 임시 장애물 배치** — 특징점 추가로 복도 drift 방지.
3. **천천히 루프 주행(왕복)으로 매핑**
   - RViz에서 `/constraint_list` 토픽 확인
   - 노란 선이 출발 지점 부근에 생기면 loop closure 성공
4. **맵 저장 후 임시 장애물 실제 환경에서 제거**
5. **GIMP로 후보정** — 장애물 흔적 및 스파이크 노이즈 제거
6. **가상 벽 처리** — 유리문 등 인식이 덜 된 구간을 GIMP로 직접 벽 그리기

```bash
# 맵 저장
ros2 run nav2_map_server map_saver_cli -f ~/map_result/map

# 저장된 맵을 프로젝트로 복사 (노트북에서 scp)
scp wego@<LIMO1_IP>:~/map_result/map.* \
  /home/wego/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/
```

---

## 멀티로봇 위치 추정 구조

> DEC-011 (2026-04-21): TF frame prefix 방식 폐기 → **amcl_pose 공유 방식** 확정

### 설계 원칙

각 로봇은 표준 TF 프레임을 그대로 유지 (`base_link`, `odom`, `map`). prefix 없음.
위치 정보는 `/amcl_pose`만 domain bridge로 전달. `/tf` 브릿징 없음.

```
LIMO 1 (domain 6)            LIMO 2 (domain 7)
map → odom → base_link       map → odom → base_link
      ↓ /amcl_pose                  ↓ /amcl_pose
      [wego_bridge]                 [wego_bridge]
             ↓                             ↓
        노트북 (domain 5)
        /limo_1/amcl_pose   /limo_2/amcl_pose
             ↓                             ↓
        wego_ui (지도 위 위치 마커 시각화)
```

### 실행 방법

```bash
# LIMO 1, LIMO 2 동일한 명령 (robot_name 인자 없음)
ros2 launch wego teleop_launch.py
ros2 launch wego navigation_diff_launch.py
ros2 launch wego_bridge robot_bridge_launch.py  # ROS_DOMAIN_ID 읽어 자동 설정

# 노트북 (domain 5)
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=<path>/map.yaml
```

### 상대 로봇 충돌 회피 (ulsan_obstacle_layer)

```
상대방 /amcl_pose 수신 (domain bridge 경유)
  → PeerObstacleLayer: 해당 좌표에 반경 0.35m 원형 가상 장애물 생성
  → global costmap LETHAL_OBSTACLE 주입
  → Nav2 글로벌 플래너(A*)가 자동 우회 경로 생성
```

Nav2 플래너 수정 없이 적용 가능. `peer_pose_topic`을 비워두면 `ROS_DOMAIN_ID`로 자동 결정 (domain 6 → limo_2, domain 7 → limo_1).

---

## 위치 추정 (AMCL)

- **방식**: Nav2 내장 AMCL (Adaptive Monte Carlo Localization)
- **사용 센서**: LiDAR 스캔 (`/scan`)
- **초기 위치**: Home 위치에서 초기 pose estimate 설정

### 수정된 AMCL 파라미터 (`diff_navigation_params.yaml`)

| 파라미터 | 기본값 | 적용값 | 이유 |
|---------|--------|--------|------|
| `do_beamskip` | false | **true** | 유리 투과·난반사 빔 자동 무시 |
| `laser_max_range` | 12.0 | **12.0** | wego_ws 원본 복원 (실기기 테스트 결과 원본이 더 안정적) |

---

## Nav2 주행 문제 해결 과정 — 유리 구간 (2026-04-28~29)

포트폴리오·면접용 엔지니어링 판단 기록.

### 배경

SLAM 시에는 유리문에 종이를 부착해 LiDAR 특징점을 확보하고 맵을 완성했다.
실제 운용 환경에서는 종이가 없으므로, 유리 구간에서 LiDAR 스캔 특징점이 부족해질 수 있었다.

### 1단계 — AMCL 위치추정 문제 의심

**증상**: 유리 회전문 통과 구간에서 로봇이 빙글빙글 돌며 통과 못함.

**초기 가설**: 유리 구간에서 LiDAR가 특징점을 인식하지 못해 AMCL 파티클이 수렴하지 못하는 것 아닌가?

**조치**: AMCL 파라미터 수정
- `do_beamskip: true` — 유리 투과·난반사 빔 자동 무시
- `laser_max_range: 5.0` — 원거리 노이즈 제거

**결과**: RViz `/particlecloud` 확인 → 파티클이 유리 구간에서도 정상 수렴.
→ **위치추정은 문제가 아니었다.** 가설 기각.

### 2단계 — Inflation 조정 시도

복도·강의실 등 다른 구간은 주행 정상. 유리 회전문 구간만 빙글빙글 도는 현상 지속.

**가설**: 유리문 근처를 로봇이 지나갈 여유 공간이 부족한 것 아닌가?

**조치**: global costmap `inflation_layer`의 `inflation_radius` 확대 (유리문 근처 여유 공간 확보 목적)

**결과**: 해결되지 않음.

### 3단계 — Global Costmap 시각화로 원인 확인

**조치**: RViz에서 `/global_costmap/costmap` 토픽 직접 확인.

**관찰**: 유리 회전문 구간 주변에 실제 장애물이 없음에도 costmap 곳곳에 장애물(occupied cell)이 찍혀 있음.

**원인 확정**: **LiDAR 난반사(phantom obstacle)**
- LiDAR 빔이 유리를 투과하거나 난반사 → 실제 없는 위치에 장애물 포인트 생성
- 난반사 빔은 raytrace 경로와 달라 자동 소거가 안 됨 → 유령 장애물 지속
- 유령 장애물이 경로를 막음 → Nav2가 반복 리플래닝 → 빙글빙글

### 4단계 — 소프트웨어 해결 방법 전수 검토 (2026-04-29)

phantom 원인 확정 후 아래 방법들을 순서대로 시도·검토.

| 방법 | 시도 결과 |
|------|----------|
| `obstacle_max_range` 축소 | phantom이 2m 이내 → 효과 없음 |
| Keepout Filter (센서 무시 구역) | phantom이 폴리곤 밖에도 찍힘 → 효과 없음 |
| 맵 유리 연장 (GIMP) | 로봇 통과 경로 차단 → 포기 |
| `laser_filters` 각도 필터 | 회전 중 유리 방향 계속 바뀜 → 완벽 해결 불가 |
| `observation_persistence` 단축 | phantom이 매 스캔 동일 위치 재생성 → 효과 없음 |
| `clearing: False` + `combination_method` 조정 | phantom 누적 완화 시도했으나 근본 해결 안 됨 |

**VoxelLayer + Orbbec 카메라 검토 결과**: Orbbec Astra는 IR 구조광 방식으로 유리 투과 → depth 값 없음. LiDAR phantom보다 오히려 유리를 아예 못 잡음. 유리 감지 목적으로는 부적합.

### 최종 결정 — Keepout Filter (금지구역 방식) + DenoiseLayer

**Keepout Filter를 금지구역으로 사용** (센서 무시 구역이 아님):
- 유리 구간 주변에 금지구역 폴리곤 설정
- global planner가 해당 구역을 우회하는 경로 생성
- 로봇이 유리에 가까이 가지 않음 → 난반사 각도 감소 → phantom 감소
- Nav2 공식 문서 등재 기능, 상용 AMR(iRobot·Locus·Geek+)의 "가상 벽"과 동일 원리

**DenoiseLayer 추가**:
- Nav2 공식 플러그인 — 고립된 단일 셀 phantom 필터링
- 설정 거의 없이 바로 적용 가능
- Keepout Filter 경계 밖으로 새어나오는 phantom 보조 차단

### 5단계 — Keepout Filter + DenoiseLayer 적용 결과 (2026-04-29)

| 구간 | 결과 |
|------|------|
| 복도·강의실 등 일반 구간 | 정상 자율주행 |
| 목적지·홈 위치 주행 | 정상 — 운용 목적 달성 |
| **유리 회전문 통과 구간** | **여전히 `controller_server: Failed to make progress` 발생** |

**유리 회전문 통과가 안 되는 근본 이유**:
- Keepout Filter는 global costmap에만 적용 → global 경로는 우회하도록 생성됨
- 그러나 유리 근처를 지나는 경로라면 local costmap에 phantom이 여전히 찍힘
- local costmap의 phantom → DWB controller가 제어 명령 생성 실패 → 진행 불가
- 유리 회전문 자체를 통과하는 경로는 어떤 소프트웨어 설정으로도 LiDAR 물리 한계 극복 불가

**최종 운용 정책**:
- **유리 회전문 통과는 경로에서 영구 제외** — Keepout 금지구역으로 완전 차단
- 운용 목적(강의실·상담실·홈 안내 주행)에는 유리 회전문 통과가 불필요 → 실질적 문제 없음
- 유리문은 항상 열린 상태 유지 가정. 닫힘 감지(초음파 + TTS)는 Phase 4.

> **면접 어필 포인트**: "LiDAR의 물리적 한계(유리 투과·난반사)를 소프트웨어만으로 완전 해결할 수 없음을 실기기 검증으로 확인하고, 운용 목적에서 해당 구간을 제외하는 현실적 판단을 내렸다. 목적지 안내 주행이라는 서비스 요구사항 내에서는 완전 동작함."

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

## Fleet 충돌 회피 (ulsan_obstacle_layer)

상대 로봇을 동적 장애물로 인식시키는 방식.

```
/limo_N/amcl_pose 수신 (Domain Bridge 경유)
  → ulsan_obstacle_layer (PeerObstacleLayer): 해당 좌표에 반경 R의 원형 가상 장애물 생성
  → global costmap에 LETHAL_OBSTACLE로 주입
  → Nav2 글로벌 플래너(NavFn/A*)가 자동으로 우회 경로 생성
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
