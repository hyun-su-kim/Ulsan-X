"""
waypoint_goto.py — waypoints.yaml에 저장된 목적지로 이동하는 CLI 노드

사용법:
  ros2 run wego_aruco waypoint_goto <목적지 이름>
  ros2 run wego_aruco waypoint_goto room_1
  ros2 run wego_aruco waypoint_goto --list   # 등록된 목적지 목록 출력
"""

import os
import sys

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node


CONFIG_DIR = os.path.join(get_package_share_directory('wego_aruco'), 'config')
WAYPOINTS_FILE = os.path.join(CONFIG_DIR, 'waypoints.yaml')


class WaypointGoto(Node):

    def __init__(self, destination: str):
        super().__init__('waypoint_goto')
        self._destination = destination
        self._action_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')

    def run(self):
        # ── waypoints.yaml 로드 ──
        if not os.path.exists(WAYPOINTS_FILE):
            print(f'[오류] waypoints.yaml을 찾을 수 없습니다: {WAYPOINTS_FILE}')
            print('  aruco_calibrator를 먼저 실행해 목적지를 등록하세요.')
            return False

        with open(WAYPOINTS_FILE) as f:
            data = yaml.safe_load(f) or {}

        waypoints = data.get('waypoints', {})

        # ── 목적지 목록 출력 옵션 ──
        if self._destination == '--list':
            if not waypoints:
                print('등록된 목적지가 없습니다.')
            else:
                print('등록된 목적지:')
                for name, wp in waypoints.items():
                    print(f'  {name}  (x={wp["x"]:.3f}, y={wp["y"]:.3f}, yaw={wp["yaw"]:.3f})')
            return True

        # ── 목적지 조회 ──
        if self._destination not in waypoints:
            print(f'[오류] "{self._destination}" 목적지를 찾을 수 없습니다.')
            print(f'  등록된 목적지: {list(waypoints.keys())}')
            return False

        wp = waypoints[self._destination]
        print(f'[이동] "{self._destination}" → x={wp["x"]:.3f}, y={wp["y"]:.3f}, yaw={wp["yaw"]:.3f}')

        # ── Nav2 액션 서버 대기 ──
        print('[대기] Nav2 액션 서버 연결 중...')
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            print('[오류] Nav2 액션 서버에 연결할 수 없습니다. Nav2가 실행 중인지 확인하세요.')
            return False

        # ── goal 메시지 구성 ──
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        goal_msg.pose.pose.position.x = float(wp['x'])
        goal_msg.pose.pose.position.y = float(wp['y'])
        goal_msg.pose.pose.position.z = 0.0

        # waypoints.yaml에 quaternion이 저장되어 있으므로 그대로 사용
        goal_msg.pose.pose.orientation.x = float(wp.get('qx', 0.0))
        goal_msg.pose.pose.orientation.y = float(wp.get('qy', 0.0))
        goal_msg.pose.pose.orientation.z = float(wp['qz'])
        goal_msg.pose.pose.orientation.w = float(wp['qw'])

        # ── goal 전송 및 결과 대기 ──
        print('[전송] 목적지 goal 전송...')
        future = self._action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if not goal_handle.accepted:
            print('[오류] Goal이 거부되었습니다.')
            return False

        print('[주행 중] 목적지로 이동 중...')
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        status = result_future.result().status
        # action_msgs/GoalStatus: SUCCEEDED=4
        if status == 4:
            print(f'[완료] "{self._destination}" 도착.')
            return True
        else:
            print(f'[실패] 주행 실패. status={status}')
            return False


def main(args=None):
    # sys.argv에서 목적지 이름 추출 (rclpy 인자 파싱 전에 처리)
    # ros2 run wego_aruco waypoint_goto <목적지> 형태로 호출됨
    user_args = [a for a in sys.argv[1:] if not a.startswith('--ros-args')]

    if not user_args:
        print('사용법: ros2 run wego_aruco waypoint_goto <목적지 이름>')
        print('       ros2 run wego_aruco waypoint_goto --list')
        sys.exit(1)

    destination = user_args[0]

    rclpy.init(args=args)
    node = WaypointGoto(destination)
    try:
        success = node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()

    sys.exit(0 if success else 1)
