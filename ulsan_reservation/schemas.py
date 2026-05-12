# Pydantic 스키마 정의 파일
# API 요청/응답의 데이터 형식과 유효성 검사를 담당한다
#
# models.py(SQLAlchemy)와 schemas.py(Pydantic)를 분리하는 이유:
# - DB 구조와 API 입출력 형식이 반드시 일치하지 않을 수 있음
# - 예: DB에는 모든 컬럼이 있어도 API 응답에서는 일부만 노출할 수 있음
# - 요청 데이터의 타입 검증, 직렬화/역직렬화를 Pydantic이 자동 처리

from pydantic import BaseModel, field_validator
from datetime import date
from enum import Enum


class ReservationStatus(str, Enum):
    """
    API 요청/응답에서 사용하는 예약 상태 열거형
    str을 상속받아 JSON 직렬화 시 문자열로 표현됨
    models.py의 ReservationStatus와 값은 동일하나 역할이 다름
    """
    PENDING     = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"


class ReservationCreate(BaseModel):
    """
    예약 생성 요청 스키마 (웹 예약 UI → POST /reservations)

    클라이언트가 보내야 할 필드를 정의한다
    room과 status는 서버에서 자동 결정하므로 요청에 포함하지 않음
    """
    name:      str   # 예약자 이름
    phone:     str   # 전화번호 전체 (저장 후 끝 4자리로 조회에 사용)
    date:      date  # 예약 날짜 (YYYY-MM-DD 형식으로 자동 파싱)
    time_slot: int   # 예약 시간대 (9~16)

    @field_validator("time_slot")
    @classmethod
    def validate_time_slot(cls, v):
        # 운영 시간(09~16시) 외 요청은 즉시 400 에러 반환
        if v < 9 or v > 16:
            raise ValueError("time_slot은 9~16 사이여야 합니다.")
        return v


class ReservationResponse(BaseModel):
    """
    예약 조회/생성 응답 스키마

    SQLAlchemy Reservation 객체를 JSON으로 변환할 때 사용한다
    from_attributes=True: SQLAlchemy 모델 객체를 dict처럼 읽어 변환 허용
    """
    id:        int
    name:      str
    phone:     str
    date:      date
    time_slot: int
    room:      str
    status:    ReservationStatus

    class Config:
        from_attributes = True  # SQLAlchemy 모델 → Pydantic 변환 활성화


class StatusUpdate(BaseModel):
    """
    예약 상태 변경 요청 스키마 (PATCH /reservations/{id})

    터치 UI 체크인 시: PENDING → IN_PROGRESS
    LIMO 홈 복귀 완료 시: IN_PROGRESS → COMPLETED
    """
    status: ReservationStatus
