import os
import yaml
import google.generativeai as genai
from ament_index_python.packages import get_package_share_directory

# ── 키워드 매핑 ────────────────────────────────────────────────────────────────
# 발화 텍스트에서 목적지 키를 찾는 1차 수단.
# 키워드를 길이 내림차순으로 정렬해 순회하므로
# "상담실2"가 "상담실"보다 먼저 비교됨 → 오매핑 방지.
KEYWORD_MAP: dict[str, str] = {
    "집중상담실1": "intensive_counseling_1",
    "집중상담실 1": "intensive_counseling_1",
    "집중상담실2": "intensive_counseling_2",
    "집중상담실 2": "intensive_counseling_2",
    "집중상담실": "intensive_counseling_1",
    "상담실1": "counseling_1",
    "상담실 1": "counseling_1",
    "상담실2": "counseling_2",
    "상담실 2": "counseling_2",
    "상담실": "counseling_1",
    "1강의실": "classroom_1",
    "일강의실": "classroom_1",
    "2강의실": "classroom_2",
    "이강의실": "classroom_2",
    "3강의실": "classroom_3",
    "삼강의실": "classroom_3",
    "4강의실": "classroom_4",
    "사강의실": "classroom_4",
    "5강의실": "classroom_5",
    "오강의실": "classroom_5",
    "카운터": "counter",
    "접수": "counter",
    "멀티룸": "multi",
    "멀티": "multi",
    "회의실": "vice_principal",
}

# 길이 내림차순 정렬 — 모듈 로드 시 1회만 수행
_SORTED_KEYWORDS = sorted(KEYWORD_MAP.keys(), key=len, reverse=True)

# ── Gemini 클라이언트 초기화 ────────────────────────────────────────────────────
# GEMINI_API_KEY 환경변수가 없으면 Gemini fallback은 동작하지 않음.
# API 키는 ~/.ros_env.sh에서 export해 설정.
_api_key = os.environ.get('GEMINI_API_KEY', '')
if _api_key:
    genai.configure(api_key=_api_key)
    _gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    _gemini_model = None

# ── Gemini 프롬프트 템플릿 ──────────────────────────────────────────────────────
# {destinations}: waypoints.yaml의 키+레이블 목록 (런타임에 채워짐)
# {text}: STT로 변환된 방문자 발화
# 키만 반환하도록 지시 → 불필요한 설명 방지
_PROMPT_TEMPLATE = """\
당신은 학원 안내 로봇의 NLU 모듈입니다.
방문자 발화에서 목적지를 파악해 아래 목록 중 정확히 일치하는 키를 반환하세요.

사용 가능한 목적지 (키: 이름):
{destinations}

방문자 발화: "{text}"

규칙:
- 목적지 키만 반환하세요. 설명, 문장 금지.
- 해당하는 목적지가 없으면 unknown 반환.
"""


def load_waypoints() -> dict:
    """wego_behaviour 패키지의 waypoints.yaml을 로드해 반환.

    colcon build 후 ROS2가 패키지 경로를 자동으로 파악하므로
    경로를 하드코딩할 필요 없음.
    반환값 예시: {'classroom_1': {'label': '1강의실', 'x': 6.8, ...}, ...}
    """
    path = os.path.join(
        get_package_share_directory('wego_behaviour'), 'config', 'waypoints.yaml'
    )
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return data.get('waypoints', {})


def _call_gemini(text: str, waypoints: dict) -> str | None:
    """Gemini API로 발화 텍스트에서 목적지 키 추출.

    키워드 매핑 실패 시 호출되는 2차 수단.
    Gemini에게 사용 가능한 목적지 목록과 발화를 함께 전달해
    가장 적합한 waypoint 키를 반환받는다.

    반환값 검증:
    - Gemini가 반환한 키가 실제 waypoints에 존재하는지 확인
    - unknown 또는 알 수 없는 키면 None 반환
    - API 오류, 네트워크 단절 등 예외는 모두 None으로 처리 (파이프라인 중단 방지)
    """
    if _gemini_model is None:
        # API 키 미설정 — Gemini 사용 불가
        return None

    # waypoints에서 홈 위치(home_robot1, home_robot2)는 방문자가 요청하는 목적지가 아니므로 제외
    dest_lines = [
        f"- {key}: {info['label']}"
        for key, info in waypoints.items()
        if not key.startswith('home_')
    ]
    destinations = "\n".join(dest_lines)

    prompt = _PROMPT_TEMPLATE.format(destinations=destinations, text=text)

    try:
        response = _gemini_model.generate_content(
            prompt,
            # 응답을 단일 키 단어로 제한 — 긴 설명 방지
            generation_config=genai.GenerationConfig(
                max_output_tokens=20,
                temperature=0.0,  # 결정적 응답 (랜덤성 제거)
            ),
        )
        result = response.text.strip().lower()

        # Gemini 응답이 실제 존재하는 waypoint 키인지 검증
        # 검증 없이 사용하면 존재하지 않는 목적지로 로봇이 이동 시도할 수 있음
        if result in waypoints:
            return result

        # unknown 또는 잘못된 키 반환 시 None
        return None

    except Exception:
        # 네트워크 오류, API 할당량 초과, 타임아웃 등
        # 예외를 상위로 전파하지 않고 None 반환 → 파이프라인 중단 없음
        return None


def extract_destination(text: str, waypoints: dict | None = None) -> str | None:
    """발화 텍스트에서 목적지 waypoint 키 추출.

    1차: 키워드 매핑 (빠름, 오프라인 동작)
    2차: Gemini API fallback (waypoints 전달 시에만 활성화)
        - "강의실 첫 번째"처럼 키워드 매핑이 실패하는 애매한 표현 처리
        - 네트워크 필요, 1~3초 지연 가능

    Args:
        text: STT 결과 텍스트
        waypoints: load_waypoints() 결과. None이면 Gemini fallback 비활성화.

    Returns:
        waypoint 키 문자열 또는 None
    """
    # ── 1차: 키워드 매핑 ──────────────────────────────────────────────────────
    for keyword in _SORTED_KEYWORDS:
        if keyword in text:
            return KEYWORD_MAP[keyword]

    # ── 2차: Gemini API fallback ──────────────────────────────────────────────
    # waypoints가 전달된 경우에만 실행
    # voice_node.py에서 self._waypoints를 넘겨줌
    if waypoints:
        return _call_gemini(text, waypoints)

    return None
