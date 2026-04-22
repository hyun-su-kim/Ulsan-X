#pragma once

#include <atomic>
#include <string>

#include <nav2_costmap_2d/layer.hpp>
#include <nav2_costmap_2d/layered_costmap.hpp>
#include <geometry_msgs/msg/pose_with_covariance_stamped.hpp>
#include <rclcpp/rclcpp.hpp>

namespace ulsan_obstacle_layer
{

/**
 * @brief 상대 로봇 amcl_pose를 global costmap에 LETHAL_OBSTACLE로 마킹하는 Nav2 Layer 플러그인.
 *
 * [스레드 모델]
 *   Thread A (Nav2 costmap update loop, 0.5Hz)
 *     → updateBounds(), updateCosts() 호출
 *     → peer_x_, peer_y_, peer_valid_ 읽기
 *
 *   Thread B (ROS executor)
 *     → poseCallback() 호출 (amcl_pose 수신 시)
 *     → peer_x_, peer_y_, peer_valid_ 쓰기
 *
 *   두 스레드가 공유 변수에 동시 접근하므로 동기화 필요.
 *   mutex 대신 std::atomic 사용: Thread A가 mutex 해제를 기다리지 않으므로
 *   costmap 루프 0.5Hz 보장.
 *
 * [TF 변환]
 *   현재 global_costmap(map 프레임)에만 적용하므로 TF 변환 불필요.
 *   amcl_pose도 map 프레임으로 발행되어 프레임이 일치한다.
 *   local_costmap(odom 프레임) 추가 시 tf_->transform()으로 map→odom 변환 필요.
 */
class PeerObstacleLayer : public nav2_costmap_2d::Layer
{
public:
  PeerObstacleLayer();
  ~PeerObstacleLayer() override;

  /**
   * @brief 플러그인 초기화. Nav2가 레이어 로드 시 한 번 호출.
   *        파라미터 선언, peer_topic 결정, 구독 생성.
   */
  void onInitialize() override;

  /**
   * @brief costmap 업데이트 범위 지정. updateCosts() 직전에 호출.
   *        상대 로봇 위치 ± obstacle_radius_ 영역만 업데이트 대상으로 지정해 연산 최소화.
   */
  void updateBounds(
    double robot_x, double robot_y, double robot_yaw,
    double * min_x, double * min_y,
    double * max_x, double * max_y) override;

  /**
   * @brief 실제 costmap 셀에 LETHAL_OBSTACLE(254) 마킹. Thread A에서 0.5Hz로 호출.
   *        peer_valid_ 확인 → 좌표 읽기 → worldToMap 변환 → 반경 내 셀 마킹.
   */
  void updateCosts(
    nav2_costmap_2d::Costmap2D & master_grid,
    int min_i, int min_j,
    int max_i, int max_j) override;

  /**
   * @brief 레이어 상태 초기화. clear costmap 서비스 호출 시 또는 재시작 시 사용.
   */
  void reset() override;

  /**
   * @brief clear costmap 서비스로 이 레이어를 지울 수 있는지 여부.
   *        false 반환: 상대 로봇은 실시간 위치 기반이므로 수동 clear 대상 아님.
   */
  bool isClearable() override;

private:
  /**
   * @brief 상대 로봇 amcl_pose 수신 콜백. Thread B(ROS executor)에서 호출.
   *        수신한 x, y 좌표를 atomic에 저장하고 peer_valid_를 true로 설정.
   */
  void poseCallback(
    const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg);

  // ------------------------------------------------------------------
  // 공유 변수 — Thread A(읽기)와 Thread B(쓰기)가 동시 접근
  // std::atomic으로 lock-free 동기화. mutex 없이 CPU 명령어 한 줄로 처리.
  // memory_order_relaxed: x, y 간 순서 보장 불필요.
  //   costmap은 매 프레임 재계산하므로 x와 y가 서로 다른 콜백 프레임의
  //   값이어도 다음 프레임에 정정되어 문제없음.
  // ------------------------------------------------------------------

  // 상대 로봇의 map 프레임 x 좌표 (미터)
  std::atomic<double> peer_x_{0.0};
  // 상대 로봇의 map 프레임 y 좌표 (미터)
  std::atomic<double> peer_y_{0.0};
  // amcl_pose를 한 번이라도 수신했는지 여부.
  // 초기값 (0.0, 0.0)은 유효한 맵 좌표일 수 있으므로
  // 좌표값만으로 수신 여부를 판단할 수 없어 별도 플래그 필요.
  std::atomic<bool>   peer_valid_{false};

  // amcl_pose 구독자
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr sub_;

  // 구독할 토픽명: yaml peer_pose_topic 파라미터 또는 ROS_DOMAIN_ID로 자동 결정
  std::string peer_pose_topic_;
  // costmap에 LETHAL로 마킹할 원형 반경 (미터). yaml obstacle_radius 파라미터.
  double obstacle_radius_;
};

}  // namespace ulsan_obstacle_layer
