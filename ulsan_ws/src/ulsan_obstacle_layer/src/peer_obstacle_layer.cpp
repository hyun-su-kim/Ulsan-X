#include "ulsan_obstacle_layer/peer_obstacle_layer.hpp"

#include <pluginlib/class_list_macros.hpp>

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <string>

using nav2_costmap_2d::LETHAL_OBSTACLE;

namespace ulsan_obstacle_layer
{

PeerObstacleLayer::PeerObstacleLayer()
: obstacle_radius_(0.35)
{}

PeerObstacleLayer::~PeerObstacleLayer() {}

void PeerObstacleLayer::onInitialize()
{
  // ----------------------------------------------------------------
  // 파라미터 선언 및 읽기
  // name_: Nav2가 yaml 키 이름으로 설정해주는 레이어 이름 ("ulsan_obstacle_layer")
  // 파라미터 전체 경로: "ulsan_obstacle_layer.peer_pose_topic"
  // ----------------------------------------------------------------
  declareParameter("peer_pose_topic", rclcpp::ParameterValue(std::string("")));
  declareParameter("obstacle_radius", rclcpp::ParameterValue(0.35));

  auto node = node_.lock();
  if (!node) {
    RCLCPP_ERROR(logger_, "[PeerObstacleLayer] node_.lock() 실패: 노드가 이미 소멸됨");
    return;
  }

  node->get_parameter(name_ + ".peer_pose_topic", peer_pose_topic_);
  node->get_parameter(name_ + ".obstacle_radius", obstacle_radius_);

  // ----------------------------------------------------------------
  // peer_topic 결정: yaml에 값이 있으면 그대로, 없으면 ROS_DOMAIN_ID로 자동 결정.
  // robot_bridge_launch.py의 DOMAIN_MAP과 동일한 매핑 규칙 사용:
  //   domain 6 (limo_1) → 상대방은 limo_2 → /limo_2/amcl_pose
  //   domain 7 (limo_2) → 상대방은 limo_1 → /limo_1/amcl_pose
  // domain bridge가 remap으로 /limo_N/amcl_pose 형태로 발행하므로 슬래시 포함.
  // ----------------------------------------------------------------
  if (peer_pose_topic_.empty()) {
    const char * env = std::getenv("ROS_DOMAIN_ID");
    if (env) {
      int domain = std::atoi(env);
      if (domain == 6) {
        peer_pose_topic_ = "/limo_2/amcl_pose";
      } else if (domain == 7) {
        peer_pose_topic_ = "/limo_1/amcl_pose";
      }
    }
  }

  if (peer_pose_topic_.empty()) {
    RCLCPP_ERROR(logger_,
      "[PeerObstacleLayer] peer_pose_topic을 결정할 수 없습니다. "
      "yaml에 peer_pose_topic을 지정하거나 ROS_DOMAIN_ID를 6 또는 7로 설정하세요.");
    return;
  }

  RCLCPP_INFO(logger_,
    "[PeerObstacleLayer] 초기화 완료 — 구독 토픽: %s, 장애물 반경: %.2f m",
    peer_pose_topic_.c_str(), obstacle_radius_);

  // ----------------------------------------------------------------
  // 구독 생성.
  // poseCallback은 ROS executor(Thread B)에서 메시지 수신 시 호출된다.
  // QoS depth 10: amcl_pose는 저주파(~1Hz) 발행이므로 큐 넘침 없음.
  // ----------------------------------------------------------------
  sub_ = node->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
    peer_pose_topic_,
    rclcpp::QoS(10),
    std::bind(&PeerObstacleLayer::poseCallback, this, std::placeholders::_1));

  // current_: 레이어가 최신 상태임을 Nav2에 알림. false면 Nav2가 재초기화 시도.
  current_ = true;
}

// ----------------------------------------------------------------
// Thread B (ROS executor) — amcl_pose 수신 시 호출
// ----------------------------------------------------------------
void PeerObstacleLayer::poseCallback(
  const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg)
{
  // atomic store: CPU 명령어 한 줄, 즉시 반환.
  // Thread A(costmap 루프)가 동시에 읽어도 블로킹 없음.
  peer_x_.store(msg->pose.pose.position.x, std::memory_order_relaxed);
  peer_y_.store(msg->pose.pose.position.y, std::memory_order_relaxed);
  // x, y 저장 후 valid 플래그 설정.
  // relaxed이므로 x, y보다 valid가 먼저 보일 수 있으나,
  // costmap이 매 프레임 재계산하므로 한 프레임 어긋나도 무방.
  peer_valid_.store(true, std::memory_order_relaxed);
}

// ----------------------------------------------------------------
// Thread A (Nav2 costmap update loop, 0.5Hz) — updateCosts() 직전 호출
// costmap 업데이트가 필요한 영역의 경계(bounding box)를 지정한다.
// 지정 범위 밖의 셀은 이번 프레임에서 updateCosts()가 호출되지 않아 연산 절약.
// ----------------------------------------------------------------
void PeerObstacleLayer::updateBounds(
  double /*robot_x*/, double /*robot_y*/, double /*robot_yaw*/,
  double * min_x, double * min_y,
  double * max_x, double * max_y)
{
  // 아직 상대 로봇 위치를 수신하지 못했으면 업데이트 범위 확장 불필요.
  if (!peer_valid_.load(std::memory_order_relaxed)) {
    return;
  }

  // atomic load: Thread B와 동시 접근 가능하지만 블로킹 없음.
  double px = peer_x_.load(std::memory_order_relaxed);
  double py = peer_y_.load(std::memory_order_relaxed);

  // 상대 로봇 위치 ± obstacle_radius_ 영역을 업데이트 범위에 포함.
  *min_x = std::min(*min_x, px - obstacle_radius_);
  *min_y = std::min(*min_y, py - obstacle_radius_);
  *max_x = std::max(*max_x, px + obstacle_radius_);
  *max_y = std::max(*max_y, py + obstacle_radius_);
}

// ----------------------------------------------------------------
// Thread A (Nav2 costmap update loop, 0.5Hz) — 실제 costmap 마킹
// ----------------------------------------------------------------
void PeerObstacleLayer::updateCosts(
  nav2_costmap_2d::Costmap2D & master_grid,
  int /*min_i*/, int /*min_j*/,
  int /*max_i*/, int /*max_j*/)
{
  // 아직 위치 수신 전이면 마킹 스킵.
  if (!peer_valid_.load(std::memory_order_relaxed)) {
    return;
  }

  // atomic load: x와 y를 별도로 읽으므로 이론상 서로 다른 콜백 프레임의 값일 수 있음.
  // costmap은 0.5Hz로 매 프레임 재계산되므로 한 프레임 어긋나도 다음 프레임에 정정됨.
  double px = peer_x_.load(std::memory_order_relaxed);
  double py = peer_y_.load(std::memory_order_relaxed);

  // ----------------------------------------------------------------
  // TF 변환 미포함.
  // amcl_pose는 map 프레임으로 발행, global_costmap의 global_frame도 map.
  // 프레임이 일치하므로 변환 불필요.
  //
  // local_costmap(global_frame: odom) 추가 시 아래 코드 삽입 필요:
  //   geometry_msgs::msg::PoseStamped pose_in, pose_out;
  //   pose_in.header.frame_id = "map";
  //   pose_in.pose.position.x = px;
  //   pose_in.pose.position.y = py;
  //   tf_->transform(pose_in, pose_out, layered_costmap_->getGlobalFrameID(),
  //                  tf2::durationFromSec(0.1));
  //   px = pose_out.pose.position.x;
  //   py = pose_out.pose.position.y;
  // ----------------------------------------------------------------

  // world 좌표(미터) → costmap 셀 인덱스 변환.
  // 맵 범위 밖이면 false 반환 → 마킹 스킵.
  unsigned int mx, my;
  if (!master_grid.worldToMap(px, py, mx, my)) {
    RCLCPP_WARN_THROTTLE(logger_, *clock_, 2000,
      "[PeerObstacleLayer] 상대 로봇 위치(%.2f, %.2f)가 맵 범위 밖입니다. "
      "맵이 올바르게 로드됐는지 확인하세요.", px, py);
    return;
  }

  // obstacle_radius_를 셀 단위로 환산.
  // resolution: 맵 1셀의 실제 크기(미터). diff_navigation_params.yaml: 0.05m
  double resolution = master_grid.getResolution();
  int radius_cells = static_cast<int>(obstacle_radius_ / resolution);

  // 상대 로봇 중심 ± radius_cells 정사각형 범위를 순회하며 원형으로 마킹.
  for (int dx = -radius_cells; dx <= radius_cells; ++dx) {
    for (int dy = -radius_cells; dy <= radius_cells; ++dy) {
      // 정사각형 루프에서 원 밖의 셀 제외 (원형 마킹).
      // std::hypot: 직각삼각형 빗변 계산. dx, dy 셀 거리 → 미터로 환산 후 비교.
      if (std::hypot(static_cast<double>(dx), static_cast<double>(dy)) * resolution
          > obstacle_radius_) {
        continue;
      }

      int nx = static_cast<int>(mx) + dx;
      int ny = static_cast<int>(my) + dy;

      // 맵 경계 초과 셀 스킵.
      if (nx < 0 || ny < 0 ||
          nx >= static_cast<int>(master_grid.getSizeInCellsX()) ||
          ny >= static_cast<int>(master_grid.getSizeInCellsY()))
      {
        continue;
      }

      // LETHAL_OBSTACLE(254): Nav2가 이 셀을 절대 통과 불가로 판단.
      // 전역 경로 플래너(NavFn/A*)가 이 영역을 우회하는 경로를 생성한다.
      master_grid.setCost(
        static_cast<unsigned int>(nx),
        static_cast<unsigned int>(ny),
        LETHAL_OBSTACLE);
    }
  }
}

void PeerObstacleLayer::reset()
{
  // 상대 로봇 위치 정보 초기화.
  // clear costmap 서비스 호출 또는 Nav2 재시작 시 이전 위치가 남지 않도록 초기화.
  peer_valid_.store(false, std::memory_order_relaxed);
}

bool PeerObstacleLayer::isClearable()
{
  // false 반환: 이 레이어는 clear costmap 서비스 대상에서 제외.
  // 상대 로봇 위치는 amcl_pose 실시간 수신으로 갱신되므로 수동 clear가 무의미.
  return false;
}

}  // namespace ulsan_obstacle_layer

// pluginlib에 클래스를 등록하는 매크로.
// 이 매크로 없이는 Nav2가 런타임에 클래스를 로드할 수 없음.
PLUGINLIB_EXPORT_CLASS(ulsan_obstacle_layer::PeerObstacleLayer, nav2_costmap_2d::Layer)
