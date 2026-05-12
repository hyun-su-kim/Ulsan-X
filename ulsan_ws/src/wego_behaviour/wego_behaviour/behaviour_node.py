import math
import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, DurabilityPolicy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseWithCovarianceStamped
from yasmin import StateMachine, Blackboard

from wego_behaviour.states import GuidingState, IdleState, ReturningState
from nav2_simple_commander.robot_navigator import BasicNavigator


class BehaviourNode(Node):
    def __init__(self, waypoints: dict):
        super().__init__('wego_behaviour')

        self.declare_parameter('home_key', 'home_robot1')

        self.waypoints = waypoints
        self.home_key: str = self.get_parameter('home_key').get_parameter_value().string_value
        self.pending_destination: str | None = None
        self.latest_amcl_pose: PoseWithCovarianceStamped | None = None  # [DEBUG]

        self._status_pub = self.create_publisher(String, '/robot_status', 10)
        self._speak_pub = self.create_publisher(String, '/speak_text', 10)

        # TRANSIENT_LOCAL(latched) QoS: waitUntilNav2Active() 이전에 미리 발행해도
        # AMCL이 subscribe하는 순간 메시지를 즉시 수신할 수 있도록 보장.
        # 일반 volatile QoS를 쓰면 AMCL subscribe 전에 발행된 메시지가 소실되어
        # AMCL이 0,0,0 기본값으로 파티클을 초기화하고 global costmap을 오염시킴.
        _latched_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', _latched_qos
        )
        self.create_subscription(String, '/goal_destination', self._dest_cb, 10)
        self.create_subscription(  # [DEBUG]
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl_cb, 1)  # [DEBUG]

    def publish_initial_pose(self) -> None:
        home = self.waypoints[self.home_key]
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = float(home['x'])
        msg.pose.pose.position.y = float(home['y'])
        yaw = float(home['yaw'])
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f'초기 포즈 발행: {home["label"]} (x={home["x"]}, y={home["y"]}, yaw={yaw:.3f})'
        )

    def _amcl_cb(self, msg: PoseWithCovarianceStamped) -> None:  # [DEBUG]
        self.latest_amcl_pose = msg  # [DEBUG]

    def _dest_cb(self, msg: String) -> None:
        if msg.data in self.waypoints:
            self.pending_destination = msg.data
        else:
            self.get_logger().warn(f'알 수 없는 목적지 키: {msg.data}')

    def publish_status(self, status: str) -> None:
        msg = String()
        msg.data = status
        self._status_pub.publish(msg)
        
    def speak_text(self, text: str) -> None:                                        
        msg = String()                      
        msg.data = text                                                             
        self._speak_pub.publish(msg)

def main():
    rclpy.init()

    pkg_share = get_package_share_directory('wego_behaviour')
    with open(f'{pkg_share}/config/waypoints.yaml') as f:
        waypoints = yaml.safe_load(f)['waypoints']

    node = BehaviourNode(waypoints)

    # waitUntilNav2Active() 이전에 초기 포즈를 먼저 발행.
    # AMCL이 active되는 순간 latched 메시지를 즉시 수신하므로
    # 0,0,0 기본값으로 파티클이 초기화되는 타이밍 자체가 없어짐.
    node.publish_initial_pose()

    navigator = BasicNavigator()
    navigator.waitUntilNav2Active()

    # BehaviourNode를 별도 executor로 분리 — BasicNavigator 내부 global executor와 충돌 방지
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    sm = StateMachine(outcomes=['finished'])
    sm.add_state('IDLE',      IdleState(node),                      transitions={'goto_destination': 'GUIDING'})
    sm.add_state('GUIDING',   GuidingState(node, navigator),        transitions={'succeeded': 'RETURNING', 'failed': 'IDLE'})
    sm.add_state('RETURNING', ReturningState(node, navigator),      transitions={'succeeded': 'IDLE',      'failed': 'IDLE'})


    try:
        sm(Blackboard())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
