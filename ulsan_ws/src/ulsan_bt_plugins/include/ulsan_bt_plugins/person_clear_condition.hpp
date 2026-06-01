// person_clear_condition.hpp — 사람 감지 시 주행 일시정지 BT 조건 노드
//
// 동작:
//   /person_detected (std_msgs/Bool) 구독.
//   tick():
//     사람 없음(false) → SUCCESS  → ReactiveSequence가 다음 자식(FollowPath) 실행
//     사람 있음(true)  → RUNNING  → ReactiveSequence가 FollowPath를 halt() → 정지
//   FAILURE는 절대 반환하지 않음 → 복구 동작(BackUp/ClearCostmap) 미발동.
//
// BT.CPP v3에서 ConditionNode는 RUNNING 반환이 허용됨(SyncActionNode와 달리 금지 X).
// Nav2 IsBatteryLowCondition 패턴(blackboard "node" + 전용 callback group executor) 채택.

#ifndef ULSAN_BT_PLUGINS__PERSON_CLEAR_CONDITION_HPP_
#define ULSAN_BT_PLUGINS__PERSON_CLEAR_CONDITION_HPP_

#include <string>

#include "behaviortree_cpp_v3/condition_node.h"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/bool.hpp"

namespace ulsan_bt_plugins
{

class PersonClearCondition : public BT::ConditionNode
{
public:
  PersonClearCondition(
    const std::string & condition_name,
    const BT::NodeConfiguration & conf);

  PersonClearCondition() = delete;

  BT::NodeStatus tick() override;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>(
        "topic", "/person_detected", "사람 감지 Bool 토픽명"),
    };
  }

private:
  void personCallback(std_msgs::msg::Bool::SharedPtr msg);

  rclcpp::Node::SharedPtr node_;
  rclcpp::CallbackGroup::SharedPtr callback_group_;
  rclcpp::executors::SingleThreadedExecutor callback_group_executor_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr person_sub_;

  std::string topic_;
  bool person_present_;
};

}  // namespace ulsan_bt_plugins

#endif  // ULSAN_BT_PLUGINS__PERSON_CLEAR_CONDITION_HPP_
