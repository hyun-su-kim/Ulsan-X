# 로봇 상태 라우터
#
# in-memory 딕셔너리로 두 로봇의 현재 상태를 관리한다.
# DB에 저장하지 않는 이유: 상태 변화가 초 단위로 빈번하고, 서버 재시작 시 로봇이
# 첫 번째 상태 발행과 함께 자동으로 상태를 갱신하므로 영속성이 필요 없다.
#
# POST /robots/{id}/status  — ulsan_dispatcher가 로봇 상태 변경 시 호출
# GET  /robots/status       — 태블릿 GuidingPage 폴링용 전체 상태 조회

from fastapi import APIRouter, HTTPException
import schemas

router = APIRouter(prefix="/robots", tags=["robots"])

# 서버 시작 시 두 로봇 모두 IDLE로 초기화
# 실제 상태는 ulsan_dispatcher가 /limo1(2)/robot_status를 수신해 업데이트한다
robot_status: dict[str, str] = {
    "limo1": "IDLE",
    "limo2": "IDLE",
}


@router.post("/{robot_id}/status")
def update_robot_status(robot_id: str, body: schemas.RobotStatusUpdate):
    """
    ulsan_dispatcher가 /limo1(or 2)/robot_status 토픽 수신 시 호출.

    robot_id: "limo1" | "limo2"
    body.status: "IDLE" | "BUSY" | "RETURNING" | "WAITING"
    """
    if robot_id not in robot_status:
        raise HTTPException(status_code=404, detail=f"알 수 없는 로봇: {robot_id}")
    robot_status[robot_id] = body.status
    return {"ok": True}


@router.get("/status")
def get_robot_status():
    """
    두 로봇의 현재 상태를 반환.

    반환 예시: {"limo1": "BUSY", "limo2": "IDLE"}
    태블릿 GuidingPage가 0.5초마다 폴링하여 귀환 감지에 사용.
    """
    return robot_status
