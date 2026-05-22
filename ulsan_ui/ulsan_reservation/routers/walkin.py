# 현장 방문 라우터
#
# GET  /walkin/rooms/available  — 현재 시간대 빈 상담실 조회
# POST /walkin/assign           — 빈 상담실 배정 + walk-in DB 삽입 + 미션 생성

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/walkin", tags=["walkin"])

# 상담실 키 → 방문자 표시명 매핑 (waypoints.yaml label과 동일)
ROOM_LABELS = {
    "counseling_1":           "상담실 1",
    "counseling_2":           "상담실 2",
    "intensive_counseling_1": "집중상담실 1",
    "intensive_counseling_2": "집중상담실 2",
}


@router.get("/rooms/available")
def get_available_room(db: Session = Depends(get_db)):
    """
    현재 시간대에 비어있는 상담실 조회.

    반환: {"room": "counseling_1", "label": "상담실 1"}
    빈 상담실 없으면 503 반환.
    """
    current_hour = datetime.now().hour
    room = crud.get_available_room_today(db, current_hour)
    if not room:
        raise HTTPException(status_code=503, detail="현재 시간대 빈 상담실 없음")
    return {"room": room, "label": ROOM_LABELS.get(room, room)}


@router.post("/assign", response_model=schemas.WalkinAssignResponse)
def assign_walkin(db: Session = Depends(get_db)):
    """
    현장 방문 상담 배정.

    동작 순서:
    1. 현재 시간대 빈 상담실 탐색
    2. reservations 테이블에 walk-in 행 삽입 (중복 배정 방지)
    3. missions 테이블에 PENDING 미션 생성
    4. wego_dispatcher가 미션을 수락할 때까지 대기하지 않고 즉시 응답

    로봇 배정 결정은 wego_dispatcher가 폴링 시 수행한다.
    태블릿 GuidingPage는 robot 필드로 상태 폴링을 시작하는데,
    이 시점에는 배정 로봇을 아직 모르므로 임시로 None을 반환할 수 없다.
    → wego_dispatcher가 PATCH /assign/{id}/start 호출 시 robot_assigned가 확정된다.
    → 태블릿은 GET /robots/status 폴링으로 귀환 감지 — 로봇명 없이는 어느 로봇을 볼지 모름.
    → 따라서 이 엔드포인트는 즉시 IDLE 로봇을 확인하고 배정한다.

    실제 구현:
    - in-memory robot_status 딕셔너리를 직접 참조하지 않고
      robots 라우터의 get_robot_status()를 import해 사용한다.
    """
    from routers.robots import robot_status

    current_hour = datetime.now().hour
    room = crud.get_available_room_today(db, current_hour)
    if not room:
        raise HTTPException(status_code=503, detail="현재 시간대 빈 상담실 없음")

    # IDLE 로봇 선택 (limo1 우선)
    robot = _pick_idle_robot(robot_status)
    if not robot:
        raise HTTPException(status_code=503, detail="안내 로봇이 모두 사용 중")

    # walk-in 예약 행 삽입 (중복 배정 방지)
    reservation = crud.create_walkin_reservation(db, room, current_hour)

    label = ROOM_LABELS.get(room, room)
    tts_text = f"{label}로 안내해드릴게요."

    mission_data = schemas.MissionCreate(
        reservation_id=reservation.id,
        destination=room,
        tts_text=tts_text,
    )
    mission = crud.create_mission(db, mission_data)

    crud.create_log(db, log_type="mission_start",
                    message=f"현장방문 안내 배정: {label} ({robot})")

    return schemas.WalkinAssignResponse(
        mission_id=mission.id,
        robot=robot,
        room=room,
    )


def _pick_idle_robot(status: dict) -> str | None:
    """limo1 우선으로 IDLE 로봇 반환. 없으면 None."""
    for robot in ("limo1", "limo2"):
        if status.get(robot) == "IDLE":
            return robot
    return None
