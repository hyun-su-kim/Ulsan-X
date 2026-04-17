# NODE-TOPOLOGY — ROS 2 노드 및 토픽 구성

## Domain 구성

| 엔티티 | ROS_DOMAIN_ID | 역할 |
|--------|---------------|------|
| 리더 로봇 (LIMO 1) | **6** | 주 안내 로봇 |
| 서브 로봇 (LIMO 2) | **7** | 보조 안내 로봇 |
| 관제 노트북 | **5** | RViz 모니터링 |

Domain 간 통신은 `ros2-domain-bridge`로 필요한 토픽만 선택적으로 브릿징.
→ 설정 상세: [COMMUNICATION.md](COMMUNICATION.md)

---

## 노드 목록 (예정)

### wego 패키지 (기존)
| 노드 | 역할 |
|------|------|
| `/robot_base_node` | 하드웨어 드라이버 |
| `/cartographer_node` | SLAM 지도 작성 |

### wego_2d_nav 패키지 (기존)
| 노드 | 역할 |
|------|------|
| `/nav2_bringup` | Nav2 스택 (플래너, 컨트롤러, AMCL) |
| `/amcl` | 위치 추정 |

### wego_fleet 패키지 (신규)
| 노드 | 역할 |
|------|------|
| `/fleet_obstacle_node` | 상대 로봇 `/amcl_pose` 수신 → costmap 가상 장애물 발행 |

### wego_behaviour 패키지 (신규)
| 노드 | 역할 |
|------|------|
| `/behaviour_tree_node` | 최상단 BT 실행, 임무 상태 관리 |
| `/task_allocator_node` | 리더/서브 우선순위 임무 할당 |

### wego_voice 패키지 (신규)
| 노드 | 역할 |
|------|------|
| `/vad_node` | Silero VAD: 마이크 → 사람 목소리 필터 |
| `/wakeword_node` | openWakeWord: "헤이 리모" 감지 |
| `/stt_node` | faster-whisper (CUDA): 음성 → 텍스트 |
| `/nlu_node` | If-else / Gemini API / Gemma-2B 의도 해석 |
| `/tts_node` | Piper: 텍스트 → 음성 출력 |
| `/yolo_node` | YOLOv8: 카메라 → 사람 감지 + 방향 추정 |

---

## 주요 토픽

### 로봇 내부 (각 Domain 내)

| 토픽 | 타입 | 발행 | 구독 |
|------|------|------|------|
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | amcl | fleet_obstacle, task_allocator |
| `/cmd_vel` | `geometry_msgs/Twist` | nav2 controller | robot_base |
| `/scan` | `sensor_msgs/LaserScan` | LiDAR 드라이버 | cartographer, nav2 |
| `/voice/vad_active` | `std_msgs/Bool` | vad_node | wakeword_node |
| `/voice/wakeword_detected` | `std_msgs/Bool` | wakeword_node | behaviour_tree |
| `/voice/stt_result` | `std_msgs/String` | stt_node | nlu_node |
| `/voice/nlu_intent` | `wego_msgs/Intent` | nlu_node | behaviour_tree |
| `/voice/tts_request` | `std_msgs/String` | behaviour_tree | tts_node |
| `/vision/person_detected` | `std_msgs/Bool` | yolo_node | behaviour_tree |
| `/vision/person_direction` | `std_msgs/Float32` | yolo_node | behaviour_tree |
| `/robot/status` | `wego_msgs/RobotStatus` | behaviour_tree | task_allocator |

### 로봇 간 (Domain Bridge 경유)

| 토픽 | 방향 | 용도 |
|------|------|------|
| `/robot1/amcl_pose` | Robot1 → Robot2 | 서브가 리더 위치를 가상 장애물로 인식 |
| `/robot2/amcl_pose` | Robot2 → Robot1 | 리더가 서브 위치를 가상 장애물로 인식 |
| `/robot1/status` | Robot1 → Notebook | 관제 UI용 상태 모니터링 |
| `/robot2/status` | Robot2 → Notebook | 관제 UI용 상태 모니터링 |

> 브릿지 설정 상세: [COMMUNICATION.md](COMMUNICATION.md)

---

## TF 프레임 분리 전략 (구현 완료)

ROS2 namespace가 아닌 **TF frame ID prefix** 방식으로 로봇 구분 (DEC-005 참고).
각 로봇이 서로 다른 domain에서 동작하므로 토픽 이름 충돌 없음.
충돌이 생기는 건 노트북에서 `/tf`를 머지할 때뿐 → frame ID만 구분하면 충분.

```
map
├── robot1/odom → robot1/base_link → robot1/laser
│                                  → robot1/camera_mount → robot1/camera_rotate
│                                    → robot1_camera_link → robot1_camera_color_frame ...
└── robot2/odom → robot2/base_link → robot2/laser
                                   → robot2/camera_mount → ...
```

### TF 발행 노드 (teleop_launch.py 실행 시)

| 프레임 체인 | 발행 노드 |
|------------|---------|
| `robotN/odom → robotN/base_link` | EKF (`ekf_node`) |
| `robotN/base_link → robotN/laser` 등 | robot_state_publisher (frame_prefix) |
| `robotN/base_link → robotN/camera_mount → robotN/camera_rotate → robotN_camera_link` | static_transform_publisher (camera_tilt_launch.py) |
| `robotN_camera_link → robotN_camera_color_frame ...` | Orbbec camera node (camera_name=robotN_camera) |
| `map → robotN/odom` | AMCL (navigation_diff_launch.py) |
