# 학습 정리 — wego_fleet & ROS2 실행 구조

---

## 1. wego_fleet 패키지

### 역할
domain_bridge로 수신한 상대 로봇의 `amcl_pose`를 Nav2 global costmap에 원형 가상 장애물로 주입하는 **커스텀 costmap 레이어 플러그인**.

### 핵심 설계

- `nav2_costmap_2d::Layer`를 상속받아 pluginlib으로 Nav2에 등록
- 센서(LaserScan, PointCloud2) 없이 **pose만으로** costmap에 장애물 주입
- `pose_topic`, `obstacle_radius`, `stale_timeout` 파라미터로 외부 주입 가능

### 동작 흐름

```
robot2 (Domain 1)  →  domain_bridge  →  robot1 (Domain 0)
/amcl_pose                               robot2/amcl_pose
                                              ↓
                                     poseCallback() 수신
                                              ↓
                              updateBounds() — 마킹 범위 예약
                              updateCosts()  — LETHAL_OBSTACLE(254) 마킹
                                              ↓
                                    planner가 해당 셀 회피
```

### global costmap에만 넣는 이유

local costmap에도 넣으면 DWB controller가 즉각 조향을 시도해서 좁은 복도에서 **진동(oscillation)** 및 **교착(deadlock)** 발생 위험이 있다.
학원 환경에서 두 로봇은 예측 가능하게 이동하고 갑작스러운 등장이 없으므로 global re-plan 주기(0.5Hz, 약 2초) 지연이 허용 가능하다.

### diff_navigation_params.yaml 변경 내용

```yaml
# global_costmap
plugins: ["static_layer", "obstacle_layer", "fleet_obstacle_layer", "inflation_layer"]

fleet_obstacle_layer:
  plugin: "wego_fleet/FleetObstacleLayer"
  pose_topic: "robot2/amcl_pose"
  obstacle_radius: 0.3
  stale_timeout: 2.0
```

---

## 2. 스레드(Thread)

### 개념

**스레드 = 코드를 실행하는 독립적인 일꾼**

프로그램은 기본적으로 메인 스레드 1개로 시작한다.
스레드를 여러 개 만들면 코드가 **동시에** 실행된다.

```
스레드 1 ──────────────────────→  A 실행 → B 실행
스레드 2 ──────────────────────→  C 실행 → D 실행
              ↑ 동시에 실행
```

---

## 3. Race Condition (경쟁 상태)

두 스레드가 **같은 변수**에 동시에 접근할 때 값이 섞이는 문제.

```
스레드 A (poseCallback)        스레드 B (updateCosts)
──────────────────────         ──────────────────────
other_x_ = 3.0  ✓ 완료
                               other_x_ 읽음 → 3.0  ✓
other_y_ = 5.0  아직 진행중
                               other_y_ 읽음 → 0.0  ✗ (이전 값!)
```

x는 새 값, y는 이전 값이 섞여 **엉뚱한 위치에 장애물이 마킹**된다.

---

## 4. Mutex (뮤텍스)

**Mutex = 자물쇠**

한 번에 한 스레드만 공유 변수에 접근하도록 막는다.
자물쇠가 잠겨있으면 다른 스레드는 열릴 때까지 대기한다.

```
스레드 A (poseCallback)        스레드 B (updateCosts)
──────────────────────         ──────────────────────
🔒 자물쇠 잠금
other_x_ = 3.0
other_y_ = 5.0
🔓 자물쇠 열기
                               🔒 자물쇠 잠금 (A가 열어줄 때까지 대기)
                               other_x_ 읽음 → 3.0  ✓
                               other_y_ 읽음 → 5.0  ✓
                               🔓 자물쇠 열기
```

C++ 코드에서는 `lock_guard`를 사용하면 스코프가 끝날 때 자동으로 자물쇠가 열린다.

```cpp
std::lock_guard<std::mutex> lock(pose_mutex_);  // 🔒 잠금
other_x_ = msg->pose.pose.position.x;
other_y_ = msg->pose.pose.position.y;
// 스코프 끝 → 🔓 자동으로 열림
```

---

## 5. 프로세스 vs 스레드

| 구분 | 프로세스 | 스레드 |
|------|----------|--------|
| 메모리 | 독립적 (분리됨) | 공유 (같은 프로세스 안) |
| 통신 방법 | DDS 네트워크 (직렬화/역직렬화) | 변수 직접 접근 |
| 속도 | 느림 | 빠름 |
| 위험 | - | Race Condition → Mutex 필요 |

```
┌─────────────────── 프로세스 A ───────────────────┐
│  메모리 공간 (공유)                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ 스레드 1  │  │ 스레드 2  │  │ 스레드 3  │       │
│  └──────────┘  └──────────┘  └──────────┘        │
└──────────────────────────────────────────────────┘
          ↕ DDS 네트워크 통신
┌─────── 프로세스 B ───────┐
│  독립된 메모리 공간       │
│  ┌──────────┐            │
│  │ 스레드 1  │            │
│  └──────────┘            │
└──────────────────────────┘
```

---

## 6. ROS2 OS 관점 실행 방식 — 전체 구조

### 프로세스 생성

`ros2 run` 또는 `ros2 launch`를 치면 OS가 프로세스를 만든다.

```
ros2 run my_pkg my_node
         ↓
OS: fork() + exec()
         ↓
새 프로세스 생성
├── 독립된 가상 주소 공간 (힙, 스택, 코드 영역)
├── 파일 디스크립터 (소켓 등)
└── 메인 스레드 1개 (OS가 자동 생성)
```

`ros2 launch`는 런치 프로세스 1개가 뜨고, `Node()` 마다 자식 프로세스를 fork한다.  
`ComposableNodeContainer`로 묶은 것만 프로세스 1개를 공유.

```
ros2 launch (PID 100)  ← 런치 프로세스 (보모 역할)
  ├── my_node_a  (PID 101)  ← Node() → 별도 프로세스
  ├── my_node_b  (PID 102)  ← Node() → 별도 프로세스
  └── nav2_container (PID 103)  ← ComposableNodeContainer → 프로세스 1개
        ├── AmclNode      (스레드, dlopen으로 로드)
        └── PlannerServer (스레드, dlopen으로 로드)
```

### 프로세스 내부 — main()부터 spin()까지

```
프로세스 (my_node, PID 101)
└── 메인 스레드  ← OS가 자동 생성. main()부터 여기서 실행.
      ├── rclpy.init()       DDS 초기화, 소켓 준비
      ├── node = MyNode()    노드 객체 생성
      │     └── 구독/타이머/서비스 등록
      │           "이 이벤트가 오면 이 콜백을 실행해줘" 예약만 함
      │           이 시점에 콜백은 실행되지 않음
      └── rclpy.spin(node)   메인 스레드가 Executor 루프로 전환
```

### Executor — 객체이지 스레드가 아니다

`Executor`는 이벤트 루프 로직을 담은 **객체(클래스 인스턴스)** 다.  
`spin(node)` 한 줄이 내부적으로 하는 일:

```python
# rclpy.spin(node) 실제 내부
executor = SingleThreadedExecutor()   # Executor 객체 생성 (스레드 아님)
executor.add_node(node)               # 노드 등록
executor.spin()                       # 호출한 스레드(메인)가 루프로 진입
```

`spin()`을 호출한 메인 스레드가 아래 루프를 돈다.

```
메인 스레드 (Executor 루프로 전환됨)
─────────────────────────────────────────────────
while 노드가 살아있는 동안:

    epoll_wait()         ← OS 시스템 콜
                           이벤트 없으면 메인 스레드 SLEEP (CPU 반납)
                           이벤트 오면 OS가 메인 스레드 WAKE

    콜백 목록 확인        ← 지금 실행 가능한 콜백 조회

    scan_callback() 실행  ← 완료될 때까지 다음 콜백 대기
    pose_callback() 실행  ← 완료될 때까지 다음 콜백 대기
─────────────────────────────────────────────────
```

`spin()` 이후 코드는 Ctrl+C 전까지 실행되지 않는다.

### 콜백이 실행되는 전체 경로

콜백은 "이벤트 발생 시 Executor가 호출하는 일반 함수"다.  
비동기처럼 보이지만 실제로는 메인 스레드가 적절한 타이밍에 직접 호출하는 것.

```
[다른 프로세스]
  /scan 토픽 publish
        ↓ UDP 소켓 (DDS)
[현재 프로세스]
  DDS 수신 스레드 (CycloneDDS 내부 자동 생성)
    UDP 소켓 read()
    → DDS 내부 수신 큐에 메시지 적재
    → epoll fd에 신호
        ↓
  메인 스레드 (Executor 루프)
    epoll_wait() 반환  ← OS가 깨움
    → DDS 큐에서 메시지 꺼냄 (take) → 역직렬화
    → scan_callback(msg) 호출  ← 사용자 코드 실행
```

### 콜백을 쓰는 이유 — 이벤트 구동

콜백은 비동기 처리가 목적이 아니라 **이벤트 구동(event-driven)** 이 목적이다.

```python
# 콜백 없이 짠다면 — 폴링 방식 (비효율)
while True:
    msg = topic.read()   # 왔나? 안 왔나? 계속 확인
    if msg:
        process(msg)
    time.sleep(0.01)     # CPU 낭비 또는 반응 지연

# 콜백 방식 — 이벤트 구동 (효율적)
node.create_subscription(Topic, '/scan', my_callback, 10)
rclpy.spin(node)   # 이벤트 없으면 SLEEP, 오면 콜백 실행
```

언제 올지 모르는 이벤트를 폴링 없이 처리하는 것이 핵심.

### 개념 정리표

| 개념 | 실체 | 역할 |
|------|------|------|
| 프로세스 | OS가 생성한 독립 실행 단위 | 독립된 메모리 공간 |
| 메인 스레드 | OS가 프로세스 생성 시 자동 생성 | main()부터 코드 실행 |
| Executor | 객체 (클래스 인스턴스) | 이벤트 루프 로직 담당 |
| spin() | Executor의 루프 진입점 | 호출한 스레드를 루프로 전환 |
| 콜백 | 일반 함수 | 이벤트 발생 시 Executor가 호출 |
| DDS 수신 스레드 | CycloneDDS 내부 자동 생성 | 소켓 수신 → 내부 큐 적재 |
| epoll_wait() | OS 시스템 콜 | 이벤트 없으면 스레드 SLEEP, 오면 WAKE |

### 프로세스 간 통신 vs 프로세스 내 통신

| | 방식 | 속도 |
|--|------|------|
| 별도 프로세스 (Node) | DDS UDP 소켓 — 직렬화/역직렬화 | 느림 |
| 같은 프로세스 (ComposableNode) | 포인터 전달 (zero-copy) | 빠름 |

---

## 7. rclcpp vs rclpy

| 구분 | rclcpp | rclpy |
|------|--------|-------|
| 언어 | C++ | Python |
| rcl 접근 | 직접 링크 (C++ → C) | ctypes/cffi로 rcl 바인딩 |
| 스레드 | OS 네이티브 스레드 (`std::thread`) | Python 스레드 (`threading.Thread`) |
| 병렬 실행 | 진짜 병렬 (멀티코어) | GIL 때문에 제한적 |
| zero-copy | 지원 (intra-process) | 미지원 |
| 실시간성 | 가능 | 불가 (GC 멈춤 발생) |

**GIL(Global Interpreter Lock)**: Python은 한 번에 하나의 스레드만 Python 코드 실행 가능.  
CPU 바운드 작업에서 rclpy MultiThreadedExecutor는 진짜 병렬화 안 됨.  
단, `epoll_wait()` 같은 시스템 콜은 C 레벨에서 실행되므로 GIL 해제 → I/O 대기 중엔 다른 스레드 실행 가능.

**계층 구조**:
```
사용자 코드 (rclpy / rclcpp API)
      ↑
    rcl (C 공통 레이어)
      ↑
    rmw (ROS Middleware Interface — 추상화)
      ↑
    rmw_cyclonedds (실제 DDS 구현)
      ↑
    OS 소켓 (UDP) / 공유 메모리
```

rclcpp와 rclpy 모두 rcl(C 공통 레이어)을 감싼 래퍼다.

---

## 8. Nav2 costmap_thread_

**위치**: `nav2_costmap_2d/src/costmap_2d_ros.cpp` (Nav2 소스코드 내부)

**역할**: costmap 갱신을 전담하는 별도 스레드. ROS2 Executor와 독립적으로 동작.

```cpp
// Nav2 내부 코드
void Costmap2DROS::activate()
{
  costmap_thread_ = std::make_unique<std::thread>(
    &Costmap2DROS::mapUpdateLoop, this);  // 별도 스레드 생성
}

void Costmap2DROS::mapUpdateLoop()
{
  while (rclcpp::ok()) {
    updateMap();   // 모든 레이어의 updateBounds() → updateCosts() 호출
    rate.sleep();  // 0.5Hz 대기
  }
}
```

---

## 9. Nav2 Composable Node 구조

### 기존 방식 vs Composable Node 방식

**기존**: 노드마다 프로세스 1개 → DDS 네트워크 통신 필요

**Composable Node**: 여러 노드를 컨테이너(프로세스 1개)에 로드 → 공유 메모리(zero-copy) 통신

### nav2_container 구조

```
┌──────────────── nav2_container (프로세스 1개) ────────────────────┐
│                                                                   │
│  planner_server   controller_server   bt_navigator   costmap_2d  │
│  (스레드)          (스레드)             (스레드)       (스레드)    │
│                                                                   │
│  → 서로 공유 메모리로 직접 접근 (zero-copy, 네트워크 통신 없음)      │
└───────────────────────────────────────────────────────────────────┘
```

Nav2 서버들(planner_server, controller_server 등)은 모두 **하나의 프로세스 안에서 스레드로 동작**한다.

### 우리 코드에서 이미 쓰고 있는 부분

```python
# localization_launch.py
LoadComposableNodes(
    target_container='nav2_container',        # 프로세스 1개
    composable_node_descriptions=[
        ComposableNode(plugin='nav2_map_server::MapServer'),   # 스레드
        ComposableNode(plugin='nav2_amcl::AmclNode'),          # 스레드
        ComposableNode(plugin='nav2_lifecycle_manager::...'),  # 스레드
    ]
)
```

---

## 10. 왜 mutex가 필요한가 — 최종 연결

```
nav2_container (프로세스 1개)
├── ROS2 Executor 스레드
│     → robot2/amcl_pose 수신 시 poseCallback() 실행
│     → other_x_, other_y_ 쓰기
│
└── costmap_thread_ (Nav2가 별도 생성)
      → 0.5Hz로 updateBounds(), updateCosts() 실행
      → other_x_, other_y_ 읽기
```

같은 프로세스 안의 두 스레드가 `other_x_`, `other_y_`라는 **같은 메모리**에 동시 접근한다.
→ Race Condition 발생 가능
→ `pose_mutex_`로 보호 필요
