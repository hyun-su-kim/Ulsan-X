"""person_detect_node.py — YOLOv8 사람 감지 + Depth 거리 게이팅 노드

목적:
  Nav2 BT의 PersonClearCondition 플러그인이 구독할 /person_detected (Bool)를 발행.
  안내 주행 중 로봇 전방 가까이(기본 0.7m) 사람이 들어오면 True → BT가 FollowPath
  halt → 정지. 사람이 벗어나면 False → 주행 재개.

설계:
  - RGB(/camera/color/image_raw)로 YOLOv8n 추론 → COCO class 0(person) 박스 추출
  - Depth(/camera/depth/image_raw)에서 각 사람 박스 중심 영역의 거리 측정
  - 거리 < distance_threshold 인 사람이 한 명이라도 있으면 True
  - 거리 게이팅 이유: 화면 감지만 쓰면 멀리 지나가는 사람에도 멈춤 → 안내 불가.
    근접한 사람만 정지 대상으로 한정.

파라미터:
  model_path           : YOLO 가중치 (기본 'yolov8n.pt', COCO 사전학습, 미학습)
  confidence_threshold : person 최소 신뢰도 (기본 0.5)
  distance_threshold   : 정지 임계 거리 m (기본 0.7)
  rate                 : 추론 주기 Hz (기본 10.0) — 매 프레임 추론 시 CPU 과부하
  depth_scale          : depth 픽셀값 → m 환산 (16UC1 mm 기준 0.001)
  color_topic / depth_topic / output_topic
"""

import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from ultralytics import YOLO

# COCO 데이터셋에서 'person' 클래스 인덱스
PERSON_CLASS_ID = 0


class PersonDetectNode(Node):
    def __init__(self):
        super().__init__('person_detect_node')

        self.declare_parameter('model_path', 'yolov8n.pt')
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('distance_threshold', 0.7)
        self.declare_parameter('rate', 10.0)
        self.declare_parameter('depth_scale', 0.001)
        self.declare_parameter('color_topic', '/camera/color/image_raw')
        self.declare_parameter('depth_topic', '/camera/depth/image_raw')
        self.declare_parameter('output_topic', '/person_detected')

        self.conf_th = self.get_parameter('confidence_threshold').value
        self.dist_th = self.get_parameter('distance_threshold').value
        self.depth_scale = self.get_parameter('depth_scale').value
        rate = self.get_parameter('rate').value
        model_path = self.get_parameter('model_path').value

        self.bridge = CvBridge()
        self.model = YOLO(model_path)
        self.get_logger().info(f'YOLO model loaded: {model_path}')

        self._color = None   # 최신 RGB (numpy BGR)
        self._depth = None    # 최신 Depth (numpy, 원본 dtype)
        self._last_state = None  # 직전 발행값 (변화 시에만 로그)

        self.create_subscription(
            Image, self.get_parameter('color_topic').value, self._color_cb, 10)
        self.create_subscription(
            Image, self.get_parameter('depth_topic').value, self._depth_cb, 10)
        self.pub = self.create_publisher(
            Bool, self.get_parameter('output_topic').value, 10)

        self.create_timer(1.0 / rate, self._on_timer)
        self.get_logger().info(
            f'person_detect_node started '
            f'(conf={self.conf_th}, dist={self.dist_th}m, rate={rate}Hz)')

    def _color_cb(self, msg: Image):
        self._color = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def _depth_cb(self, msg: Image):
        # 16UC1(mm) 또는 32FC1(m) 모두 passthrough로 받아 depth_scale로 환산
        self._depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')

    def _on_timer(self):
        if self._color is None:
            return

        color = self._color
        depth = self._depth
        detected = False
        min_dist = None

        results = self.model(color, classes=[PERSON_CLASS_ID],
                             conf=self.conf_th, verbose=False)
        boxes = results[0].boxes

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

            # depth 없으면 거리 게이팅 불가 → 화면 감지만으로 보수적 정지
            if depth is None:
                detected = True
                break

            dist = self._box_distance(depth, color.shape, x1, y1, x2, y2)
            if dist is None:
                continue  # 유효 depth 없음 (구멍/측정 실패) → 이 박스 무시

            if min_dist is None or dist < min_dist:
                min_dist = dist
            if dist <= self.dist_th:
                detected = True

        self._publish(detected, min_dist)

    def _box_distance(self, depth, color_shape, x1, y1, x2, y2):
        """박스 중심 영역(중앙 40%)의 유효 depth 중앙값 → 거리(m).

        - 배경 픽셀 영향을 줄이려 박스 중앙부만 샘플링
        - depth와 color 해상도가 다르면 좌표를 스케일링
        - 0(측정 실패) 픽셀은 제외, 유효값 없으면 None
        """
        dh, dw = depth.shape[:2]
        ch, cw = color_shape[:2]
        sx, sy = dw / cw, dh / ch

        # 박스 중앙 40% 영역
        bw, bh = (x2 - x1), (y2 - y1)
        cx1 = int((x1 + bw * 0.3) * sx)
        cx2 = int((x2 - bw * 0.3) * sx)
        cy1 = int((y1 + bh * 0.3) * sy)
        cy2 = int((y2 - bh * 0.3) * sy)
        cx1, cx2 = max(0, cx1), min(dw, cx2)
        cy1, cy2 = max(0, cy1), min(dh, cy2)
        if cx2 <= cx1 or cy2 <= cy1:
            return None

        patch = depth[cy1:cy2, cx1:cx2].astype(np.float32)
        valid = patch[patch > 0]
        if valid.size == 0:
            return None
        return float(np.median(valid)) * self.depth_scale

    def _publish(self, detected: bool, min_dist):
        self.pub.publish(Bool(data=detected))
        if detected != self._last_state:
            if detected:
                d = f'{min_dist:.2f}m' if min_dist is not None else 'no-depth'
                self.get_logger().warn(f'PERSON detected ({d}) → STOP')
            else:
                self.get_logger().info('person cleared → RESUME')
            self._last_state = detected


def main(args=None):
    rclpy.init(args=args)
    node = PersonDetectNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
