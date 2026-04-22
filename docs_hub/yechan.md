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

---

## 11. Mutex vs Atomic vs Double Buffering — 멀티스레딩 동기화 방식 비교

### 전제: 왜 멀티스레딩이 문제인가

CPU는 명령어를 **레지스터에 올려서** 처리한다. 메모리에 있는 변수를 직접 수정하는 게 아니라:

```
메모리 → 레지스터 (load) → 연산 → 레지스터 → 메모리 (store)
```

이 과정이 **3단계**이기 때문에, 두 스레드가 동시에 같은 변수를 건드리면 문제가 생긴다.

```
double x = 1.0;

Thread A (콜백): x = 2.0;       Thread B (costmap): read x;
─────────────────────────────────────────────────────────────
A: load x → reg_A (값: 1.0)
                                 B: load x → reg_B (값: 1.0) ← 구값!
A: reg_A = 2.0
A: store reg_A → x (값: 2.0)
                                 B: 계산에 1.0 사용 → 오염
```

이게 **Data Race** (데이터 경쟁). 정의: 두 스레드가 동기화 없이 같은 메모리에 접근하고 그 중 하나 이상이 쓰기일 때. C++에서 Data Race는 **Undefined Behavior** — 프로그램이 아무렇게나 동작해도 됨.

---

### 방법 1 — Mutex (상호배제)

#### OS 레벨에서 무슨 일이 일어나나

Mutex는 **OS 커널이 관리하는 잠금**이다.

```
[스레드 A]                    [스레드 B]
lock(mtx)                     lock(mtx) ← 커널 호출
  → 커널: "A가 소유중"           → 커널: "B를 BLOCKED 상태로 전환"
  → A 실행 계속                   → B를 ready queue에서 제거
peer_x_ = new_x               (B는 CPU를 점유하지 않음)
peer_y_ = new_y
unlock(mtx)
  → 커널: "B 깨움"
  → B를 ready queue에 복귀      → B가 CPU 할당받아 실행 재개
                                lock 획득 → x, y 읽기
```

**핵심 메커니즘: Context Switch**

OS는 스레드를 sleep시킬 때 해당 스레드의 **레지스터 상태 전체를 메모리에 저장(save context)** 하고, 깨울 때 다시 복원(restore context)한다. 이 과정이 **수천 나노초** 단위 비용.

```
B가 block되는 순간:
  PC(Program Counter), SP(Stack Pointer), 범용 레지스터 16개 → 메모리에 저장
B가 깨어나는 순간:
  메모리 → 레지스터 복원 → 실행 재개
```

#### 코드

```cpp
std::mutex mtx_;
double peer_x_, peer_y_;

// Thread A (콜백)
void poseCallback(msg) {
    std::lock_guard<std::mutex> lock(mtx_);  // 커널 syscall
    peer_x_ = msg->pose.pose.position.x;
    peer_y_ = msg->pose.pose.position.y;
}  // unlock — 커널 syscall

// Thread B (costmap 루프)
void updateCosts(...) {
    std::lock_guard<std::mutex> lock(mtx_);  // A가 쓰는 중이면 여기서 BLOCK
    double px = peer_x_;
    double py = peer_y_;
}
```

#### 특성

| 항목 | 내용 |
|------|------|
| x, y 일관성 | 완벽 보장 (같은 lock 안에서 둘 다 씀) |
| 블로킹 | 발생 — B가 A를 기다림 |
| 비용 | Context Switch + 커널 syscall |
| costmap 루프 영향 | 타이밍 비결정적 — A가 늦으면 B도 늦음 |

---

### 방법 2 — std::atomic (원자적 연산)

#### CPU 레벨에서 무슨 일이 일어나나

atomic은 **OS를 전혀 거치지 않는다.** CPU 명령어 하나로 처리.

x86-64에서 `double` store/load는 정렬된 경우 자연적으로 원자적:

```asm
// peer_x_.store(2.0, relaxed)
MOVSD [peer_x_], xmm0      ; 64비트 한 번에 기록 — 찢기지 않음

// peer_x_.load(relaxed)
MOVSD xmm0, [peer_x_]      ; 64비트 한 번에 읽기 — 찢기지 않음
```

**"찢기지 않는다(no tearing)"** 가 핵심. `double`이 8바이트인데 CPU가 8바이트를 한 명령어로 처리하므로 중간 상태가 없음.

#### 그럼 Cache Coherence는?

멀티코어 CPU는 각 코어마다 **L1 Cache**가 있다. Thread A가 core 0에서, Thread B가 core 1에서 실행될 때:

```
Core 0 (Thread A)              Core 1 (Thread B)
┌─────────────────┐            ┌─────────────────┐
│  L1 Cache       │            │  L1 Cache       │
│  peer_x_ = 1.0  │            │  peer_x_ = 1.0  │  ← 캐시 복사본
└────────┬────────┘            └────────┬────────┘
         │                             │
         └──────────┬──────────────────┘
                    │
              L3 Cache / RAM
              peer_x_ = 1.0
```

A가 `peer_x_ = 2.0` 쓰면, **MESI 프로토콜**이 자동으로 Core 1의 캐시 라인을 무효화(Invalidate)하고 Core 1이 다음 읽기 시 최신값을 가져옴. atomic은 이 캐시 일관성을 보장.

#### memory_order_relaxed란?

`memory_order`는 **메모리 접근 순서 보장 수준**:

```
memory_order_seq_cst  ← 가장 강함, 모든 스레드에서 동일한 순서 보장
memory_order_acquire/release
memory_order_relaxed  ← 가장 약함, 원자성만 보장, 순서 보장 없음
```

`relaxed`의 의미:
```cpp
// Thread A
peer_x_.store(2.0, relaxed);   // ①
peer_y_.store(3.0, relaxed);   // ②

// Thread B에서 ①이 보인 시점에 ②가 안 보일 수 있음
// 즉 x=2.0, y=옛날값 조합이 가능
```

**왜 허용?** costmap은 10Hz로 계속 재계산. 한 프레임에 x, y가 1ms 어긋나도 다음 프레임에 맞춰짐. 로봇이 그 사이에 이동하는 거리 << obstacle_radius(0.3m).

#### 코드

```cpp
std::atomic<double> peer_x_{0.0};
std::atomic<double> peer_y_{0.0};
std::atomic<bool>   peer_valid_{false};

// Thread A — 블로킹 없이 즉시 저장
void poseCallback(msg) {
    peer_x_.store(msg->pose.pose.position.x, std::memory_order_relaxed);
    peer_y_.store(msg->pose.pose.position.y, std::memory_order_relaxed);
    peer_valid_.store(true, std::memory_order_relaxed);
}

// Thread B — 블로킹 없이 즉시 읽기
void updateCosts(...) {
    if (!peer_valid_.load(std::memory_order_relaxed)) return;
    double px = peer_x_.load(std::memory_order_relaxed);
    double py = peer_y_.load(std::memory_order_relaxed);
    // 마킹
}
```

#### 특성

| 항목 | 내용 |
|------|------|
| x, y 일관성 | 각각 원자적, 둘 사이 순서 보장 없음 |
| 블로킹 | 없음 — CPU 명령어 1개 |
| 비용 | ~1ns (캐시 히트 기준) |
| costmap 루프 영향 | 없음 |

---

### 방법 3 — Double Buffering (이중 버퍼)

#### 개념: Atomic으로도 해결 못하는 문제

Atomic은 **변수 하나**는 원자적이지만 **여러 변수를 묶어서** 원자적으로 처리할 수 없다.

```cpp
// x, y, theta 3개를 같은 순간의 값으로 읽어야 하는 상황
px = peer_x_.load();  // 프레임 N의 값
// ← 여기서 콜백이 새 pose를 저장하면?
py = peer_y_.load();  // 프레임 N+1의 값
th = peer_theta_.load(); // 프레임 N+1의 값
// px와 py, theta가 다른 프레임 — 일관성 깨짐
```

#### 해결책: 버퍼 2개 + 인덱스 swap

```cpp
struct Pose { double x, y, theta; };

Pose buffers_[2];               // 버퍼 2개
std::atomic<int> read_idx_{0};  // B가 읽는 버퍼 인덱스
```

```
초기 상태:
buffers_[0] = {x:1, y:1, t:0}  ← Thread B가 읽는 중 (read_idx_=0)
buffers_[1] = {x:0, y:0, t:0}  ← 비어있음 (write_idx = 1)

Thread A가 새 pose 받으면:
1. write_idx = 1 - read_idx_  → write_idx = 1
2. buffers_[1] = {x:2, y:2, t:0.1}  (쓰기, 읽기 버퍼에 손 안 댐)
3. read_idx_.store(1, release)  → swap! B는 이제 buffers_[1]을 읽음

Thread B:
int idx = read_idx_.load(acquire);
Pose p = buffers_[idx];  // 완성된 스냅샷, 일관성 보장
```

**핵심**: A가 쓰는 동안 B는 다른 버퍼를 읽음 → 둘이 같은 버퍼를 동시에 쓰고 읽는 일이 없음.

여기서 `memory_order_release` / `acquire` 쌍이 중요:

```
A: buffers_[1] = {...}          (쓰기)
A: read_idx_.store(1, release)  ← "이 시점 이전 모든 쓰기를 B에게 보장"

B: read_idx_.load(acquire)      ← "release 이전 모든 쓰기가 여기서 보임"
B: Pose p = buffers_[idx]       (완성된 데이터 읽기 보장)
```

#### 특성

| 항목 | 내용 |
|------|------|
| x, y, theta 일관성 | 완벽 보장 (스냅샷 단위) |
| 블로킹 | 없음 — 버퍼만 교체 |
| 비용 | atomic 인덱스 swap 1회 + struct 복사 |
| 단점 | 버퍼 2개 메모리, 구현 복잡도 |

---

### 3가지 비교 총정리

```
[공유 변수에 두 스레드가 접근]
              │
              ▼
    여러 필드를 스냅샷으로 읽어야 하나?
       │                    │
      YES                   NO
       │                    │
  블로킹 허용?         단일 값(double 등)
    │        │                 │
   YES       NO            → Atomic (relaxed)
    │        │               CPU 명령어 1개
  Mutex   Double             OS 없음
  OS 관리  Buffering          ~1ns
  확실한   Lock-free
  일관성   스냅샷 보장
  Context  구현 복잡
  Switch
  ~수μs
```

| 상황 | 선택 | 이유 |
|------|------|------|
| 실시간 루프 + 단순 좌표 공유 | **Atomic** | 블로킹 없음, 충분한 일관성 |
| 실시간 루프 + 멀티 필드 스냅샷 필요 | **Double Buffering** | Lock-free + 일관성 |
| 실시간성 불필요 + 완벽한 일관성 | **Mutex** | 단순, 확실 |
| 이 프로젝트 (x, y만, 오차 허용) | **Atomic** | 가장 단순하고 충분 |

**면접 한 줄 요약**: Mutex는 OS가 스레드를 재우고 깨우는 비용이 있고, Atomic은 CPU 명령어 하나로 처리해 블로킹이 없으며, Double Buffering은 Atomic을 확장해 멀티 필드를 스냅샷 단위로 교체함으로써 일관성과 Lock-free를 동시에 얻는 기법.

---

## 12. 멀티로봇 충돌 회피 설계 — 방식 비교 및 채택 근거

### 검토했던 방식과 채택하지 않은 이유

#### 중앙집중식 FMS (Fleet Management System)
노트북의 FMS 노드가 모든 로봇 pose를 수집해 배열 토픽으로 묶어 발행.

**채택하지 않은 이유**:
- 2대 규모에서 O(N²) vs O(N) 차이 없음
- 노트북이 꺼지면 충돌 회피 자체 불가 → 단일 장애점(SPOF)
- ROS2가 분산 구조를 제공하는데 FMS로 중앙 의존성을 애플리케이션 레벨에서 재도입하는 셈

#### 직접 구독 + Mutex
각 로봇이 상대방 amcl_pose를 직접 구독, mutex로 동기화.

**채택하지 않은 이유**:
- costmap 루프(0.5Hz)가 콜백 스레드의 mutex 해제를 기다리며 블로킹 → 0.5Hz 보장 불가
- 친구 코드에서 `has_pose_`를 lock 없이 읽는 버그도 발생

### 채택한 방식 — 직접 구독 + std::atomic

| 기준 | 이유 |
|------|------|
| 규모 | 2대에서 O(N²) 부하 없음 |
| 안정성 | 노트북 없이도 로봇끼리 직접 pose 수신 |
| 단순성 | FMS 노드, 배열 메시지, 전환 로직 불필요 |
| ROS2 철학 | 각 로봇이 자율적으로 동작, 중앙 의존성 없음 |
| 실시간성 | atomic으로 costmap 루프 블로킹 없음 |

---

## 13. Nav2 Layer 인터페이스

Nav2가 costmap 플러그인에게 요구하는 함수 목록. Nav2가 정해진 타이밍에 호출한다.

```cpp
onInitialize()   // 플러그인 처음 로드될 때 한 번 호출
                 // → 구독 설정, 파라미터 읽기

updateBounds()   // costmap 업데이트 직전 호출 (최적화용)
                 // → "이 범위만 업데이트할 거야" 영역 지정
                 // → 지정 범위 밖 셀은 이번 프레임 updateCosts() 호출 안 함

updateCosts()    // 실제 costmap 셀에 값 쓰는 곳
                 // → LETHAL_OBSTACLE(254) 마킹

reset()          // clear costmap 서비스 또는 재시작 시 호출
isClearable()    // clear costmap 서비스 대응 여부 반환
```

Nav2 costmap 루프 순서:
```
onInitialize()
    ↓
[updateBounds() → updateCosts()] 반복 (0.5Hz, costmap_thread_)
```

### updateBounds vs updateCosts 역할 구분

- `updateBounds()`: 이번 프레임에서 업데이트가 필요한 영역의 bounding box를 지정. 연산 최적화용.
- `updateCosts()`: 실제로 costmap 셀에 LETHAL_OBSTACLE 값을 기록.

updateBounds를 비워두면 전체 맵을 매번 업데이트하므로 범위를 좁혀주는 게 성능상 좋다.

---

## 14. peer_valid_ 가 필요한 이유

`peer_x_`, `peer_y_`는 초기값 `0.0`으로 시작한다. 그런데 `(0.0, 0.0)`은 맵 상의 실제 유효한 좌표다.

```
상황 1: 아직 amcl_pose를 한 번도 못 받음
  peer_x_ = 0.0, peer_y_ = 0.0  ← 초기값일 뿐

상황 2: 상대 로봇이 실제로 (0.0, 0.0)에 있음
  peer_x_ = 0.0, peer_y_ = 0.0  ← 실제 위치
```

`peer_valid_` 없이는 이 두 상황을 구별할 수 없다.
결과적으로 로봇 시작 직후 맵 원점에 가짜 장애물이 마킹된다.

```cpp
// peer_valid_ = false → 아직 수신 전, 마킹 안 함
// peer_valid_ = true  → 실제 위치 수신됨, 마킹
if (!peer_valid_.load(std::memory_order_relaxed)) return;
```

---

## 15. TF 프레임과 좌표 변환

### 프레임 = 기준 좌표계

RViz의 fixed frame과 동일한 개념. TF가 프레임들 사이의 관계를 관리한다.

```
map → odom → base_link

map:       전역 고정 좌표계. AMCL이 맵 기준으로 로봇 위치 계산.
odom:      주행거리계 기반. 시간이 지나면 누적 오차로 map과 어긋남.
base_link: 로봇 본체 중심.
```

`amcl_pose`는 항상 `map` 프레임으로 발행된다 = "맵 원점 기준으로 로봇이 x=1.5, y=2.3에 있다".

### costmap과 TF 변환의 관계

```
global_costmap → global_frame: map
  amcl_pose(map 프레임)와 같은 프레임 → 변환 불필요

local_costmap → global_frame: odom
  amcl_pose(map 프레임)와 다른 프레임 → map→odom TF 변환 필요
```

우리 프로젝트는 global_costmap에만 플러그인을 추가하므로 TF 변환 불필요.
local_costmap 추가 시 `tf_->transform(pose_in, pose_out, "odom", ...)` 삽입 필요.

---

## 16. pluginlib 등록 방식

Nav2가 플러그인을 인식하는 3단계 구조.

### 1단계 — plugins.xml

클래스 정보 등록. Nav2가 이 파일을 읽어 어떤 클래스가 존재하는지 파악한다.

```xml
<library path="peer_obstacle_layer">  <!-- CMakeLists의 target 이름과 일치 -->
  <class
    name="ulsan_obstacle_layer/PeerObstacleLayer"  <!-- yaml의 plugin: 값 -->
    type="ulsan_obstacle_layer::PeerObstacleLayer" <!-- 실제 C++ 클래스 -->
    base_class_type="nav2_costmap_2d::Layer">
  </class>
</library>
```

### 2단계 — CMakeLists.txt

```cmake
# SHARED 필수: pluginlib이 dlopen()으로 런타임 로드하므로
add_library(peer_obstacle_layer SHARED src/peer_obstacle_layer.cpp)

# ament index에 등록: Nav2가 부팅 시 이 파일을 검색해 플러그인 목록 파악
pluginlib_export_plugin_description_file(nav2_costmap_2d plugins.xml)
```

### 3단계 — C++ 파일 맨 아래

```cpp
// 이 매크로 없으면 Nav2가 런타임에 클래스를 로드할 수 없음
PLUGINLIB_EXPORT_CLASS(ulsan_obstacle_layer::PeerObstacleLayer, nav2_costmap_2d::Layer)
```

### 등록 흐름 요약

```
colcon build
    → ament index에 plugins.xml 경로 등록

Nav2 실행
    → yaml에서 plugin: "ulsan_obstacle_layer/PeerObstacleLayer" 읽음
    → ament index 검색 → plugins.xml 발견
    → dlopen("libpeer_obstacle_layer.so")
    → PLUGINLIB_EXPORT_CLASS 매크로로 등록된 클래스 인스턴스 생성
    → onInitialize() 호출
```

---

## 17. worldToMap — 좌표 변환

`amcl_pose`는 미터 단위 world 좌표. costmap은 셀 인덱스로 동작.

```
amcl_pose: x=1.5m, y=2.3m
    ↓ worldToMap()
costmap 셀: mx=30, my=46  (resolution=0.05m 기준)
```

```cpp
unsigned int mx, my;
if (!master_grid.worldToMap(px, py, mx, my)) {
    // 맵 범위 밖이면 false 반환 → 마킹 스킵
    return;
}
```

### 원형 마킹 로직

worldToMap으로 얻은 셀 중심에서 반경 내 셀을 LETHAL_OBSTACLE로 마킹.
정사각형 루프를 돌며 원 밖 셀은 hypot으로 제외.

```cpp
int radius_cells = static_cast<int>(obstacle_radius_ / resolution);

for (int dx = -radius_cells; dx <= radius_cells; ++dx) {
  for (int dy = -radius_cells; dy <= radius_cells; ++dy) {
    // 정사각형 루프에서 원 밖 셀 제외
    if (std::hypot((double)dx, (double)dy) * resolution > obstacle_radius_) continue;

    master_grid.setCost(mx + dx, my + dy, LETHAL_OBSTACLE);
  }
}
```

```
□□□□□□□
□□■■■□□
□■■■■■□   ■ = LETHAL_OBSTACLE(254)
□■■●■■□   ● = 상대 로봇 위치 (mx, my)
□■■■■■□
□□■■■□□
□□□□□□□
```

---

## 18. ulsan_obstacle_layer 패키지 최종 구조

### 파일 구성

```
ulsan_ws/src/ulsan_obstacle_layer/
├── CMakeLists.txt          # 빌드 설정, pluginlib 등록
├── package.xml             # 의존성 선언
├── plugins.xml             # Nav2 플러그인 등록 정보
├── include/ulsan_obstacle_layer/
│   └── peer_obstacle_layer.hpp   # 클래스 선언, 스레드 모델 설명
└── src/
    └── peer_obstacle_layer.cpp   # 구현
```

### 스레드 모델 요약

```
Thread A (Nav2 costmap_thread_, 0.5Hz)   Thread B (ROS executor)
────────────────────────────────         ──────────────────────────
updateBounds() 호출                      poseCallback() 호출
  peer_valid_.load()  ← 읽기              peer_x_.store(x)   ← 쓰기
updateCosts() 호출                        peer_y_.store(y)   ← 쓰기
  peer_x_.load()      ← 읽기              peer_valid_.store(true) ← 쓰기
  peer_y_.load()      ← 읽기
  worldToMap → LETHAL 마킹
```

- 스레드를 직접 만들지 않음. Nav2와 ROS2가 이미 돌리고 있는 두 스레드 사이의 공유 변수만 안전하게 처리.
- `std::atomic`으로 lock-free 동기화 → Thread A의 0.5Hz 보장.

### peer_topic 자동 결정 규칙

```
ROS_DOMAIN_ID=6 (limo_1) → /limo_2/amcl_pose 구독
ROS_DOMAIN_ID=7 (limo_2) → /limo_1/amcl_pose 구독
```

yaml에 `peer_pose_topic`을 직접 지정하면 env 무시. 비워두면 env 자동 결정.
robot_bridge_launch.py의 DOMAIN_MAP과 동일한 매핑 규칙.

### 친구 구현(Mutex)과 비교

| 항목 | 친구 (wego_fleet, mutex) | 우리 (ulsan_obstacle_layer, atomic) |
|------|--------------------------|--------------------------------------|
| has_pose_ 동기화 | 버그 (lock 없이 읽음) | atomic으로 해결 |
| costmap 루프 블로킹 | 발생 가능 | 없음 |
| TF 변환 | 포함 (방어적 코드) | 미포함 (주석으로 추후 추가 방법 명시) |
| peer_topic 유연성 | yaml + env 둘 다 지원 | yaml + env 둘 다 지원 |
