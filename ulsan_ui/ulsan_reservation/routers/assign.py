# 임무 배정 라우터
#
# POST  /assign                — 예약 체크인 후 로봇 임무 배정
# POST  /assign/classroom      — 강의실 안내 배정 (DB 기록 없음)
# GET   /assign/pending        — wego_dispatcher 폴링용 미결 미션 조회
# PATCH /assign/{id}/start     — wego_dispatcher: PENDING → ACTIVE
# PATCH /assign/{id}/complete  — wego_dispatcher: ACTIVE → COMPLETED

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db

router = APIRouter(prefix="/assign", tags=["assign"])

# 상담실 키 → TTS 표시명
ROOM_LABELS = {
    "counseling_1":           "상담실 1",
    "counseling_2":           "상담실 2",
    "intensive_counseling_1": "집중상담실 1",
    "intensive_counseling_2": "집중상담실 2",
}

# 강의실 키 → TTS 표시명
CLASSROOM_LABELS = {
    "classroom_1": "1강의실",
    "classroom_2": "2강의실",
    "classroom_3": "3강의실",
    "classroom_4": "4강의실",
    "classroom_5": "5강의실",
}


@router.post("", response_model=schemas.AssignResponse)
def assign_reservation(body: schemas.AssignReservationRequest, db: Session = Depends(get_db)):
    """
    예약 체크인 후 로봇 임무 배정.

    CheckinResultPage에서 [안내 시작] 클릭 시 호출된다.
    IDLE 로봇을 즉시 선택하고 missions 테이블에 PENDING 미션을 생성한다.
    wego_dispatcher는 폴링으로 이 미션을 수락한다.
    """
    from routers.robots import robot_status

    reservation = (
        db.query(models.Reservation)
        .filter(models.Reservation.id == body.reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없음")

    robot = _pick_idle_robot(robot_status)
    if not robot:
        raise HTTPException(status_code=503, detail="안내 로봇이 모두 사용 중")

    label = ROOM_LABELS.get(reservation.room, reservation.room)
    tts_text = f"{reservation.name}님 {reservation.time_slot}시 상담 예약으로 {label}로 안내합니다."

    mission = crud.create_mission(db, schemas.MissionCreate(
        reservation_id=body.reservation_id,
        destination=reservation.room,
        tts_text=tts_text,
    ))

    return schemas.AssignResponse(mission_id=mission.id, robot=robot)


@router.post("/classroom", response_model=schemas.AssignResponse)
def assign_classroom(body: schemas.AssignClassroomRequest, db: Session = Depends(get_db)):
    """
    강의실 안내 배정.

    ClassroomPage에서 강의실 버튼 클릭 시 호출된다.
    DB 기록 없이 미션만 생성한다 (강의실 안내는 예약 없는 임시 안내).

    classroom: "classroom_1" ~ "classroom_5"
    """
    from routers.robots import robot_status

    if body.classroom not in CLASSROOM_LABELS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 강의실: {body.classroom}")

    robot = _pick_idle_robot(robot_status)
    if not robot:
        raise HTTPException(status_code=503, detail="안내 로봇이 모두 사용 중")

    label = CLASSROOM_LABELS[body.classroom]
    tts_text = f"{label}로 안내해드릴게요."

    mission = crud.create_mission(db, schemas.MissionCreate(
        reservation_id=None,
        destination=body.classroom,
        tts_text=tts_text,
    ))

    return schemas.AssignResponse(mission_id=mission.id, robot=robot)


@router.get("/pending", response_model=list[schemas.MissionResponse])
def get_pending(db: Session = Depends(get_db)):
    """
    wego_dispatcher 폴링용 — PENDING 상태 미션 전체 조회.

    0.5초 간격으로 호출된다. 미션이 없으면 빈 리스트 반환.
    """
    return crud.get_pending_missions(db)


@router.patch("/{mission_id}/start")
def start_mission(mission_id: int, robot: str, db: Session = Depends(get_db)):
    """
    wego_dispatcher가 로봇에 goal 발행 완료 후 PENDING → ACTIVE로 변경.

    robot: "limo1" | "limo2"
    """
    mission = crud.start_mission(db, mission_id, robot)
    if not mission:
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없음")
    return {"ok": True}


@router.patch("/{mission_id}/complete")
def complete_mission(mission_id: int, db: Session = Depends(get_db)):
    """
    로봇 홈 복귀 확인 후 wego_dispatcher가 ACTIVE → COMPLETED로 변경.
    연결된 예약이 있으면 함께 COMPLETED 처리.
    """
    mission = crud.complete_mission(db, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없음")
    return {"ok": True}


def _pick_idle_robot(status: dict) -> str | None:
    """limo1 우선으로 IDLE 로봇 반환."""
    for robot in ("limo1", "limo2"):
        if status.get(robot) == "IDLE":
            return robot
    return None
