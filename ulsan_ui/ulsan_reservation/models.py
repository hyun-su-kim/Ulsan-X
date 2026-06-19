# SQLAlchemy ORM 모델 정의 파일
# Python 클래스로 MySQL 테이블 구조를 정의한다
# main.py에서 Base.metadata.create_all()을 호출하면 이 클래스를 보고 테이블을 자동 생성한다

from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
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


class MissionStatus(enum.Enum):
    """
    로봇 임무 상태 열거형

    PENDING   : 방문자 UI에서 배정 요청 완료, ulsan_dispatcher가 아직 수락 전
    ACTIVE    : ulsan_dispatcher가 로봇에 goal_destination 발행 완료
    COMPLETED : 로봇 홈 복귀 확인, ulsan_dispatcher가 완료 처리
    """
    PENDING   = "PENDING"
    ACTIVE    = "ACTIVE"
    COMPLETED = "COMPLETED"


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


class Mission(Base):
    """
    missions 테이블: 로봇 임무 1건 = 행 1개

    방문자 UI에서 [안내 시작] 클릭 시 생성된다.
    ulsan_dispatcher가 0.5초 간격으로 PENDING 미션을 폴링하여 로봇에 전달한다.

    reservation_id는 nullable — 강의실 안내(DB 기록 없음)처럼 예약 없는 미션도 허용.
    """
    __tablename__ = "missions"

    id             = Column(Integer, primary_key=True, index=True)
    # 예약 체크인/현장상담 배정 시에만 존재, 강의실 안내는 NULL
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    # ulsan_behaviour가 waypoints.yaml에서 좌표를 찾을 때 쓰는 키 (예: counseling_1, classroom_3)
    destination    = Column(String(50), nullable=False)
    # ulsan_dispatcher가 /speak_text에 발행할 TTS 멘트
    tts_text       = Column(String(200), nullable=False)
    status         = Column(Enum(MissionStatus), default=MissionStatus.PENDING)
    # 배정된 로봇 이름 (limo1 / limo2). ulsan_dispatcher가 결정 후 업데이트
    robot_assigned = Column(String(20), nullable=True)
    created_at     = Column(DateTime, server_default=func.now())


class Log(Base):
    """
    logs 테이블: 관제 GUI 알림 로그

    현재 용도: 노쇼(No-show) 알림
    APScheduler가 매시 10분에 PENDING 예약 중 현재 시간대인 것을 확인하여 로그를 삽입한다.
    """
    __tablename__ = "logs"

    id         = Column(Integer, primary_key=True, index=True)
    # 로그 유형 (현재: "noshow")
    type       = Column(String(30), nullable=False)
    message    = Column(String(300), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
