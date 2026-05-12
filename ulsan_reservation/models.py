# SQLAlchemy ORM 모델 정의 파일
# Python 클래스로 MySQL 테이블 구조를 정의한다
# main.py에서 Base.metadata.create_all()을 호출하면 이 클래스를 보고 테이블을 자동 생성한다

from sqlalchemy import Column, Integer, String, Date, Enum
from database import Base
import enum


class ReservationStatus(enum.Enum):
    """
    예약 상태 열거형 (MySQL ENUM 타입으로 저장됨)

    PENDING     : 예약됨, 아직 방문 전
    IN_PROGRESS : 터치 UI에서 체크인 후 LIMO 안내 시작
    COMPLETED   : LIMO가 홈으로 복귀 완료, 안내 종료
    """
    PENDING     = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"


class Reservation(Base):
    """
    reservations 테이블 정의

    상담 예약 1건 = 이 테이블의 행 1개
    클래스 변수 하나가 컬럼 하나에 대응된다
    """
    __tablename__ = "reservations"

    # 기본키: 자동 증가 정수. 각 예약의 고유 식별자
    id        = Column(Integer, primary_key=True, index=True)

    # 예약자 이름 (최대 50자)
    name      = Column(String(50), nullable=False)

    # 예약자 전화번호 전체 저장 (조회 시 끝 4자리로 검색)
    phone     = Column(String(20), nullable=False)

    # 예약 날짜 (MySQL DATE 타입: YYYY-MM-DD)
    date      = Column(Date, nullable=False)

    # 예약 시간대: 정수로 저장 (9=09시, 10=10시, ... 16=16시)
    time_slot = Column(Integer, nullable=False)

    # 자동 배정된 상담실 이름
    # 배정 순서: counseling_1 → counseling_2 → intensive_counseling_1 → intensive_counseling_2
    room      = Column(String(50), nullable=False)

    # 예약 진행 상태. 기본값은 PENDING
    status    = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING)
