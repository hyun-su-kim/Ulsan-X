# DB 쿼리 함수 모음 (CRUD: Create, Read, Update, Delete)
# 라우터(routers/reservations.py)에서 호출한다
# DB 로직을 라우터와 분리함으로써 코드 재사용성과 가독성을 높인다

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
import models
import schemas

# 상담실 배정 순서: 일반 상담실 우선, 이후 집중 상담실
ROOMS = [
    "counseling_1",
    "counseling_2",
    "intensive_counseling_1",
    "intensive_counseling_2",
]


def _get_available_room(db: Session, target_date: date, time_slot: int, exclude_id: int = None):
    """
    특정 날짜 + 시간대에서 배정 가능한 상담실 반환 (내부 헬퍼 함수)

    exclude_id: 예약 변경 시 자신의 예약은 제외하고 빈 방 탐색
    반환값: 배정 가능한 상담실 이름 또는 None (만석)
    """
    query = db.query(models.Reservation.room).filter(
        and_(
            models.Reservation.date == target_date,
            models.Reservation.time_slot == time_slot,
        )
    )

    # 변경 대상 예약 자신은 제외 (자신의 슬롯은 비어있는 것으로 간주)
    if exclude_id is not None:
        query = query.filter(models.Reservation.id != exclude_id)

    taken_rooms = [row[0] for row in query.all()]
    available = [r for r in ROOMS if r not in taken_rooms]
    return available[0] if available else None


def create_reservation(db: Session, data: schemas.ReservationCreate):
    """
    예약 생성 및 상담실 자동 배정

    동작 순서:
    1. 요청한 날짜 + 시간대에 이미 예약된 상담실 목록 조회
    2. ROOMS 순서대로 비어있는 첫 번째 상담실 배정
    3. 모든 상담실이 찼으면 None 반환 (라우터에서 400 에러 처리)

    평일 여부와 예약 가능 기간(당일~2주)은 라우터에서 사전 검증한다
    """
    room = _get_available_room(db, data.date, data.time_slot)
    if not room:
        return None

    reservation = models.Reservation(
        name=data.name,
        phone=data.phone,
        date=data.date,
        time_slot=data.time_slot,
        room=room,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def get_full_slots(db: Session, target_date: date):
    """
    특정 날짜에서 만석(4개 예약)인 시간대 목록 반환

    프론트엔드에서 날짜 선택 시 호출하여 만석 시간대를 회색으로 비활성화할 때 사용
    상담실이 4개이므로 예약 수 >= 4이면 만석
    """
    from sqlalchemy import func

    # 날짜별 time_slot 예약 건수 집계
    counts = (
        db.query(models.Reservation.time_slot, func.count(models.Reservation.id))
        .filter(models.Reservation.date == target_date)
        .group_by(models.Reservation.time_slot)
        .all()
    )

    # 예약 건수가 4 이상인 시간대만 반환
    return [slot for slot, count in counts if count >= 4]


def get_today_reservations(db: Session, today: date):
    """
    오늘 날짜 예약 전체 조회 (관제 GUI용)

    관제 GUI에서 오늘의 예약 현황과 각 예약의 진행 상태를 표시할 때 사용
    """
    return (
        db.query(models.Reservation)
        .filter(models.Reservation.date == today)
        .order_by(models.Reservation.time_slot)
        .all()
    )


def get_my_reservations(db: Session, name: str, phone_last4: str, today: date):
    """
    이름 + 전화번호 끝 4자리로 본인의 취소/변경 가능한 예약 목록 조회

    오늘 이후 PENDING 상태만 반환한다
    - 오늘 이전: 이미 지난 예약이므로 조회 불필요
    - IN_PROGRESS / COMPLETED: 안내 중이거나 완료된 예약이므로 변경 불가
    """
    return (
        db.query(models.Reservation)
        .filter(
            and_(
                models.Reservation.name == name,
                models.Reservation.phone.endswith(phone_last4),
                models.Reservation.date >= today,   # 오늘 포함 미래 예약만
                models.Reservation.status == models.ReservationStatus.PENDING,
            )
        )
        .order_by(models.Reservation.date, models.Reservation.time_slot)
        .all()
    )


def check_reservation(db: Session, name: str, phone_last4: str, today: date):
    """
    이름 + 전화번호 끝 4자리로 오늘 예약 조회 (터치 UI용)

    터치 UI에서 방문자가 이름과 전화번호 끝 4자리를 입력하면
    오늘 날짜의 PENDING 상태 예약을 찾아 반환한다

    PENDING만 조회하는 이유:
    - IN_PROGRESS: 이미 안내 중 → 중복 체크인 방지
    - COMPLETED: 안내 완료 → 재체크인 방지
    """
    return (
        db.query(models.Reservation)
        .filter(
            and_(
                models.Reservation.name == name,
                models.Reservation.phone.endswith(phone_last4),
                models.Reservation.date == today,
                models.Reservation.status == models.ReservationStatus.PENDING,
            )
        )
        .first()
    )


def update_reservation(db: Session, reservation_id: int, data: schemas.ReservationUpdate):
    """
    예약 날짜/시간 변경 및 상담실 재배정

    동작 순서:
    1. 변경 대상 예약 조회 (없거나 PENDING 아니면 None 반환)
    2. 새 날짜+시간대에서 빈 상담실 탐색 (자신의 현재 슬롯 제외)
    3. 빈 방 없으면 None 반환 (라우터에서 400 처리)
    4. 날짜, 시간대, 상담실 업데이트
    """
    reservation = (
        db.query(models.Reservation)
        .filter(
            and_(
                models.Reservation.id == reservation_id,
                models.Reservation.status == models.ReservationStatus.PENDING,
            )
        )
        .first()
    )

    if not reservation:
        return None, "not_found"

    # 변경할 슬롯에서 빈 상담실 탐색 (자신 제외)
    room = _get_available_room(db, data.date, data.time_slot, exclude_id=reservation_id)
    if not room:
        return None, "full"

    reservation.date      = data.date
    reservation.time_slot = data.time_slot
    reservation.room      = room
    db.commit()
    db.refresh(reservation)
    return reservation, "ok"


def delete_reservation(db: Session, reservation_id: int):
    """
    예약 취소 (DB에서 삭제)

    PENDING 상태 예약만 취소 가능하다
    IN_PROGRESS(안내 중)이거나 COMPLETED(완료)된 예약은 취소 불가
    반환값: True(성공), False(없거나 취소 불가)
    """
    reservation = (
        db.query(models.Reservation)
        .filter(
            and_(
                models.Reservation.id == reservation_id,
                models.Reservation.status == models.ReservationStatus.PENDING,
            )
        )
        .first()
    )

    if not reservation:
        return False

    db.delete(reservation)
    db.commit()
    return True


def update_status(db: Session, reservation_id: int, status: schemas.ReservationStatus):
    """
    예약 상태 변경

    호출 시점:
    - 터치 UI 체크인 확인 버튼: PENDING → IN_PROGRESS
    - wego_behaviour FSM RETURNING 완료: IN_PROGRESS → COMPLETED

    reservation_id에 해당하는 예약이 없으면 None 반환 (라우터에서 404 처리)
    """
    reservation = (
        db.query(models.Reservation)
        .filter(models.Reservation.id == reservation_id)
        .first()
    )

    if not reservation:
        return None

    reservation.status = models.ReservationStatus(status.value)
    db.commit()
    db.refresh(reservation)
    return reservation
