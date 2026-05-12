# DB 쿼리 함수 모음 (CRUD: Create, Read, Update, Delete)
# 라우터(routers/reservations.py)에서 호출한다
# DB 로직을 라우터와 분리함으로써 코드 재사용성과 가독성을 높인다

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date, timedelta
import models
import schemas

# 상담실 배정 순서: 일반 상담실 우선, 이후 집중 상담실
ROOMS = [
    "counseling_1",
    "counseling_2",
    "intensive_counseling_1",
    "intensive_counseling_2",
]


def create_reservation(db: Session, data: schemas.ReservationCreate):
    """
    예약 생성 및 상담실 자동 배정

    동작 순서:
    1. 요청한 날짜 + 시간대에 이미 예약된 상담실 목록 조회
    2. ROOMS 순서대로 비어있는 첫 번째 상담실 배정
    3. 모든 상담실이 찼으면 None 반환 (라우터에서 400 에러 처리)

    평일 여부와 예약 가능 기간(당일~2주)은 라우터에서 사전 검증한다
    """
    # 해당 날짜 + 시간대에 이미 배정된 상담실 이름 목록 조회
    taken_rooms = [
        row[0]
        for row in db.query(models.Reservation.room).filter(
            and_(
                models.Reservation.date == data.date,
                models.Reservation.time_slot == data.time_slot,
            )
        ).all()
    ]

    # ROOMS 순서대로 첫 번째 빈 상담실 선택
    available = [r for r in ROOMS if r not in taken_rooms]
    if not available:
        # 4개 상담실 모두 예약됨 → 해당 시간대 예약 불가
        return None

    # 예약 객체 생성 후 DB에 저장
    reservation = models.Reservation(
        name=data.name,
        phone=data.phone,
        date=data.date,
        time_slot=data.time_slot,
        room=available[0],  # 배정 순서 중 첫 번째 빈 상담실
    )
    db.add(reservation)
    db.commit()           # DB에 실제 반영
    db.refresh(reservation)  # DB에서 자동 생성된 id 등 최신값 반영
    return reservation


def get_today_reservations(db: Session, today: date):
    """
    오늘 날짜 예약 전체 조회 (관제 GUI용)

    관제 GUI에서 오늘의 예약 현황과 각 예약의 진행 상태를 표시할 때 사용
    """
    return (
        db.query(models.Reservation)
        .filter(models.Reservation.date == today)
        .order_by(models.Reservation.time_slot)  # 시간순 정렬
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
                models.Reservation.phone.endswith(phone_last4),  # 끝 4자리 일치 확인
                models.Reservation.date == today,
                models.Reservation.status == models.ReservationStatus.PENDING,
            )
        )
        .first()  # 조건 만족하는 첫 번째 결과만 반환 (없으면 None)
    )


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

    # Pydantic enum 값을 SQLAlchemy enum으로 변환하여 저장
    reservation.status = models.ReservationStatus(status.value)
    db.commit()
    db.refresh(reservation)
    return reservation
