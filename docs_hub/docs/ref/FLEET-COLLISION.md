# 멀티로봇 충돌 회피 구현 설계

> ⚠️ **이 문서의 결론(PeerObstacleLayer — 상대 로봇을 costmap 가상 장애물로 주입)은 전량 폐기되었습니다 (DEC-022).**
> global costmap은 경로 계획 시에만 참조되어 주행 중 동적 회피가 불가한 구조적 한계가 확인됨.
> **현재 방식: 우선순위 기반 pause/resume** — `wego_traffic`(domain 5)이 두 로봇 거리 감지 → `/pause`·`/resume` → `wego_behaviour` WAITING. 상세: [NAVIGATION.md](NAVIGATION.md) "상대 로봇 충돌 회피" + DECISION-LOG DEC-022.
>
> 아래 내용은 **설계 탐색 이력**(중앙 FMS vs 분산 구독, O(N) vs O(N²), SPOF 분석 등)으로만 보존 — 현재 구현 아님.

## 1. 검토했던 방식과 채택하지 않은 이유

### 1-1. 중앙집중식 FMS (Fleet Management System) Primary 방식
**개요**: 노트북의 FMS 노드가 모든 로봇의 `/amcl_pose`를 수집해 `/global_robot_poses` 배열 토픽으로 묶어 발행. 각 로봇의 costmap 플러그인은 이 배열을 구독.

**장점**:
- 로봇이 N대로 늘어도 각 로봇의 구독 수는 1개로 고정 O(N)
- 코드 수정 없이 확장 가능

**채택하지 않은 이유**:
- 2대 규모에서 O(N²) vs O(N) 차이가 실질적으로 없음
- 노트북(FMS)이 꺼지면 충돌 회피 자체가 불가능 → 단일 장애점(SPOF)
- ROS2가 ROS1 master 제거로 분산 구조를 확보했는데, FMS를 충돌 회피의 주 경로로 쓰면 중앙 의존성을 애플리케이션 레벨에서 재도입하는 셈

### 1-2. FMS Primary + 직접 구독 Fallback 하이브리드
**개요**: 평상시 FMS 배열 토픽 사용, 노트북 연결 끊기면 직접 구독으로 전환.

**채택하지 않은 이유**:
- 현재 구성에서 로봇 간 직접 통신도 domain bridge를 경유하고, domain bridge는 같은 WiFi를 사용
- 노트북이 끊기더라도 로봇끼리는 같은 subnet에 있으므로 직접 bridge는 살아있을 수 있음 → Fallback 자체는 유효
- 그러나 2대 규모에서 이를 위한 구현 복잡도(타임아웃 감지, 구독 전환 로직)가 얻는 이익 대비 과함
- LiDAR 기반 기존 obstacle_layer가 자연스러운 최후 보루로 이미 존재

### 1-3. Mutex 기반 쓰레드 동기화
**개요**: 콜백 쓰레드와 costmap 업데이트 쓰레드 간 공유 변수를 mutex로 보호.

**채택하지 않은 이유**:
- Nav2 costmap 루프(10~20Hz)가 콜백 쓰레드의 mutex 해제를 기다리며 블로킹
- 루프 타이밍이 비결정적으로 변함 → 실시간 제어 루프에서 지연 발생 가능
- OS 스케줄러 개입으로 Determinism 보장 불가

### 1-4. 리더 로봇만 /map 전송
**개요**: robot1을 리더로 지정해 `/map`을 노트북으로 전송하는 역할만 담당.

**채택하지 않은 이유**:
- robot1이 꺼지면 노트북 RViz에서 지도 소실 → 단일 의존성
- 두 로봇이 동일한 map.yaml을 사용하므로 둘 다 전송해도 중복·충돌 없음
- `transient_local` QoS 덕분에 어느 쪽이라도 살아있으면 지도 유지 가능
- 리더 개념의 복잡도 대비 이득 없음

---

## 2. 채택한 방식 — 직접 구독 + std::atomic

### 2-1. 직접 구독 방식을 선택한 이유

| 기준 | 이유 |
|------|------|
| 규모 | 2대 시스템에서 O(N²) 부하 문제 없음 |
| 안정성 | 노트북 없이도 로봇끼리 직접 pose 수신 가능 |
| 단순성 | FMS 노드, 배열 메시지, 전환 로직 불필요 |
| ROS2 철학 | 각 로봇이 자율적으로 동작, 중앙 의존성 없음 |

### 2-2. std::atomic을 선택한 이유

Nav2 costmap 내부에는 두 쓰레드가 동시에 실행된다:

```
쓰레드 A (ROS executor)      → /amcl_pose 콜백: peer_x, peer_y 쓰기
쓰레드 B (Nav2 costmap 루프) → updateCosts(): peer_x, peer_y 읽기
```

**Mutex 방식의 문제**:
```cpp
// 쓰레드 B가 여기서 멈춤 — 쓰레드 A가 mutex 놓을 때까지 대기
std::lock_guard<std::mutex> lock(mtx_);
```

**std::atomic 방식의 해결**:
```cpp
// CPU 명령어 한 줄로 처리 — 대기 없음, 블로킹 없음
peer_x_.store(x, std::memory_order_relaxed);
double x = peer_x_.load(std::memory_order_relaxed);
```

| 항목 | Mutex | std::atomic |
|------|-------|-------------|
| 동기화 레벨 | OS 스케줄러 | CPU 명령어 |
| 블로킹 | 발생 | 없음 (lock-free) |
| costmap 루프 영향 | 지연 가능 | 영향 없음 |
| Determinism | 비결정적 | 결정적 |

`memory_order_relaxed`를 사용하는 이유: x와 y 사이의 순서 보장이 불필요. costmap은 어차피 다음 프레임에 재계산하므로 x와 y가 한 프레임 어긋나도 무방. 가장 빠른 옵션.

---

## 3. 최종 아키텍처

### 통신 흐름

```
Robot 1 (domain 6)              Robot 2 (domain 7)
──────────────────              ──────────────────
/amcl_pose 발행                 /amcl_pose 발행
        │                               │
        ├── bridge → domain 5           ├── bridge → domain 5
        │   (노트북: 위치 시각화용)      │   (노트북: 위치 시각화용)
        │                               │
        └── bridge → domain 7           └── bridge → domain 6
              ↓                                ↓
     Robot 2 C++ 플러그인          Robot 1 C++ 플러그인
     peer pose 수신                peer pose 수신
     costmap 마킹                  costmap 마킹
```

> /map, /tf, /tf_static 은 bridge 대상에서 제외.
> 맵은 scp로 사전 배포 후 각 기기가 로컬 map_server 실행.
> TF는 각 로봇 내부에서만 사용하며 노트북으로 전달하지 않음.

### Fallback

FMS 없음. 노트북이 꺼져도 로봇 간 bridge는 독립적으로 동작.
LiDAR 기반 기존 `obstacle_layer`가 자연스러운 최후 보루.

---

## 4. 구현 목록

### 4-1. `wego_obstacle_layer` 패키지 신규 생성 (C++, ament_cmake)

```
ulsan_ws/src/wego_obstacle_layer/
├── CMakeLists.txt
├── package.xml
├── plugins.xml                              ← pluginlib 등록
├── include/wego_obstacle_layer/
│   └── peer_obstacle_layer.hpp
└── src/
    └── peer_obstacle_layer.cpp
```

**핵심 구현 구조**:

```cpp
class PeerObstacleLayer : public nav2_costmap_2d::Layer {

  // Lock-free 좌표 저장
  std::atomic<double> peer_x_{0.0};
  std::atomic<double> peer_y_{0.0};
  std::atomic<bool>   peer_valid_{false};

  // 콜백: 상대 로봇 amcl_pose 수신 → atomic 갱신 (쓰레드 A)
  void poseCallback(const PoseWithCovarianceStamped::SharedPtr msg) {
    peer_x_.store(msg->pose.pose.position.x, std::memory_order_relaxed);
    peer_y_.store(msg->pose.pose.position.y, std::memory_order_relaxed);
    peer_valid_.store(true,                  std::memory_order_relaxed);
  }

  // Nav2 costmap 루프에서 호출 — blocking 없이 즉시 읽기 (쓰레드 B)
  void updateCosts(Costmap2D & master_grid, ...) override {
    if (!peer_valid_.load(std::memory_order_relaxed)) return;
    double px = peer_x_.load(std::memory_order_relaxed);
    double py = peer_y_.load(std::memory_order_relaxed);
    // px, py 중심 반경(obstacle_radius) 내 셀을 LETHAL_OBSTACLE(254)로 마킹
  }
};
```

**plugins.xml**:
```xml
<library path="peer_obstacle_layer">
  <class name="wego_obstacle_layer/PeerObstacleLayer"
         type="wego_obstacle_layer::PeerObstacleLayer"
         base_class_type="nav2_costmap_2d::Layer">
  </class>
</library>
```

### 4-2. domain bridge config 수정

각 로봇이 bridge 인스턴스 2개 실행:

**인스턴스 1** — 자기 domain → domain 5 (노트북):
```yaml
topics:
  /amcl_pose: { type: geometry_msgs/msg/PoseWithCovarianceStamped }
```

**인스턴스 2** — 자기 domain → 상대 robot domain:
```yaml
topics:
  /amcl_pose: { type: geometry_msgs/msg/PoseWithCovarianceStamped }
```

> /map, /tf, /tf_static 은 bridge 불필요. 맵은 scp 사전 배포 + 로컬 map_server.

launch 파일 인자: `peer_domain` (robot1→7, robot2→6)

### 4-3. `diff_navigation_params.yaml` 수정

```yaml
global_costmap:
  plugins: ["static_layer", "obstacle_layer", "wego_obstacle_layer", "inflation_layer"]
  wego_obstacle_layer:
    plugin: "wego_obstacle_layer/PeerObstacleLayer"
    peer_topic: "PEER_ROBOT_NAME/amcl_pose"   # launch 인자로 치환
    obstacle_radius: 0.3                       # 로봇 반경 0.2 + 여유 0.1
```

`local_costmap`에는 추가하지 않음 — 좁은 복도에서 DWB가 즉각 조향 시 진동(oscillation) 및 교착(deadlock) 발생 위험.

---

## 5. 포트폴리오 서술 요약

> "멀티로봇 충돌 회피를 위해 중앙집중식 FMS와 직접 구독 방식을 비교 검토했다. FMS는 O(N) 확장성의 장점이 있으나, 2대 규모에서 실익이 없고 충돌 회피의 단일 장애점이 된다는 문제가 있어 채택하지 않았다. 직접 구독 방식은 노트북 없이도 로봇 간 독립 동작이 가능하며 ROS2의 분산 철학에 부합한다. 구현 시 Nav2 costmap 루프와 ROS 콜백 쓰레드 간 공유 변수 접근에 mutex 대신 std::atomic을 사용해 lock-free 설계로 costmap 루프의 실시간성을 보장했다."
