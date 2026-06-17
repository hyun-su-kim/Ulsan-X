// motion_hold_condition.cpp — 주행 정지 게이트(WAITING) 신호 수신 시 FollowPath halt BT 조건 노드
// 헤더 motion_hold_condition.hpp 참고.

#include "ulsan_bt_plugins/motion_hold_condition.hpp"

namespace ulsan_bt_plugins
{

MotionHoldCondition::MotionHoldCondition(
  const std::string & condition_name,
  const BT::NodeConfiguration & conf)
: BT::ConditionNode(condition_name, conf),
  hold_active_(false)
{
  // bt_navigator가 blackboard에 넣어주는 공유 rclcpp 노드 획득
  node_ = config().blackboard->get<rclcpp::Node::SharedPtr>("node");

  getInput("topic", topic_);

  // 메인 실행기와 분리된 전용 callback group — tick()에서 spin_some으로 직접 수집
  callback_group_ = node_->create_callback_group(
    rclcpp::CallbackGroupType::MutuallyExclusive, false);
  callback_group_executor_.add_callback_group(
    callback_group_, node_->get_node_base_interface());

  rclcpp::SubscriptionOptions sub_option;
  sub_option.callback_group = callback_group_;
  hold_sub_ = node_->create_subscription<std_msgs::msg::Bool>(
    topic_,
    rclcpp::SystemDefaultsQoS(),
    std::bind(&MotionHoldCondition::holdCallback, this, std::placeholders::_1),
    sub_option);

  RCLCPP_INFO(
    node_->get_logger(),
    "MotionHoldCondition 초기화: topic=%s", topic_.c_str());
}

BT::NodeStatus MotionHoldCondition::tick()
{
  // 최신 /motion_hold 콜백 수집 (논블로킹)
  callback_group_executor_.spin_some();

  if (hold_active_) {
    // 정지 게이트 ON → RUNNING → ReactiveSequence가 FollowPath halt → cmd_vel 정지
    return BT::NodeStatus::RUNNING;
  }
  // 게이트 OFF → SUCCESS → FollowPath 정상 진행
  return BT::NodeStatus::SUCCESS;
}

void MotionHoldCondition::holdCallback(std_msgs::msg::Bool::SharedPtr msg)
{
  hold_active_ = msg->data;
}

}  // namespace ulsan_bt_plugins

#include "behaviortree_cpp_v3/bt_factory.h"
BT_REGISTER_NODES(factory)
{
  factory.registerNodeType<ulsan_bt_plugins::MotionHoldCondition>("MotionHoldCondition");
}
