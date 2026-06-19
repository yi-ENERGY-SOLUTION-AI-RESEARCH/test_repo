# -*- coding: utf-8 -*-
"""종합 경력확인서 자동 변환 Streamlit 애플리케이션.

전력기술인 경력확인서 PDF를 업로드하면 GPT-4o Vision OCR을 통해
종합 경력확인서 엑셀 양식을 자동으로 작성하여 다운로드할 수 있다.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import dotenv_values
from loguru import logger
from openai import OpenAI

from excel_filler import fill_excel_template
from pdf_processor import process_pdf

# cwd가 younginhr라 루트 .env가 안 잡히고, Windows에 빈 OPENAI_API_KEY가 있으면 load_dotenv가 파일을 무시하는 경우가 있음
_APP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _APP_DIR.parent
for _env_path in (_APP_DIR / ".env", _REPO_ROOT / ".env"):
    if not _env_path.is_file():
        continue
    for _k, _v in dotenv_values(_env_path).items():
        if _v is None:
            continue
        _v = str(_v).strip()
        if not _v:
            continue
        os.environ[_k] = _v

# ── 상수 ──────────────────────────────────────────────────────────────────────
TEMPLATE_PATH = Path("sample/종합 경력확인서 양식.xlsx")
OUTPUT_FILENAME = "종합_경력확인서_작성본.xlsx"
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ── 페이지 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="경력확인서 자동 변환기",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 헤더 ──────────────────────────────────────────────────────────────────────
st.title("📋 전력기술인 경력확인서 → 종합 경력확인서 자동 변환")
st.markdown(
    "PDF를 업로드하면 **AI(GPT-4o)**가 OCR로 내용을 인식하여 엑셀 양식을 자동으로 작성합니다."
)
st.divider()

# ── 사전 검사 ─────────────────────────────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY", "")
if not api_key or api_key.startswith("여기에"):
    st.error(
        "❌ **OPENAI_API_KEY**가 설정되어 있지 않습니다.  \n"
        "`.env` 파일을 열어 발급받은 API 키를 입력한 후 앱을 재시작하세요."
    )
    st.caption("아래는 입력 형식 **예시**입니다. 실제 키 값은 표시하지 않습니다.")
    st.code("OPENAI_API_KEY=sk-...", language="bash")
    st.stop()

if not TEMPLATE_PATH.exists():
    st.error(f"❌ 엑셀 템플릿 파일을 찾을 수 없습니다: `{TEMPLATE_PATH}`")
    st.stop()

client = OpenAI(api_key=api_key)
template_bytes = TEMPLATE_PATH.read_bytes()


# ── 사이드바: 옵션 ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    append_mode = st.toggle(
        "기존 데이터 뒤에 추가",
        value=False,
        help="ON: 기존 엑셀 데이터 다음 행에 추가 / OFF: 4행부터 새로 입력",
    )
    show_raw_json = st.toggle(
        "추출된 원시 JSON 표시",
        value=False,
        help="GPT-4o가 추출한 원시 데이터를 확인할 수 있습니다",
    )
    st.divider()
    st.caption("📌 **지원 문서**: 한국전기기술인협회 발행 전력기술인 경력확인서")
    st.caption("📌 **처리 방식**: PDF → 이미지 → GPT-4o Vision OCR → 엑셀 자동 입력")


# ── 1단계: PDF 업로드 ─────────────────────────────────────────────────────────
st.header("① PDF 파일 업로드")

uploaded_files = st.file_uploader(
    "전력기술인 경력확인서 PDF를 업로드하세요 (여러 명 동시 처리 가능)",
    type=["pdf"],
    accept_multiple_files=True,
    help="한국전기기술인협회에서 발행한 경력확인서 PDF",
)

if not uploaded_files:
    st.info("📂 PDF 파일을 업로드하면 분석이 시작됩니다.")
    st.stop()

st.success(f"✅ **{len(uploaded_files)}개** 파일 업로드 완료")

# ── 2단계: AI 분석 ────────────────────────────────────────────────────────────
st.header("② AI 분석 및 데이터 추출")

# 세션 상태로 분석 결과를 유지 (재실행 방지)
if "career_results" not in st.session_state:
    st.session_state.career_results = []
if "last_file_names" not in st.session_state:
    st.session_state.last_file_names = []

current_file_names = [f.name for f in uploaded_files]

# 업로드된 파일이 바뀌면 기존 결과 초기화
if current_file_names != st.session_state.last_file_names:
    st.session_state.career_results = []
    st.session_state.last_file_names = current_file_names

if st.button("🚀 AI 분석 시작", type="primary", use_container_width=True):
    st.session_state.career_results = []
    progress_bar = st.progress(0, text="분석 준비 중...")
    results: list[dict] = []
    errors: list[str] = []

    for i, uploaded_file in enumerate(uploaded_files):
        progress_text = f"[{i + 1}/{len(uploaded_files)}] **{uploaded_file.name}** 분석 중..."
        progress_bar.progress((i) / len(uploaded_files), text=progress_text)

        with st.spinner(f"🤖 AI가 '{uploaded_file.name}' OCR 처리 중..."):
            try:
                logger.info(f"처리 시작: {uploaded_file.name}")
                career_info = process_pdf(client, uploaded_file.read())
                results.append(career_info)

            except Exception as exc:
                error_msg = f"{uploaded_file.name}: {exc}"
                errors.append(error_msg)
                st.error(f"❌ 처리 실패 — {error_msg}")
                logger.error(f"PDF 처리 오류: {exc}")

    progress_bar.progress(1.0, text="✅ 분석 완료!")
    st.session_state.career_results = results

    if errors:
        st.warning(f"⚠️ {len(errors)}개 파일 처리 중 오류가 발생했습니다.")

# ── 추출 결과 표시 ─────────────────────────────────────────────────────────────
if st.session_state.career_results:
    st.subheader("📊 추출 결과 미리보기")

    for idx, career_info in enumerate(st.session_state.career_results):
        name = career_info.get("성명", f"항목 {idx + 1}")
        records = career_info.get("경력목록", [])

        with st.expander(
            f"👤 {name} — 경력 {len(records)}건 / 실근무 {career_info.get('실근무기간_일수', '-')}일",
            expanded=(idx == 0),
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**기본 정보**")
                st.write(f"- 성명: {career_info.get('성명', '-')}")
                st.write(f"- 생년월일: {career_info.get('생년월일', '-')}")
                st.write(f"- 등급: {career_info.get('등급', '-')}")
                st.write(f"- 기술자격: {career_info.get('기술자격', '-')}")

            with col2:
                st.markdown("**학력 및 근무처**")
                st.write(f"- 학력: {career_info.get('학력', '-')}")
                st.write(f"- 근무처(기간): {career_info.get('근무처명_근무기간', '-')}")

            with col3:
                st.markdown("**경력 요약**")
                st.write(f"- 경력 건수: {len(records)}건")
                st.write(f"- 실근무기간: {career_info.get('실근무기간_일수', '-')}일")

            if records:
                st.markdown("**경력 목록**")
                df = pd.DataFrame(records)
                # 컬럼 순서 정렬
                ordered_cols = [
                    "착수일", "준공일", "참여일수",
                    "참여사업명", "발주자",
                    "직무분야", "담당분야", "비고",
                ]
                display_cols = [c for c in ordered_cols if c in df.columns]
                st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

            if show_raw_json:
                st.markdown("**원시 JSON**")
                st.json(career_info)

    # ── 3단계: 엑셀 생성 및 다운로드 ─────────────────────────────────────────
    st.divider()
    st.header("③ 엑셀 파일 생성 및 다운로드")

    col_gen, col_info = st.columns([2, 3])

    with col_gen:
        if st.button("📊 엑셀 양식 생성", type="primary", use_container_width=True):
            with st.spinner("엑셀 양식 작성 중..."):
                try:
                    filled_bytes = fill_excel_template(
                        template_bytes,
                        st.session_state.career_results,
                        append_mode=append_mode,
                    )
                    st.session_state.filled_excel = filled_bytes
                    st.success(
                        f"✅ **{len(st.session_state.career_results)}명**의 데이터가 입력되었습니다!"
                    )
                except Exception as exc:
                    st.error(f"❌ 엑셀 생성 실패: {exc}")
                    logger.error(f"엑셀 생성 오류: {exc}")

    with col_info:
        st.info(
            f"**입력 모드**: {'기존 데이터 뒤에 추가' if append_mode else '4행부터 새로 입력'}  \n"
            "설정을 변경하려면 왼쪽 사이드바를 확인하세요."
        )

    # 다운로드 버튼
    if "filled_excel" in st.session_state and st.session_state.filled_excel:
        st.download_button(
            label="📥 종합 경력확인서 다운로드 (.xlsx)",
            data=st.session_state.filled_excel,
            file_name=OUTPUT_FILENAME,
            mime=EXCEL_MIME,
            type="primary",
            use_container_width=True,
        )
