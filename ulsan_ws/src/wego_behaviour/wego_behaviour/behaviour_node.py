import os
import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import String, Empty
from geometry_msgs.msg import PoseWithCovarianceStamped
from yasmin import StateMachine, Blackboard

from wego_behaviour.states import GuidingState, IdleState, ReturningState, WaitingState
from nav2_simple_commander.robot_navigator import BasicNavigator

class BehaviourNode(Node):
    def __init__(self, waypoints: dict, domain_home_map: dict):
        super().__init__('wego_behaviour')

        self.waypoints = waypoints

        # ROS_DOMAIN_ID로 복귀 홈 위치 결정 — 매핑은 robot_config.yaml의 domain_home_map, 좌표는 waypoints.yaml 참조
        domain_id = os.environ.get('ROS_DOMAIN_ID', '6')
        self.home_key: str = domain_home_map.get(domain_id, 'home_robot1')
        self.get_logger().info(f'home_key: {self.home_key} (DOMAIN_ID={domain_id})')

        self.pending_destination: str | None = None
        self.latest_amcl_pose: PoseWithCovarianceStamped | None = None  # [DEBUG]
        self._pause_flag  = False
        self._resume_flag = False

        self._status_pub = self.create_publisher(String, '/robot_status', 10)
        self._speak_pub = self.create_publisher(String, '/speak_text', 10)

        self.create_subscription(String, '/goal_destination', self._dest_cb, 10)
        self.create_subscription(Empty, '/pause',  self._pause_cb,  10)
        self.create_subscription(Empty, '/resume', self._resume_cb, 10)
        self.create_subscription(  # [DEBUG]
            PoseWithCovarianceStamped, '/amcl_pose', self._amcl_cb, 1)  # [DEBUG]

    def _pause_cb(self, _: Empty) -> None:
        self._pause_flag  = True
        self._resume_flag = False
        self.get_logger().info('pause 수신')

    def _resume_cb(self, _: Empty) -> None:
        self._resume_flag = True
        self._pause_flag  = False
        self.get_logger().info('resume 수신')

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

    # 도메인 → home_key 매핑 — domain_home_map 사용 (domain_robot_map은 브릿지/dispatcher용)
    with open(f'{pkg_share}/config/robot_config.yaml') as f:
        config = yaml.safe_load(f)
        domain_home_map = config['domain_home_map']

    node = BehaviourNode(waypoints, domain_home_map)

    navigator = BasicNavigator()
    navigator.waitUntilNav2Active()

    # BehaviourNode를 별도 executor로 분리 — BasicNavigator 내부 global executor와 충돌 방지
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    sm = StateMachine(outcomes=['finished'])
    sm.add_state('IDLE',      IdleState(node),               transitions={'goto_destination': 'GUIDING'})
    sm.add_state('GUIDING',   GuidingState(node, navigator), transitions={'succeeded': 'RETURNING', 'failed': 'IDLE', 'paused': 'WAITING'})
    sm.add_state('RETURNING', ReturningState(node, navigator),transitions={'succeeded': 'IDLE',      'failed': 'IDLE', 'paused': 'WAITING'})
    sm.add_state('WAITING',   WaitingState(node),            transitions={'resume_guiding': 'GUIDING', 'resume_returning': 'RETURNING'})


    try:
        sm(Blackboard())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
