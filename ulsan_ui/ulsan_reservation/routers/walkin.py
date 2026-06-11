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
from constants import ROOM_LABELS, pick_idle_robot

router = APIRouter(prefix="/walkin", tags=["walkin"])


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
    1. 현재 시간대 빈 상담실 탐색 (없으면 503)
    2. 가용(IDLE) 로봇 유무 확인 (없으면 503 즉답)
    3. reservations 테이블에 walk-in 행 삽입 (동시 방문자 중복 배정 방지)
    4. PENDING 미션 생성 — 어느 로봇이 맡을지는 wego_dispatcher가 디스패치
       시점에 단독 결정하고 PATCH /start로 robot_assigned를 채운다.
       태블릿 GuidingPage는 GET /assign/{mission_id}로 배정 결과를 폴링한다.
    """
    from routers.robots import robot_status

    current_hour = datetime.now().hour
    room = crud.get_available_room_today(db, current_hour)
    if not room:
        raise HTTPException(status_code=503, detail="현재 시간대 빈 상담실 없음")

    if not pick_idle_robot(robot_status):
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
                    message=f"현장방문 안내 배정: {label}")

    return schemas.WalkinAssignResponse(
        mission_id=mission.id,
        room=room,
    )


