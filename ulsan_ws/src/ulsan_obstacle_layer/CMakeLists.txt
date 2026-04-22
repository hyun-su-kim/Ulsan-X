cmake_minimum_required(VERSION 3.8)
project(ulsan_obstacle_layer)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav2_costmap_2d REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(pluginlib REQUIRED)

# 공유 라이브러리로 빌드 — pluginlib이 런타임에 dlopen()으로 로드하므로 SHARED 필수.
# 라이브러리 이름(peer_obstacle_layer)은 plugins.xml의 path 속성과 반드시 일치해야 함.
add_library(peer_obstacle_layer SHARED
  src/peer_obstacle_layer.cpp
)

target_include_directories(peer_obstacle_layer PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(peer_obstacle_layer
  rclcpp
  nav2_costmap_2d
  geometry_msgs
  pluginlib
)

# plugins.xml을 ament index에 등록.
# Nav2가 부팅 시 nav2_costmap_2d 플러그인 목록을 검색할 때 이 파일을 읽어
# PeerObstacleLayer 클래스를 발견한다.
pluginlib_export_plugin_description_file(nav2_costmap_2d plugins.xml)

install(TARGETS peer_obstacle_layer
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include/
)

install(FILES plugins.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
