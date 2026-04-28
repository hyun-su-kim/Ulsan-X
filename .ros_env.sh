#!/bin/bash

# ROS2 humble 환경
source /opt/ros/humble/setup.bash && echo "humble is ready!"

alias ros='source /opt/ros/humble/setup.bash && echo "source -> humble!"'
alias set='source install/local_setup.bash && echo "source -> install/setup.bash!"'
alias cb='code ~/.bashrc'
alias sb='source ~/.bashrc && echo "source -> .bashrc!"'
alias col='colcon build'
alias cr='code ~/Ulsan-X/.ros_env.sh'
alias wego='ssh wego@192.168.0.101'
alias wego2='ssh wego@192.168.0.102'

get() {
    echo "===== ROS2 ENV STATE ====="

    # ROS_DOMAIN_ID
    if [ -z "$ROS_DOMAIN_ID" ]; then
        echo "ROS_DOMAIN_ID      : (not set, default = 0)"
    else
        echo "ROS_DOMAIN_ID      : $ROS_DOMAIN_ID"
    fi

    # RMW_IMPLEMENTATION
    if [ -z "$RMW_IMPLEMENTATION" ]; then
        echo "RMW_IMPLEMENTATION : (not set, default = rmw_fastrtps_cpp)"
    else
        echo "RMW_IMPLEMENTATION : $RMW_IMPLEMENTATION"
    fi

    # ROS_LOCALHOST_ONLY
    if [ -z "$ROS_LOCALHOST_ONLY" ]; then
        echo "ROS_LOCALHOST_ONLY : (not set, default = 0)"
    else
        echo "ROS_LOCALHOST_ONLY : $ROS_LOCALHOST_ONLY"
    fi

    # IP 주소
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$IP" ]; then
        echo "IP ADDRESS         : (not found)"
    else
        echo "IP ADDRESS         : $IP"
    fi

    echo "=========================="
}


#cyclonedds Setting
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=/home/wego/Ulsan-X/cyclone_peers.xml

# Domain Setting

# 관제 ui
export ROS_DOMAIN_ID=5

# limo 1
# export ROS_DOMAIN_ID=6

# limo 2
# export ROS_DOMAIN_ID=7

