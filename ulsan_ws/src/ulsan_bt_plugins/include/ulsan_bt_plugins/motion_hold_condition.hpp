// motion_hold_condition.hpp — 주행 정지 게이트(WAITING) 신호 수신 시 FollowPath halt BT 조건 노드
//
// 동작:
//   /motion_hold (std_msgs/Bool) 구독.
//   tick():
//     hold=false → SUCCESS  → ReactiveSequence가 다음 자식(FollowPath) 실행
//     hold=true  → RUNNING  → ReactiveSequence가 FollowPath를 halt() → 정지
//   FAILURE는 절대 반환하지 않음 → 복구 동작(BackUp/ClearCostmap) 미발동.
//
//   /motion_hold는 ulsan_behaviour가 발행한다. 사람 감지(/person_detected)·관제 GUI
//   pause·로봇 접근(ulsan_traffic)을 게이트(OR)로 합쳐 FSM이 WAITING 상태일 때만 true.
//   구 PersonClearCondition(/person_detected 단일 소스 직접 구독)을 대체 — 세 정지
//   트리거를 behaviour 게이트 하나로 통합하고, BT는 단일 신호만 본다.
//
// BT.CPP v3에서 ConditionNode는 RUNNING 반환이 허용됨(SyncActionNode와 달리 금지 X).
// Nav2 IsBatteryLowCondition 패턴(blackboard "node" + 전용 callback group executor) 채택.

#ifndef ULSAN_BT_PLUGINS__MOTION_HOLD_CONDITION_HPP_
#define ULSAN_BT_PLUGINS__MOTION_HOLD_CONDITION_HPP_

#include <string>

#include "behaviortree_cpp_v3/condition_node.h"
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/bool.hpp"

namespace ulsan_bt_plugins
{

class MotionHoldCondition : public BT::ConditionNode
{
public:
  MotionHoldCondition(
    const std::string & condition_name,
    const BT::NodeConfiguration & conf);

  MotionHoldCondition() = delete;

  BT::NodeStatus tick() override;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>(
        "topic", "/motion_hold", "주행 정지 게이트 Bool 토픽명"),
    };
  }

private:
  void holdCallback(std_msgs::msg::Bool::SharedPtr msg);

  rclcpp::Node::SharedPtr node_;
  rclcpp::CallbackGroup::SharedPtr callback_group_;
  rclcpp::executors::SingleThreadedExecutor callback_group_executor_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr hold_sub_;

  std::string topic_;
  bool hold_active_;
};

}  // namespace ulsan_bt_plugins

#endif  // ULSAN_BT_PLUGINS__MOTION_HOLD_CONDITION_HPP_
