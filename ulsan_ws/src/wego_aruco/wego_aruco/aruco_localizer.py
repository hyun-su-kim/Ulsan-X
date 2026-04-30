import math

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_srvs.srv import Trigger
import tf2_ros


ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)

# /initialpose 공분산 (위치 5cm, 자세 5도 불확실성)
_COV = [0.0] * 36
_COV[0] = 0.05 ** 2
_COV[7] = 0.05 ** 2
_COV[35] = (5.0 * math.pi / 180.0) ** 2


def _rot_z(yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s, 0, 0],
                     [s,  c, 0, 0],
                     [0,  0, 1, 0],
                     [0,  0, 0, 1]], dtype=float)


def _translation(x: float, y: float, z: float = 0.0) -> np.ndarray:
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = x, y, z
    return m


def _rvec_tvec_to_mat(rvec: np.ndarray, tvec: np.ndarray) -> np.ndarray:
    R, _ = cv2.Rodrigues(rvec)
    m = np.eye(4)
    m[:3, :3] = R
    m[:3, 3] = tvec.flatten()
    return m


def _mat_to_yaw(m: np.ndarray) -> float:
    return math.atan2(m[1, 0], m[0, 0])


class ArucoLocalizer(Node):
    def __init__(self):
        super().__init__('aruco_localizer')

        self.declare_parameter('home_key', 'home_robot1')
        self.declare_parameter(
            'markers_file',
            str(get_package_share_directory('wego_aruco')) + '/config/markers.yaml',
        )

        home_key = self.get_parameter('home_key').get_parameter_value().string_value
        markers_file = self.get_parameter('markers_file').get_parameter_value().string_value

        with open(markers_file, 'r') as f:
            data = yaml.safe_load(f)

        self._markers: dict = data['markers']
        self._target_id: int = data['home_marker'][home_key]
        self._target_info: dict = self._markers[self._target_id]
        self.get_logger().info(
            f'홈 키: {home_key} → 마커 ID {self._target_id}'
        )

        self._bridge = CvBridge()
        self._camera_matrix: np.ndarray | None = None
        self._dist_coeffs: np.ndarray | None = None
        self._latest_image: np.ndarray | None = None

        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)

        self.create_subscription(CameraInfo, '/camera/color/camera_info', self._info_cb, 1)
        self.create_subscription(Image, '/camera/color/image_raw', self._image_cb, 1)
        self._pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 1
        )
        self.create_service(Trigger, '/aruco_correct', self._correct_cb)

        self.get_logger().info('/aruco_correct 서비스 대기 중')

    def _info_cb(self, msg: CameraInfo) -> None:
        if self._camera_matrix is not None:
            return
        k = msg.k
        self._camera_matrix = np.array(
            [[k[0], k[1], k[2]],
             [k[3], k[4], k[5]],
             [k[6], k[7], k[8]]], dtype=float
        )
        self._dist_coeffs = np.array(msg.d, dtype=float)
        self.get_logger().info('카메라 파라미터 수신 완료')

    def _image_cb(self, msg: Image) -> None:
        self._latest_image = self._bridge.imgmsg_to_cv2(msg, 'bgr8')

    def _correct_cb(self, _req: Trigger.Request, res: Trigger.Response):
        if self._camera_matrix is None:
            res.success = False
            res.message = 'CameraInfo 미수신'
            return res

        if self._latest_image is None:
            res.success = False
            res.message = '이미지 미수신'
            return res

        gray = cv2.cvtColor(self._latest_image, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = DETECTOR.detectMarkers(gray)

        if ids is None or self._target_id not in ids.flatten():
            res.success = False
            res.message = f'마커 ID {self._target_id} 미감지'
            self.get_logger().warn(res.message)
            return res

        idx = list(ids.flatten()).index(self._target_id)
        marker_size = float(self._target_info['size'])

        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            [corners[idx]], marker_size, self._camera_matrix, self._dist_coeffs
        )
        T_cam_marker = _rvec_tvec_to_mat(rvecs[0][0], tvecs[0][0])

        # 맵 기준 마커 pose (2D 평면 — z=0 가정)
        mx = float(self._target_info['x'])
        my = float(self._target_info['y'])
        myaw = float(self._target_info['yaw'])
        T_map_marker = _translation(mx, my) @ _rot_z(myaw)

        # camera_color_optical_frame → base_link TF 조회
        try:
            tf = self._tf_buffer.lookup_transform(
                'base_link',
                'camera_color_optical_frame',
                Time(),
                timeout=rclpy.duration.Duration(seconds=1.0),
            )
        except Exception as e:
            res.success = False
            res.message = f'TF 조회 실패: {e}'
            self.get_logger().error(res.message)
            return res

        t = tf.transform.translation
        rot = tf.transform.rotation
        # quaternion → rotation matrix
        qx, qy, qz, qw = rot.x, rot.y, rot.z, rot.w
        R_cb = np.array([
            [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
            [2*(qx*qy + qz*qw), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qx*qw)],
            [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx**2 + qy**2)],
        ])
        T_base_cam = np.eye(4)
        T_base_cam[:3, :3] = R_cb
        T_base_cam[:3, 3] = [t.x, t.y, t.z]

        # T_map_base = T_map_marker × inv(T_cam_marker) × T_base_cam
        T_map_base = T_map_marker @ np.linalg.inv(T_cam_marker) @ T_base_cam

        pose_msg = PoseWithCovarianceStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = 'map'
        pose_msg.pose.pose.position.x = T_map_base[0, 3]
        pose_msg.pose.pose.position.y = T_map_base[1, 3]
        yaw = _mat_to_yaw(T_map_base)
        pose_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        pose_msg.pose.covariance = _COV

        self._pose_pub.publish(pose_msg)

        res.success = True
        res.message = (
            f'보정 완료: x={T_map_base[0,3]:.3f}, '
            f'y={T_map_base[1,3]:.3f}, yaw={math.degrees(yaw):.1f}°'
        )
        self.get_logger().info(res.message)
        return res


def main():
    rclpy.init()
    node = ArucoLocalizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
