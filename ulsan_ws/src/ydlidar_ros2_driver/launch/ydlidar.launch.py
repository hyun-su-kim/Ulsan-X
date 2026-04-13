#!/usr/bin/python3
# Copyright 2020, EAIBOT
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch_ros.actions import LifecycleNode
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.actions import LogInfo

import lifecycle_msgs.msg
import os


def generate_launch_description():
    share_dir = get_package_share_directory('ydlidar_ros2_driver')
    parameter_file = LaunchConfiguration('params_file')
    name = 'ydlidar_ros2_driver_node'

    params_declare = DeclareLaunchArgument('params_file',
                                           default_value=os.path.join(
                                               share_dir, 'params', 'ydlidar.yaml'),
                                           description='FPath to the ROS2 parameters file to use.')

    # [멀티로봇] namespace='/' 제거.
    # 원본에 namespace='/' 하드코딩 시 PushRosNamespace가 무시되어
    # 항상 글로벌 /scan으로 발행됨 → AMCL이 /limo_001/scan을 구독하지 못해 위치추정 실패.
    # 제거 후 navigation_diff_launch.py의 PushRosNamespace가 적용되어
    # /limo_001/scan, /limo_002/scan으로 격리됨.
    driver_node = LifecycleNode(package='ydlidar_ros2_driver',
                                executable='ydlidar_ros2_driver_node',
                                name='ydlidar_ros2_driver_node',
                                output='screen',
                                emulate_tty=True,
                                parameters=[parameter_file],
                                )
    # tf2_node = Node(package='tf2_ros',
    #                 executable='static_transform_publisher',
    #                 name='static_tf_pub_laser',
    #                 arguments=['0', '0', '0.02','0', '0', '0', '1','base_link','laser_link'],
    #                 )

    return LaunchDescription([
        params_declare,
        driver_node,
        # tf2_node,
    ])
