cmake_minimum_required(VERSION 3.8)
project(ulsan_bt_plugins)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(behaviortree_cpp_v3 REQUIRED)
find_package(std_msgs REQUIRED)

include_directories(include)

set(dependencies
  rclcpp
  behaviortree_cpp_v3
  std_msgs
)

# --- MotionHoldCondition BT 플러그인 ---
# 라이브러리명 = plugin_lib_names 항목명 (lib 접두/.so 접미 제외)
add_library(ulsan_motion_hold_condition_bt_node SHARED
  src/motion_hold_condition.cpp)
list(APPEND plugin_libs ulsan_motion_hold_condition_bt_node)

foreach(bt_plugin ${plugin_libs})
  ament_target_dependencies(${bt_plugin} ${dependencies})
  target_compile_definitions(${bt_plugin} PRIVATE BT_PLUGIN_EXPORT)
endforeach()

install(TARGETS ${plugin_libs}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_include_directories(include)
ament_export_libraries(${plugin_libs})
ament_export_dependencies(${dependencies})

ament_package()
