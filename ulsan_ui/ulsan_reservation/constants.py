ROOM_LABELS = {
    "counseling_1":           "상담실 1",
    "counseling_2":           "상담실 2",
    "intensive_counseling_1": "집중상담실 1",
    "intensive_counseling_2": "집중상담실 2",
}

CLASSROOM_LABELS = {
    "classroom_1": "1강의실",
    "classroom_2": "2강의실",
    "classroom_3": "3강의실",
    "classroom_4": "4강의실",
    "classroom_5": "5강의실",
}


def pick_idle_robot(robot_status: dict) -> str | None:
    """limo1 우선으로 IDLE 로봇 반환. 없으면 None."""
    for robot in ("limo1", "limo2"):
        if robot_status.get(robot) == "IDLE":
            return robot
    return None
