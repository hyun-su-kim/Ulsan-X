# Pydantic 스키마 정의 파일
# API 요청/응답의 데이터 형식과 유효성 검사를 담당한다
#
# models.py(SQLAlchemy)와 schemas.py(Pydantic)를 분리하는 이유:
# - DB 구조와 API 입출력 형식이 반드시 일치하지 않을 수 있음
# - 예: DB에는 모든 컬럼이 있어도 API 응답에서는 일부만 노출할 수 있음
# - 요청 데이터의 타입 검증, 직렬화/역직렬화를 Pydantic이 자동 처리

from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional
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
    time_slot: int   # 예약 시간대 (9~17)

    @field_validator("time_slot")
    @classmethod
    def validate_time_slot(cls, v):
        # 운영 시간(09~17시) 외 요청은 즉시 400 에러 반환
        if v < 9 or v > 17:
            raise ValueError("time_slot은 9~17 사이여야 합니다.")
        return v


class ReservationUpdate(BaseModel):
    """
    예약 변경 요청 스키마 (웹 예약 UI → PUT /reservations/{id})

    날짜와 시간대만 변경 가능하다
    이름/전화번호는 본인 확인 용도라 변경 불가
    변경 시 새 날짜+시간대에 빈 상담실이 없으면 400 에러 반환
    """
    date:      date
    time_slot: int

    @field_validator("time_slot")
    @classmethod
    def validate_time_slot(cls, v):
        if v < 9 or v > 17:
            raise ValueError("time_slot은 9~17 사이여야 합니다.")
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


# ── 미션 스키마 ─────────────────────────────────────────────────────────────

class MissionStatus(str, Enum):
    PENDING   = "PENDING"
    ACTIVE    = "ACTIVE"
    COMPLETED = "COMPLETED"


class AssignReservationRequest(BaseModel):
    reservation_id: int

class AssignClassroomRequest(BaseModel):
    classroom: str


class MissionCreate(BaseModel):
    """POST /assign, /walkin/assign, /assign/classroom에서 서버 내부적으로 사용"""
    reservation_id: Optional[int] = None
    destination:    str
    tts_text:       str
    robot_assigned: Optional[str] = None


class MissionResponse(BaseModel):
    """ulsan_dispatcher 폴링 응답 및 배정 결과 반환"""
    id:             int
    reservation_id: Optional[int]
    destination:    str
    tts_text:       str
    status:         MissionStatus
    robot_assigned: Optional[str]
    created_at:     datetime

    class Config:
        from_attributes = True


class AssignResponse(BaseModel):
    """POST /assign 성공 응답 — 태블릿 UI가 받는 형식

    로봇 선택은 ulsan_dispatcher가 디스패치 시점에 단독 수행하므로
    생성 응답에는 robot이 없다. 태블릿은 GET /assign/{mission_id}를
    폴링해 배정 로봇과 진행 상태를 확인한다.

    queued=True면 임무 생성 시점에 가용(IDLE) 로봇이 없어 대기열에
    들어간 것 — 태블릿은 "대기 안내" 화면을 띄운다. 로봇이 복귀하면
    ulsan_dispatcher가 FIFO로 꺼내 배정한다.
    """
    mission_id: int
    queued:     bool = False


class MissionStatusResponse(BaseModel):
    """GET /assign/{mission_id} 응답 — 태블릿 GuidingPage 폴링용"""
    status:         MissionStatus
    robot_assigned: Optional[str]   # PENDING 동안 None, dispatcher 배정 후 채워짐


class RobotStatusUpdate(BaseModel):
    """POST /robots/{id}/status — ulsan_dispatcher가 상태 변경 시 전송"""
    status: str   # "IDLE" | "BUSY" | "RETURNING" | "WAITING"


# ── 로그 스키마 ─────────────────────────────────────────────────────────────

class LogResponse(BaseModel):
    id:         int
    type:       str
    message:    str
    created_at: datetime

    class Config:
        from_attributes = True


# ── 현장 방문 스키마 ─────────────────────────────────────────────────────────

class WalkinAssignResponse(BaseModel):
    """POST /walkin/assign 성공 응답 — 배정 로봇은 GET /assign/{mission_id}로 확인"""
    mission_id: int
    room:       str   # 배정된 상담실 키 (예: counseling_1)
    queued:     bool = False   # True면 가용 로봇 없어 대기열 진입
