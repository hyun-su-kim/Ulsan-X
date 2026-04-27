include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "imu_link",
  published_frame = "odom",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = true,
  use_odometry = true,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.2,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.,
  odometry_sampling_ratio = 1.,
  fixed_frame_pose_sampling_ratio = 1.,
  imu_sampling_ratio = 1.,
  landmarks_sampling_ratio = 1.,
}

MAP_BUILDER.use_trajectory_builder_2d = true

TRAJECTORY_BUILDER_2D.min_range = 0.1
TRAJECTORY_BUILDER_2D.max_range = 5.0                              -- [수정] 8.0 -> 5.0 : 유리 투과 노이즈 차단
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 2.0                -- [수정] 0.1 -> 2.0 : 유리 구간 자유공간 추론 거리 확대
TRAJECTORY_BUILDER_2D.use_imu_data = true
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.1)
TRAJECTORY_BUILDER_2D.submaps.num_range_data = 40                  -- [추가] 기본값 90 -> 40 : 복도 loop closure 기회 증가
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.translation_weight = 30.  -- [추가] 기본값 10 -> 30 : 복도 오도메트리 신뢰도 향상
TRAJECTORY_BUILDER_2D.ceres_scan_matcher.rotation_weight = 70.     -- [추가] 기본값 40 -> 70 : 복도 IMU 신뢰도 향상

POSE_GRAPH.optimize_every_n_nodes = 10                             -- [수정] 주석 해제 + 30 -> 10 : 복도 drift 빠른 보정
POSE_GRAPH.constraint_builder.min_score = 0.62                     -- [수정] 0.7 -> 0.62 : 복도 loop closure 허용 범위 확대
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.7

return options