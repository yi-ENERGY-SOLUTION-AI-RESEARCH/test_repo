# -*- coding: utf-8 -*-
"""영인에너지솔루션 AI 인력 매칭 에이전트.

RFP 참여인력 평가기준 파일(.md/.docx)을 업로드하면
CV 데이터와 회사 실적을 분석하여 최적의 인력을 추천한다.
"""

import io
import os

import streamlit as st
from docx import Document
from openai import AuthenticationError

from data_loader import build_context_text, load_cv_data, load_siljeok_data
from matcher import APIKeyMissingError, ask_followup, run_matching_pipeline

# ── 페이지 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="영인에너지솔루션 AI 인력 매칭",
    page_icon="⚡",
    layout="wide",
)

# ── 데이터 캐싱 ────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def get_cv_data() -> list[dict]:
    """CV 데이터를 캐싱하여 반환."""
    return load_cv_data()


@st.cache_data(show_spinner=False)
def get_siljeok_data() -> dict[str, list[dict]]:
    """실적 데이터를 캐싱하여 반환."""
    return load_siljeok_data()


# ── 유틸 함수 ──────────────────────────────────────────────────────────────────

def read_uploaded_file(uploaded_file) -> str:
    """업로드된 .md 또는 .docx 파일에서 텍스트를 추출.

    Args:
        uploaded_file: Streamlit의 UploadedFile 객체.

    Returns:
        파일에서 추출한 텍스트 문자열.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".md"):
        return uploaded_file.read().decode("utf-8")
    elif name.endswith(".docx"):
        doc = Document(io.BytesIO(uploaded_file.read()))
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    else:
        return uploaded_file.read().decode("utf-8", errors="ignore")


def render_score_table(items: list[dict]) -> None:
    """항목별 점수를 HTML 테이블로 렌더링.

    Args:
        items: 항목별점수 리스트 ({"항목명", "배점", "획득점수", "근거"}).
    """
    if not items:
        return

    rows_html = ""
    for item in items:
        earned = item.get("획득점수", 0)
        full = item.get("배점", 0)
        pct = round(earned / full * 100) if full else 0

        if pct >= 90:
            bar_color = "#4caf50"
        elif pct >= 60:
            bar_color = "#ff9800"
        else:
            bar_color = "#f44336"

        progress_html = (
            f"<div style='display:flex;align-items:center;gap:6px;'>"
            f"<div style='flex:1;background:#e0e0e0;border-radius:4px;height:10px;min-width:80px;'>"
            f"<div style='width:{pct}%;background:{bar_color};height:10px;border-radius:4px;'></div>"
            f"</div>"
            f"<span style='font-size:0.8rem;color:#555;white-space:nowrap;'>{pct}%</span>"
            f"</div>"
        )

        rows_html += (
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;'>{item.get('항목명', '')}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:center;color:#666;'>{full}점</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:center;font-weight:700;color:#1a1a1a;'>{earned}점</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;min-width:160px;'>{progress_html}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:0.85rem;color:#555;'>{item.get('근거', '')}</td>"
            f"</tr>"
        )

    html = f"""
    <table style='width:100%;border-collapse:collapse;font-size:0.9rem;'>
      <thead>
        <tr style='background:#f7f7f7;'>
          <th style='padding:10px 12px;text-align:left;font-weight:600;color:#444;border-bottom:2px solid #e0e0e0;'>항목</th>
          <th style='padding:10px 12px;text-align:center;font-weight:600;color:#444;border-bottom:2px solid #e0e0e0;'>배점</th>
          <th style='padding:10px 12px;text-align:center;font-weight:600;color:#444;border-bottom:2px solid #e0e0e0;'>획득</th>
          <th style='padding:10px 12px;text-align:left;font-weight:600;color:#444;border-bottom:2px solid #e0e0e0;'>달성률</th>
          <th style='padding:10px 12px;text-align:left;font-weight:600;color:#444;border-bottom:2px solid #e0e0e0;'>근거</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """
    st.html(html)


def render_person_card(person: dict, rank: int) -> None:
    """인력 1명의 매칭 결과 카드를 렌더링.

    Args:
        person: 매칭결과 리스트의 단일 인력 딕셔너리.
        rank: 추천 순위 (1부터 시작).
    """
    총점 = person.get("총점", 0)
    최대 = person.get("최대_가능점수", 15)
    달성 = round(총점 / 최대 * 100) if 최대 else 0

    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")

    with st.container(border=True):
        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.subheader(f"{medal} {person.get('성명', '?')} ({person.get('등급', '')})")
            st.caption(f"추천 포지션: **{person.get('추천_포지션', '')}**")
        with col_right:
            st.markdown(
                f"<div style='text-align:right;'>"
                f"<span style='font-size:0.75rem;color:#888;'>총점</span><br>"
                f"<span style='font-size:1.1rem;font-weight:700;'>{총점}점 / {최대}점</span><br>"
                f"<span style='font-size:0.8rem;color:#4caf50;'>달성률 {달성}%</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        건수 = person.get("유사실적_건수", 0) or 0
        인정 = person.get("유사실적_인정건수", 0) or 0
        인정_pct = round(인정 / 건수 * 100) if 건수 else 0

        st.markdown(
            f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0;">

  <div style="border-radius:10px;padding:16px 18px;background:#f8faff;border:1px solid #dbeafe;">
    <p style="margin:0 0 10px 0;font-size:0.72rem;font-weight:700;color:#93c5fd;letter-spacing:0.08em;text-transform:uppercase;">📅 경력년수</p>
    <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
      <span style="font-size:0.85rem;color:#94a3b8;">실제 경력</span>
      <span style="font-size:0.85rem;font-weight:600;color:#334155;">{person.get("경력년수_원본", "-")}년</span>
    </div>
    <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
      <span style="font-size:0.85rem;color:#94a3b8;">등급 보정 후</span>
      <span style="font-size:0.85rem;font-weight:600;color:#334155;">{person.get("경력년수_가중적용", "-")}년</span>
    </div>
    <div style="margin-bottom:10px;padding:4px 8px;background:#eef2ff;border-radius:4px;">
      <span style="font-size:0.7rem;color:#818cf8;">실제 경력 × 등급 가중치 (기술사 1.0 · 특급 0.9 · 고급 0.8 · 중급 0.7 · 초급 0.6)</span>
    </div>
    <div style="background:#dbeafe;border-radius:6px;padding:8px 12px;display:flex;justify-content:space-between;align-items:center;">
      <span style="font-size:0.8rem;font-weight:600;color:#3b82f6;">최종 인정</span>
      <span style="font-size:1.1rem;font-weight:800;color:#3b82f6;">{person.get("경력년수_인정", "-")}년</span>
    </div>
  </div>

  <div style="border-radius:10px;padding:16px 18px;background:#fffaf5;border:1px solid #fed7aa;">
    <p style="margin:0 0 10px 0;font-size:0.72rem;font-weight:700;color:#fdba74;letter-spacing:0.08em;text-transform:uppercase;">📋 유사실적</p>
    <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
      <span style="font-size:0.85rem;color:#94a3b8;">해당건수</span>
      <span style="font-size:0.85rem;font-weight:600;color:#334155;">{건수}건</span>
    </div>
    <div style="background:#fed7aa;border-radius:6px;padding:8px 12px;display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="font-size:0.8rem;font-weight:600;color:#ea580c;">인정건수</span>
      <span style="font-size:1.1rem;font-weight:800;color:#ea580c;">{인정}건</span>
    </div>
    <div style="background:#e5e7eb;border-radius:99px;height:5px;">
      <div style="width:{인정_pct}%;background:#f97316;height:5px;border-radius:99px;"></div>
    </div>
    <p style="margin:4px 0 0 0;font-size:0.72rem;color:#a3a3a3;text-align:right;">{인정_pct}% 인정</p>
  </div>

  <div style="border-radius:10px;padding:16px 18px;background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:1px solid #bbf7d0;position:relative;overflow:hidden;">
    <div style="position:absolute;top:-8px;left:10px;font-size:3.5rem;color:#86efac;line-height:1;font-family:Georgia,serif;opacity:0.5;">"</div>
    <p style="margin:0 0 8px 0;font-size:0.72rem;font-weight:700;color:#16a34a;letter-spacing:0.08em;text-transform:uppercase;">💡 추천 이유</p>
    <p style="margin:0;font-size:0.9rem;color:#166534;line-height:1.75;font-style:italic;padding-left:4px;">{person.get("추천_이유", "-")}</p>
    <div style="position:absolute;bottom:-12px;right:10px;font-size:3.5rem;color:#86efac;line-height:1;font-family:Georgia,serif;opacity:0.5;">"</div>
  </div>

</div>
""",
            unsafe_allow_html=True,
        )

        # 항목별 점수표
        items = person.get("항목별점수", [])
        if items:
            with st.expander("📊 항목별 점수 상세", expanded=(rank == 1)):
                render_score_table(items)

        # 유사실적 목록
        proj_list = person.get("유사실적_목록", [])
        if proj_list:
            with st.expander(f"📋 유사실적 목록 ({len(proj_list)}건)"):
                for i, proj in enumerate(proj_list, 1):
                    st.write(f"{i}. {proj}")

        # 주의사항
        주의 = person.get("주의사항", "")
        if 주의:
            st.warning(f"⚠️ {주의}")


# ── 사이드바 ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚡ 영인에너지솔루션")
    st.subheader("AI 인력 매칭 에이전트")
    st.divider()

    with st.spinner("데이터 로딩 중..."):
        cv_list = get_cv_data()
        siljeok = get_siljeok_data()
        context_text = build_context_text(cv_list, siljeok)

    st.success("✅ 데이터 로드 완료")

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("인력", f"{len(cv_list)}명")
    with col_b:
        total_proj = sum(len(v) for v in siljeok.values())
        st.metric("회사 실적", f"{total_proj}건")

    st.divider()
    st.caption("🔑 OpenAI API 키")
    api_key_input = st.text_input(
        "API 키 입력",
        type="password",
        placeholder="sk-...",
        help=".env 파일이 없어도 이 브라우저 세션에서만 사용됩니다.",
    )
    if api_key_input:
        os.environ["OPENAI_API_KEY"] = api_key_input.strip()
        st.success("API 키가 현재 세션에 적용되었습니다.")
    elif not os.getenv("OPENAI_API_KEY"):
        st.warning("분석을 시작하려면 OpenAI API 키를 입력하세요.")

    st.divider()
    st.caption("📂 인력 목록")
    for p in cv_list:
        st.write(f"• {p['성명']} ({p['등급']}, {p['경력년수']}년)")

    st.divider()
    st.caption("💡 사용 방법")
    st.write("1. RFP 파일(.md/.docx) 업로드")
    st.write("2. '매칭 분석 시작' 버튼 클릭")
    st.write("3. 결과 확인 후 추가 질문 가능")


# ── 메인 화면 ─────────────────────────────────────────────────────────────────

st.title("⚡ RFP 참여인력 매칭 분석")
st.write("RFP 참여인력 평가기준 파일을 업로드하면 최적 인력 조합을 자동으로 분석합니다.")

# 세션 상태 초기화
if "criteria" not in st.session_state:
    st.session_state.criteria = {}
if "match_result" not in st.session_state:
    st.session_state.match_result = {}
if "rfp_text" not in st.session_state:
    st.session_state.rfp_text = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

# ── 파일 업로드 & 분석 시작 ────────────────────────────────────────────────────
st.subheader("1️⃣ RFP 파일 업로드")

uploaded = st.file_uploader(
    "RFP 참여인력 평가기준 파일을 업로드하세요",
    type=["md", "docx"],
    help="마크다운(.md) 또는 워드(.docx) 파일을 지원합니다",
)

if uploaded:
    rfp_text = read_uploaded_file(uploaded)
    st.session_state.rfp_text = rfp_text

    with st.expander("📄 파일 내용 미리보기", expanded=False):
        st.text(rfp_text[:2000] + ("..." if len(rfp_text) > 2000 else ""))

    st.info(f"📁 파일명: `{uploaded.name}` | 텍스트 길이: {len(rfp_text)}자")

    if st.button("🚀 매칭 분석 시작", type="primary", use_container_width=True):
        try:
            with st.spinner("🔍 1단계: RFP 평가기준 파싱 중..."):
                criteria, match_result = run_matching_pipeline(rfp_text, context_text)
        except APIKeyMissingError:
            st.error("OpenAI API 키가 설정되지 않았습니다.")
            st.info("`younginmatch/.env` 파일에 아래 형식으로 API 키를 저장한 뒤 앱을 다시 실행하세요.")
            st.code("OPENAI_API_KEY=sk-...", language="dotenv")
            st.stop()
        except AuthenticationError:
            st.error("OpenAI API 키가 없거나 유효하지 않습니다. `OPENAI_API_KEY` 값을 확인하세요.")
            st.stop()

        st.session_state.criteria = criteria
        st.session_state.match_result = match_result
        st.session_state.analysis_done = True
        st.session_state.chat_history = []
        st.rerun()

# ── 분석 결과 표시 ─────────────────────────────────────────────────────────────
if st.session_state.analysis_done and st.session_state.match_result:
    criteria = st.session_state.criteria
    match_result = st.session_state.match_result

    st.divider()
    st.subheader("2️⃣ 분석 결과")

    # 유사사업 정의 표시
    if criteria.get("유사사업_정의"):
        st.info(f"🎯 **유사사업 정의**: {criteria['유사사업_정의']}")

    # 평가기준 요약
    with st.expander("📋 파싱된 평가기준 요약"):
        eval_items = criteria.get("평가항목", [])
        if eval_items:
            for item in eval_items:
                구간_text = " / ".join(
                    f"{g['조건']}:{g['점수']}점"
                    for g in item.get("구간", [])[:5]
                )
                st.write(f"• **{item['항목명']}** (배점 {item.get('배점', '?')}점): {구간_text}")
        else:
            st.warning("평가항목을 파싱하지 못했습니다.")

    # 추천 순위 배너
    순위 = match_result.get("추천_순위", [])
    if 순위:
        st.success(f"🏆 추천 순위: {' > '.join(순위)}")

    # 종합 의견
    종합 = match_result.get("종합_의견", "")
    if 종합:
        with st.expander("💬 종합 의견"):
            st.write(종합)

    # 포지션별 최적 인력 추천
    st.subheader("3️⃣ 포지션별 추천 인력")

    매칭결과 = match_result.get("매칭결과", [])

    # CV 원본 데이터에서 성명 → 참여분야/참여업무명 매핑 생성 (필터 fallback 용도)
    cv_by_name: dict[str, dict] = {p["성명"]: p for p in cv_list}

    def has_discipline(person: dict, keywords: list[str]) -> bool:
        """LLM의 추천_포지션 + CV의 참여분야/참여업무명을 종합해 해당 분야 적합 여부 판단."""
        name = person.get("성명", "")
        haystacks: list[str] = [person.get("추천_포지션", "")]

        cv = cv_by_name.get(name, {})
        if cv:
            haystacks.append(" ".join(cv.get("참여분야", []) or []))
            haystacks.append(cv.get("해당분야", "") or "")
            haystacks.append(" ".join(cv.get("참여업무명", []) or []))

        # 송전 키워드는 T/L, 송전선로 등 영문/약어 패턴도 광범위하게 포함
        expanded: list[str] = []
        for kw in keywords:
            expanded.append(kw)
            if kw == "송전":
                expanded.extend(["T/L", "송전선", "송전선로", "송전탑", "가공송전"])
            elif kw == "변전":
                expanded.extend(["S/S", "변전소", "GIS", "M.Tr", "M/Tr", "Switchgear", "SWGR"])
            elif kw == "토목":
                expanded.extend(["구조", "건축", "측량", "토건"])

        text = " ".join(haystacks).lower()
        return any(kw.lower() in text for kw in expanded)

    TARGET_POSITIONS: list[tuple[str, list[str]]] = [
        ("PM",        ["PM", "프로젝트매니저", "project manager"]),
        ("전기(송전)", ["송전"]),
        ("전기(변전)", ["변전"]),
        ("토목",       ["토목"]),
    ]

    # 포지션별 상위 3명 선정 규칙:
    # - PM: 총점 기준
    # - 송전/변전/토목: 인정 경력년수 기준
    # - PM에 배정된 인력은 송전/변전/토목 탭에서도 제외하면 송전 슬롯이 비어버릴 수 있어
    #   PM과 다른 분야는 중복 노출을 허용하고, 송전/변전/토목 사이에서만 중복을 방지한다.
    field_assigned: set[str] = set()
    position_picks: list[tuple[str, list[dict]]] = []

    for label, keywords in TARGET_POSITIONS:
        is_pm = label == "PM"
        sort_key = (lambda p: p.get("총점", 0)) if is_pm else (lambda p: p.get("경력년수_인정", 0))

        if is_pm:
            pool = [p for p in 매칭결과 if has_discipline(p, keywords)]
        else:
            pool = [
                p for p in 매칭결과
                if has_discipline(p, keywords)
                and p.get("성명", "") not in field_assigned
            ]

        candidates = sorted(pool, key=sort_key, reverse=True)

        picks = candidates[:3]
        if not is_pm:
            field_assigned.update(p.get("성명", "") for p in picks if p.get("성명"))
        position_picks.append((label, picks))

    tab_labels = [f"{label} ({len(picks)}명)" for label, picks in position_picks]
    tabs = st.tabs(tab_labels)

    for tab, (label, people) in zip(tabs, position_picks):
        with tab:
            if people:
                for rank, person in enumerate(people, 1):
                    render_person_card(person, rank)
            else:
                st.info(f"'{label}' 포지션에 배정 가능한 인력이 없습니다.")

    # ── 추가 질문 채팅 ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("4️⃣ 추가 질문")
    st.caption("분석 결과에 대해 추가로 궁금한 점을 질문하세요.")

    # 이전 대화 이력 표시
    for msg in st.session_state.chat_history:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.write(msg["content"])

    # 새 질문 입력
    if question := st.chat_input("예: 전기(변전) 분야 가장 적합한 인력은? / 실적 부족한 인력은 누구?"):
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                try:
                    answer = ask_followup(
                        question=question,
                        criteria=st.session_state.criteria,
                        match_result=st.session_state.match_result,
                        context_text=context_text,
                        chat_history=st.session_state.chat_history[:-1],
                    )
                except APIKeyMissingError:
                    answer = "OpenAI API 키가 설정되지 않았습니다. `younginmatch/.env` 파일의 `OPENAI_API_KEY`를 확인해주세요."
                except AuthenticationError:
                    answer = "OpenAI API 키가 없거나 유효하지 않습니다. `OPENAI_API_KEY` 값을 확인해주세요."
            st.write(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})

elif not uploaded:
    st.info("👆 위에서 RFP 파일을 업로드해주세요.")
