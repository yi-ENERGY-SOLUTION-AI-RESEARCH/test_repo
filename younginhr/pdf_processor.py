# -*- coding: utf-8 -*-
"""PDF 처리 및 OpenAI Vision OCR 모듈.

전력기술인 경력확인서 PDF를 이미지로 변환하고,
GPT-4o Vision API를 통해 구조화된 경력 데이터를 추출한다.
"""

import base64
import json
import re
from typing import Any

import fitz  # PyMuPDF
from loguru import logger
from openai import OpenAI

# OCR 추출을 위한 상세 프롬프트
_EXTRACTION_PROMPT = """
당신은 "전력기술인 경력확인서" 문서 분석 전문가입니다.
첨부된 이미지들은 한국전기기술인협회에서 발행한 경력확인서 스캔 이미지입니다.
아래 규칙에 따라 정보를 추출하여 순수 JSON만 반환하세요 (마크다운 코드블록 없이).

## 첫 번째 페이지 추출 항목
- 성명: 한글 이름만 (괄호 안 한자 제외)
- 생년월일: YYYY.MM.DD 형식
- 등급: 고급/중급/초급/특급 중 하나 (괄호 안 등록번호 제외)
- 기술자격: "기술자격" 섹션의 자격종목명 (여러 개면 \\n으로 구분)
- 학력: "학교명\\n학과명(전공)\\n학위" 형식 (여러 학력이면 \\n으로 구분)
- 근무처명_근무기간: 근무처경력 섹션에서 "근무처명\\n(근무기간시작 ~ 신고일현재)" 형식으로 작성
  예시: "(주)영인에너지솔루션\\n(2014.04.14 ~\\n신고일현재)"

## 두 번째 이후 페이지 추출 항목 ("전력기술근무경력 [ 총괄 ]")
테이블의 각 프로젝트 블록마다 하나의 경력 항목으로 추출한다.
각 블록에는 여러 서브 행(본사/참여)이 있으나, 프로젝트 블록 단위로 하나씩 추출한다.

각 항목에서 추출할 필드:
- 착수일: 참여기간 셀의 상단 날짜 (시작일), YYYY.MM.DD 형식
- 준공일: 참여기간 셀의 하단 날짜 (종료일), YYYY.MM.DD 형식
- 참여일수: 괄호 안의 숫자 (예: "(218일/218일)" → "218", "(1,678일/1,678일)" → "1678", 쉼표 제거)
- 참여사업명: 참여사업명 열의 상단 사업명 텍스트
- 발주자: 참여사업명 열의 하단 발주처/발주자 텍스트
- 참여분야: "직무분야/참여분야" 열에는 위아래 두 값이 있다.
  위 행 = 직무분야 (예: "전기") — 이 값은 절대 사용하지 않는다.
  아래 행 = 참여분야 (예: "변전", "화력", "송전", "그 밖의 발송변배전시설", "기타" 등) — 반드시 이 값을 사용한다.
  단, 아래 행이 없고 위 행만 있을 경우에만 위 행 값을 사용한다.
- 담당분야: "담당분야" 열은 위/아래 두 값이 있다. 위 = 담당분야, 아래 = 담당업무.
  반드시 아래 행의 "담당업무" 값을 사용하며 프로젝트마다 1:1로 매칭한다
  (예: "공사감독", "공사감리", "상주감리", "전기기술" 등).
  단, 아래 행이 없을 경우에는 위 행 값을 사용한다.
- 비고: 비고 열의 텍스트 (없으면 빈 문자열, "현재"가 있으면 "현재" 기입)

## 실근무기간
마지막 페이지 하단의 "(실근무기간) (X,XXX일)" 또는 "(실근무기간)(X일)" 에서 숫자만 추출 (쉼표 제거)

## 반환 JSON 형식
{
  "성명": "김종민",
  "생년월일": "1989.01.23",
  "등급": "고급",
  "기술자격": "전기기사",
  "학력": "한경대학교\\n전기공학과\\n학사",
  "근무처명_근무기간": "(주)영인에너지솔루션\\n(2014.04.14 ~\\n신고일현재)",
  "실근무기간_일수": "3774",
  "경력목록": [
    {
      "착수일": "1990.09.05",
      "준공일": "1990.10.30",
      "참여일수": "56",
      "참여사업명": "345KV장항S/S 옥외GIS 도장공사",
      "발주자": "한국전력공사",
      "참여분야": "변전",
      "담당분야": "공사감독",
      "비고": ""
    },
    {
      "착수일": "2021.05.14",
      "준공일": "2021.11.09",
      "참여일수": "180",
      "참여사업명": "154kV울량S/S#2M.Tr및청주울량SW증설공사",
      "발주자": "한국전력공사 충북본부",
      "참여분야": "변전",
      "담당분야": "상주감리",
      "비고": ""
    },
    {
      "착수일": "2022.06.08",
      "준공일": "2023.01.01",
      "참여일수": "208",
      "참여사업명": "전력계통 해석 및 컨설팅",
      "발주자": "",
      "참여분야": "기타",
      "담당분야": "전기기술",
      "비고": "현재"
    }
  ]
}
"""


def _pdf_to_base64_images(pdf_bytes: bytes, dpi: int = 200) -> list[str]:
    """PDF를 페이지별 base64 인코딩 PNG 이미지 목록으로 변환.

    Args:
        pdf_bytes: PDF 파일 바이트 데이터.
        dpi: 렌더링 해상도 (높을수록 OCR 정확도 향상, 기본 200).

    Returns:
        각 페이지의 base64 인코딩 PNG 문자열 목록.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_b64: list[str] = []
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    for page in doc:
        pixmap = page.get_pixmap(matrix=matrix)
        png_bytes = pixmap.tobytes("png")
        images_b64.append(base64.b64encode(png_bytes).decode("utf-8"))

    doc.close()
    logger.info(f"📸 {len(images_b64)}페이지 이미지 변환 완료 (DPI={dpi})")
    return images_b64


def _parse_json_from_response(raw_text: str) -> dict[str, Any]:
    """GPT 응답 텍스트에서 JSON 객체를 파싱한다.

    응답이 토큰 한도로 중간에 잘린 경우, 불완전한 경력 항목을 제거하고
    JSON을 복구하여 파싱을 시도한다.

    Args:
        raw_text: GPT API 응답 텍스트.

    Returns:
        파싱된 딕셔너리.

    Raises:
        ValueError: JSON 파싱에 실패한 경우.
    """
    # 마크다운 코드블록 제거 후 JSON 추출
    cleaned = re.sub(r"```(?:json)?\s*", "", raw_text).replace("```", "").strip()
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not json_match:
        raise ValueError(f"응답에서 JSON을 찾을 수 없습니다: {raw_text[:200]}")

    candidate = json_match.group()

    # 1차: 정상 파싱 시도
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ JSON 파싱 실패 (잘린 응답으로 복구 시도): {e}")

    # 2차: 응답이 토큰 한도로 잘린 경우 복구 시도
    # 마지막으로 완성된 경력 항목까지만 살리고 배열/객체를 닫아준다.
    recovered = _recover_truncated_json(candidate)
    if recovered:
        logger.warning(
            f"🔧 잘린 JSON 복구 완료. "
            f"일부 경력 항목이 누락됐을 수 있습니다."
        )
        return recovered

    raise ValueError(f"JSON 복구 실패. 원문 앞부분: {raw_text[:300]}")


def _recover_truncated_json(text: str) -> dict[str, Any] | None:
    """토큰 한도로 잘린 JSON을 복구한다.

    마지막으로 완성된 경력 항목(닫는 `}`) 위치를 찾아 배열과 최상위 객체를
    올바르게 닫은 뒤 파싱을 재시도한다.

    Args:
        text: 잘린 JSON 문자열.

    Returns:
        복구된 딕셔너리. 복구 불가 시 None.
    """
    # "경력목록" 배열 안의 마지막으로 완결된 항목(}) 위치를 찾는다.
    # 완결된 항목은 "}," 또는 "}\n" 또는 "}" 패턴으로 끝난다.
    last_complete = -1
    for m in re.finditer(r"\}", text):
        # 해당 위치까지 잘라서 JSON 파싱 가능한지 테스트
        trial = text[: m.end()].rstrip().rstrip(",")
        # 열린 괄호/브라켓 개수를 세서 닫아줌
        open_braces = trial.count("{") - trial.count("}")
        open_brackets = trial.count("[") - trial.count("]")
        closing = "]" * open_brackets + "}" * open_braces
        try:
            result = json.loads(trial + closing)
            if isinstance(result, dict):
                last_complete = m.end()
        except json.JSONDecodeError:
            continue

    if last_complete == -1:
        return None

    trial = text[:last_complete].rstrip().rstrip(",")
    open_braces = trial.count("{") - trial.count("}")
    open_brackets = trial.count("[") - trial.count("]")
    closing = "]" * open_brackets + "}" * open_braces
    try:
        return json.loads(trial + closing)
    except json.JSONDecodeError:
        return None


def extract_career_info(client: OpenAI, images_b64: list[str]) -> dict[str, Any]:
    """GPT-4o Vision으로 경력확인서 이미지에서 정보를 추출.

    Args:
        client: OpenAI 클라이언트 인스턴스.
        images_b64: 페이지별 base64 PNG 이미지 목록.

    Returns:
        추출된 경력 정보 딕셔너리. 키 구조는 _EXTRACTION_PROMPT 참조.

    Raises:
        openai.OpenAIError: API 호출 실패 시.
        ValueError: 응답 파싱 실패 시.
    """
    # 텍스트 프롬프트 + 모든 페이지 이미지를 하나의 메시지로 구성
    content: list[dict] = [{"type": "text", "text": _EXTRACTION_PROMPT}]

    for idx, b64 in enumerate(images_b64):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })
        logger.debug(f"  이미지 {idx + 1}/{len(images_b64)} 추가됨")

    logger.info(f"🤖 GPT-4o Vision으로 {len(images_b64)}페이지 분석 요청 중...")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=16384,
        temperature=0,
    )

    choice = response.choices[0]
    raw_text = choice.message.content.strip()

    if choice.finish_reason == "length":
        logger.warning(
            "⚠️ GPT 응답이 토큰 한도(16384)로 잘렸습니다. "
            "경력 항목이 누락될 수 있습니다."
        )

    logger.info("✅ GPT-4o OCR 분석 완료")
    logger.debug(f"응답 원문:\n{raw_text[:500]}")

    return _parse_json_from_response(raw_text)


def process_pdf(client: OpenAI, pdf_bytes: bytes) -> dict[str, Any]:
    """PDF 바이트 데이터에서 경력 정보를 추출하는 메인 함수.

    Args:
        client: OpenAI 클라이언트 인스턴스.
        pdf_bytes: 업로드된 PDF 파일 바이트 데이터.

    Returns:
        추출된 경력 정보 딕셔너리.
    """
    logger.info("📄 PDF → 이미지 변환 시작")
    images_b64 = _pdf_to_base64_images(pdf_bytes)
    return extract_career_info(client, images_b64)
