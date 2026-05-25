# 임무 배정 라우터
#
# POST  /assign                — 예약 체크인 후 로봇 임무 배정 (중복 시 409)
# POST  /assign/classroom      — 강의실 안내 배정 (DB 기록 없음)
# GET   /assign/pending        — wego_dispatcher 폴링용 미결 미션 조회
# GET   /assign/today/by-robot — 관제 GUI용 금일 로봇별 임무 카운트
# PATCH /assign/{id}/start     — wego_dispatcher: PENDING → ACTIVE
# PATCH /assign/{id}/complete  — wego_dispatcher: ACTIVE → COMPLETED
# PATCH /assign/{id}/fail      — wego_dispatcher: ACTIVE → COMPLETED (실패 로그)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import get_db
from constants import ROOM_LABELS, CLASSROOM_LABELS, pick_idle_robot

router = APIRouter(prefix="/assign", tags=["assign"])


@router.post("", response_model=schemas.AssignResponse)
def assign_reservation(body: schemas.AssignReservationRequest, db: Session = Depends(get_db)):
    """
    예약 체크인 후 로봇 임무 배정.

    CheckinResultPage에서 [안내 시작] 클릭 시 호출된다.
    같은 예약에 PENDING/ACTIVE 미션이 이미 있으면 409 반환 (중복 안내 방지).
    IDLE 로봇을 즉시 선택해 missions 테이블에 PENDING 미션으로 생성한다.
    robot_assigned를 생성 시점에 기록해 GuidingPage 폴링 대상 로봇을 확정한다.
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

    existing = crud.get_active_mission_for_reservation(db, body.reservation_id)
    if existing:
        raise HTTPException(status_code=409, detail="이미 진행 중인 안내가 있습니다")

    robot = pick_idle_robot(robot_status)
    if not robot:
        raise HTTPException(status_code=503, detail="안내 로봇이 모두 사용 중")

    label = ROOM_LABELS.get(reservation.room, reservation.room)
    tts_text = f"{reservation.name}님 {reservation.time_slot}시 상담 예약으로 {label}로 안내합니다."

    mission = crud.create_mission(db, schemas.MissionCreate(
        reservation_id=body.reservation_id,
        destination=reservation.room,
        tts_text=tts_text,
        robot_assigned=robot,
    ))

    crud.create_log(db, log_type="mission_start",
                    message=f"예약 안내 배정: {reservation.name}님 → {label} ({robot})")

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

    robot = pick_idle_robot(robot_status)
    if not robot:
        raise HTTPException(status_code=503, detail="안내 로봇이 모두 사용 중")

    label = CLASSROOM_LABELS[body.classroom]
    tts_text = f"{label}로 안내해드릴게요."

    mission = crud.create_mission(db, schemas.MissionCreate(
        reservation_id=None,
        destination=body.classroom,
        tts_text=tts_text,
    ))

    crud.create_log(db, log_type="mission_start",
                    message=f"강의실 안내 배정: {label} ({robot})")

    return schemas.AssignResponse(mission_id=mission.id, robot=robot)


@router.get("/today/by-robot")
def count_today_by_robot(db: Session = Depends(get_db)):
    """
    오늘 생성된 미션을 로봇별로 카운트.

    관제 GUI 로봇 뷰의 '금일 임무 / 완료' 카드에서 사용한다.
    반환 예: {"limo1": {"total": 5, "done": 3}, "limo2": {"total": 2, "done": 2}}
    """
    return crud.count_today_missions_by_robot(db)


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

    crud.create_log(db, log_type="mission_complete",
                    message=f"임무 완료: {mission.destination} ({mission.robot_assigned})")

    return {"ok": True}


@router.patch("/{mission_id}/fail")
def fail_mission(mission_id: int, db: Session = Depends(get_db)):
    """
    임무 실패 후 홈 복귀 확인 시 wego_dispatcher가 호출.

    GUIDING 중 Nav2 실패 → FAILED → RETURNING → IDLE 시퀀스를
    dispatcher가 추적해 /complete 대신 /fail로 호출한다.

    mission.status는 COMPLETED로 마킹하되 logs에 mission_fail 타입으로 기록 →
    "오늘 임무 N건 중 M건 실패" 같은 집계를 logs 테이블 기준으로 가능.
    """
    mission = crud.complete_mission(db, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없음")

    crud.create_log(db, log_type="mission_fail",
                    message=f"임무 실패: {mission.destination} ({mission.robot_assigned})")

    return {"ok": True}


