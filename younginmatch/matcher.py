# -*- coding: utf-8 -*-
"""RFP 평가기준 파싱 및 인력 매칭 모듈.

GPT-4o를 2단계로 호출하여:
  1단계: RFP 텍스트에서 평가 기준(점수표)을 JSON으로 파싱
  2단계: 파싱된 기준 + CV/실적 데이터로 인력별 점수를 계산
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

load_dotenv(Path(__file__).parents[1] / ".env")
load_dotenv(Path(__file__).parent / ".env")


class APIKeyMissingError(RuntimeError):
    """Raised when OpenAI API key configuration is missing."""


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise APIKeyMissingError(
            "OPENAI_API_KEY가 설정되지 않았습니다. younginmatch/.env 파일에 API 키를 추가하세요."
        )

    return OpenAI(api_key=api_key)

_PARSE_SYSTEM_PROMPT = """당신은 공공 발주 RFP(제안요청서)의 참여인력 평가기준을 분석하는 전문가입니다.

주어진 RFP 텍스트에서 인력 평가기준을 파악하여 반드시 아래 JSON 형식으로만 응답하세요.
JSON 외 어떠한 텍스트도 포함하지 마세요.

응답 형식:
{
  "유사사업_정의": "예: 국내외 110kV 이상 송전 또는 변전 사업",
  "컨설팅_유형": "예: 예비타당성조사, 타당성조사, 기본설계, 상세설계 등",
  "평가항목": [
    {
      "항목명": "PM 자격",
      "배점": 1.0,
      "구간": [
        {"조건": "기술사", "점수": 1.0},
        {"조건": "특급기술자", "점수": 0.9},
        {"조건": "고급기술자", "점수": 0.8},
        {"조건": "중급기술자", "점수": 0.7},
        {"조건": "초급기술자", "점수": 0.6}
      ],
      "비고": ""
    }
  ],
  "등급_가중치": {
    "기술사": 1.0,
    "특급기술자": 0.9,
    "고급기술자": 0.8,
    "중급기술자": 0.7,
    "초급기술자": 0.6,
    "기타": 0.5
  },
  "경력_최대인정_년수": 8,
  "실적_최대인정_건수": 8
}

항목이 RFP에 없으면 해당 필드를 null로 설정하세요.
구간이 명시되지 않은 경우 빈 배열([])로 설정하세요.
"""

_MATCH_SYSTEM_PROMPT = """당신은 전력·에너지 분야 엔지니어링 인력 매칭 전문가입니다.

제공된 RFP 평가기준 JSON과 인력 데이터, 회사 실적 데이터를 바탕으로
각 인력의 항목별 점수를 계산하고 추천 결과를 JSON으로 반환하세요.

계산 규칙:
1. 경력년수는 등급 가중치를 곱한 후 최대 인정년수로 캡핑
   예) 특급기술자 12년 × 0.9 = 10.8년 → 8년으로 캡핑
2. 실적건수는 유사사업 정의에 해당하는 프로젝트명만 카운트, 최대 인정건수로 캡핑
3. 각 구간표에서 해당 구간의 점수를 찾아 적용
4. 점수를 찾을 수 없으면 가장 낮은 구간 점수 적용

[추천_포지션 작성 규칙 — 매우 중요]
- 인력 데이터의 "참여분야"에 포함된 모든 분야 키워드(송전, 변전, 배전, 토목, 건축, 통신, 원자력, 화력, 산업시설 등)와
  "참여업무명"에서 식별되는 분야를 누락 없이 모두 명시해야 합니다.
- 형식 예시: "PM / 전기(송전·변전) / 토목" 또는 "전기(송전)", "전기(변전·배전)" 등.
- 송전 실적(T/L, 송전선로, 송전탑, 가공송전선로 등)이 1건이라도 있으면 반드시 "송전"을 포함.
- 변전 실적(S/S, 변전소, GIS, M.Tr, Switchgear 등)이 1건이라도 있으면 반드시 "변전"을 포함.
- 토목/건축 관련 키워드(토목, 구조, 건축, 측량)가 해당분야·참여분야·참여업무명에 있으면 "토목" 또는 "건축"을 포함.
- 모든 평가항목 점수가 일정 수준 이상이고 PM 자격(기술사/특급+장기경력)이 있으면 "PM"을 추가.
- "추천_포지션"은 후속 단계에서 키워드 매칭에 사용되므로, 인력의 실제 보유 역량을 빠짐없이 나열하는 것이 중요합니다.

반드시 아래 JSON 형식으로만 응답하세요. JSON 외 어떠한 텍스트도 포함하지 마세요.

{
  "매칭결과": [
    {
      "성명": "홍길동",
      "등급": "고급기술자",
      "경력년수_원본": 10.3,
      "경력년수_가중적용": 8.2,
      "경력년수_인정": 8.0,
      "유사실적_건수": 6,
      "유사실적_인정건수": 6,
      "유사실적_목록": ["프로젝트명1", "프로젝트명2"],
      "항목별점수": [
        {"항목명": "PM 자격", "배점": 1.0, "획득점수": 0.8, "근거": "고급기술자 해당"},
        {"항목명": "PM 경력", "배점": 2.0, "획득점수": 2.0, "근거": "가중적용 후 8년 이상"}
      ],
      "총점": 8.2,
      "최대_가능점수": 15.0,
      "추천_포지션": "PM / 전기(송전·변전)",
      "추천_이유": "송전 T/L 실적 다수, 변전 분야 경력 10년 이상 보유",
      "주의사항": "기술사 자격 미보유로 PM 자격점수 감점"
    }
  ],
  "추천_순위": ["성명1", "성명2", "성명3"],
  "종합_의견": "전체 인력에 대한 종합 평가 의견"
}
"""


def parse_rfp_criteria(rfp_text: str) -> dict:
    """RFP 텍스트에서 평가기준을 파싱하여 JSON으로 반환.

    Args:
        rfp_text: RFP 문서 전문 텍스트.

    Returns:
        평가기준이 담긴 딕셔너리. 파싱 실패 시 빈 딕셔너리.
    """
    logger.info("🔍 [1단계] RFP 평가기준 파싱 중...")

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 RFP 텍스트를 분석하여 평가기준 JSON을 추출하세요:\n\n{rfp_text}"},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    try:
        result = json.loads(raw)
        logger.info(f"✅ 평가기준 파싱 완료: {len(result.get('평가항목', []))}개 항목")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ 평가기준 JSON 파싱 실패: {e}")
        return {}


def match_personnel(
    criteria: dict,
    context_text: str,
    rfp_text: str,
) -> dict:
    """파싱된 평가기준과 인력 데이터를 바탕으로 인력 매칭 점수를 계산.

    Args:
        criteria: parse_rfp_criteria() 반환값.
        context_text: build_context_text() 반환값 (인력 + 실적 통합 텍스트).
        rfp_text: 원본 RFP 텍스트 (보충 컨텍스트용).

    Returns:
        매칭 결과가 담긴 딕셔너리. 실패 시 빈 딕셔너리.
    """
    logger.info("🤖 [2단계] 인력 매칭 점수 계산 중...")

    user_content = f"""
[RFP 평가기준 JSON]
{json.dumps(criteria, ensure_ascii=False, indent=2)}

[인력 및 회사 실적 데이터]
{context_text}

[RFP 원문 (참고)]
{rfp_text[:3000]}

위 데이터를 바탕으로 각 인력의 점수를 계산하고 매칭 결과 JSON을 반환하세요.
유사사업 판단 시 프로젝트명과 발주처를 종합적으로 고려하세요.
"""

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _MATCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    try:
        result = json.loads(raw)
        count = len(result.get("매칭결과", []))
        logger.info(f"✅ 인력 매칭 완료: {count}명 결과 생성")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ 매칭 결과 JSON 파싱 실패: {e}")
        return {}


def run_matching_pipeline(
    rfp_text: str,
    context_text: str,
) -> tuple[dict, dict]:
    """RFP 분석부터 인력 매칭까지 전체 파이프라인 실행.

    Args:
        rfp_text: RFP 문서 텍스트.
        context_text: 인력 + 실적 통합 컨텍스트 텍스트.

    Returns:
        (criteria, match_result) 튜플.
        - criteria: 파싱된 평가기준 딕셔너리
        - match_result: 매칭 결과 딕셔너리
    """
    criteria = parse_rfp_criteria(rfp_text)
    if not criteria:
        logger.warning("⚠️ 평가기준 파싱 결과가 비어있습니다.")

    match_result = match_personnel(criteria, context_text, rfp_text)
    return criteria, match_result


def ask_followup(
    question: str,
    criteria: dict,
    match_result: dict,
    context_text: str,
    chat_history: list[dict],
) -> str:
    """매칭 결과에 대한 추가 질문에 답변.

    Args:
        question: 사용자 추가 질문.
        criteria: 파싱된 평가기준.
        match_result: 이전 매칭 결과.
        context_text: 인력 + 실적 컨텍스트.
        chat_history: 이전 대화 이력 ({"role": ..., "content": ...} 형식).

    Returns:
        GPT 답변 문자열.
    """
    system_msg = f"""당신은 영인에너지솔루션의 인력 매칭 전문 AI 어시스턴트입니다.
이미 RFP 분석과 인력 매칭이 완료된 상태에서 추가 질문에 답변합니다.
항상 한국어로 답변하세요.

[평가기준 요약]
{json.dumps(criteria, ensure_ascii=False, indent=2)[:1500]}

[매칭 결과 요약]
{json.dumps(match_result, ensure_ascii=False, indent=2)[:2000]}

[인력 데이터]
{context_text[:2000]}
"""

    messages = [{"role": "system", "content": system_msg}]
    messages.extend(chat_history[-6:])  # 최근 6개 이력만 유지
    messages.append({"role": "user", "content": question})

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content or ""
