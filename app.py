import streamlit as st
import json
import anthropic
import random
from pathlib import Path

# ── 페이지 설정 ──────────────────────────────────────────
st.set_page_config(
    page_title="영어 기출 문제 생성기",
    page_icon="📝",
    layout="wide",
)

# ── 데이터 로드 ──────────────────────────────────────────
@st.cache_data
def load_questions():
    with open(Path(__file__).parent / "questions_db.json", encoding="utf-8") as f:
        return json.load(f)

QUESTIONS = load_questions()

# 대단원 목록 (기본 단원 우선 정렬)
PRIMARY_UNITS = ["관계사", "수동태", "시제", "to부정사", "비교", "접속사", "동명사", "분사", "조동사", "가정법"]
ALL_UNITS = sorted(set(q["u"] for q in QUESTIONS if q["u"]))
SORTED_UNITS = [u for u in PRIMARY_UNITS if u in ALL_UNITS] + [u for u in ALL_UNITS if u not in PRIMARY_UNITS]

# 문제 유형 목록 (주요 유형 우선)
PRIMARY_TYPES = ["어법상 맞는 것", "어법상 옳은 것", "어법상 옳지 않은 것", "빈칸 채우기", "개수 고르기", "올바른 영작"]
ALL_TYPES = sorted(set(q["t"] for q in QUESTIONS if q["t"]))
SORTED_TYPES = [t for t in PRIMARY_TYPES if t in ALL_TYPES] + [t for t in ALL_TYPES if t not in PRIMARY_TYPES]

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
        color: white;
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
    }
    .main-header h1 { margin: 0; font-size: 2rem; }
    .main-header p  { margin: 0.4rem 0 0; opacity: 0.85; font-size: 1rem; }

    .section-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .question-box {
        background: white;
        border-left: 4px solid #2d6a9f;
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .answer-box {
        background: #f0fdf4;
        border: 1px solid #86efac;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin-top: 0.8rem;
    }
    .explanation-box {
        background: #fffbeb;
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin-top: 0.5rem;
    }
    .ref-badge {
        display: inline-block;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.8rem;
        margin: 0.2rem;
    }
    .stat-box {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .stat-box .num { font-size: 2rem; font-weight: 700; color: #2d6a9f; }
    .stat-box .label { font-size: 0.85rem; color: #64748b; }
    .stButton > button {
        background: linear-gradient(135deg, #1e3a5f, #2d6a9f);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-size: 1rem;
        font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover { opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

# ── 헤더 ─────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>📝 영어 기출 문제 생성기</h1>
    <p>강남구 중학교 기출 154문제 데이터 기반 · AI 응용 문제 자동 생성</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바: API 키 ──────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
    st.markdown("---")
    st.markdown("### 📊 DB 현황")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""<div class="stat-box"><div class="num">{len(QUESTIONS)}</div><div class="label">총 기출 문제</div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="stat-box"><div class="num">{len(ALL_UNITS)}</div><div class="label">문법 단원</div></div>""", unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**📚 포함 단원**")
    for u in PRIMARY_UNITS:
        cnt = sum(1 for q in QUESTIONS if q["u"] == u)
        st.markdown(f"- {u} ({cnt}문제)")

# ── 탭 ───────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🤖 AI 문제 생성", "📚 기출 문제 탐색", "📋 생성 기록"])

# ════════════════════════════════════════════════
# TAB 1: AI 문제 생성
# ════════════════════════════════════════════════
with tab1:
    st.markdown("### 문제 생성 옵션")

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("**① 문법 단원 선택**")
        selected_unit = st.selectbox("대단원", SORTED_UNITS, label_visibility="collapsed")

        # 선택된 단원의 소단원
        sub_units = sorted(set(q["s"] for q in QUESTIONS if q["u"] == selected_unit and q["s"]))
        if sub_units:
            selected_sub = st.selectbox("소단원 (선택)", ["전체"] + sub_units)
        else:
            selected_sub = "전체"

        st.markdown("**② 문제 유형**")
        selected_type = st.selectbox("문제 유형", SORTED_TYPES, label_visibility="collapsed")

        st.markdown("**③ 생성 개수**")
        num_questions = st.slider("문제 수", 1, 5, 3)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("**④ 추가 요청사항 (선택)**")
        extra_instruction = st.text_area(
            "난이도, 특정 어휘, 주제 등 자유롭게 입력",
            placeholder="예) 난이도 상, 스포츠 주제로 만들어주세요\n예) 강남구 기출 스타일로, 함정 선지 포함",
            height=120,
            label_visibility="collapsed",
        )

        st.markdown("**⑤ 참고할 기출 문제**")
        # 선택된 단원의 기출 필터
        ref_pool = [q for q in QUESTIONS if q["u"] == selected_unit]
        if selected_sub != "전체":
            ref_pool = [q for q in ref_pool if q["s"] == selected_sub]

        if ref_pool:
            st.info(f"'{selected_unit}' 관련 기출 {len(ref_pool)}문제를 참고합니다.")
        else:
            st.warning("선택한 단원의 기출이 없어 전체 DB를 참고합니다.")
            ref_pool = QUESTIONS

        st.markdown('</div>', unsafe_allow_html=True)

    # 생성 버튼
    generate_btn = st.button("🚀 문제 생성하기", use_container_width=True)

    if generate_btn:
        if not api_key:
            st.error("왼쪽 사이드바에 Anthropic API Key를 입력해주세요.")
        else:
            # 참고할 기출 샘플 (최대 5개)
            ref_samples = random.sample(ref_pool, min(5, len(ref_pool)))
            ref_text = "\n\n".join([
                f"[기출 {i+1}]\n문제유형: {q['t']}\n발문: {q['q']}\n보기/지문: {q['c']}\n정답: {q['a']}\n해설: {q['e']}"
                for i, q in enumerate(ref_samples)
            ])

            prompt = f"""당신은 강남구 중학교 영어 시험 문제 전문 출제자입니다.
아래 기출 문제들의 스타일, 발문 형식, 선지 구성 방식을 정확히 분석하여 응용 문제를 출제하세요.

=== 참고 기출 문제 ===
{ref_text}

=== 출제 조건 ===
- 문법 단원: {selected_unit}{f' > {selected_sub}' if selected_sub != '전체' else ''}
- 문제 유형: {selected_type}
- 생성 개수: {num_questions}개
- 추가 요청: {extra_instruction if extra_instruction else '없음'}

=== 출제 규칙 ===
1. 기출 문제와 동일한 발문 스타일을 사용하세요 (예: "밑줄 친 부분이 어법상 맞는 것은?")
2. 선지는 ①②③④⑤ 형식으로 5개 구성
3. 각 문제마다 반드시 [정답]과 [해설]을 포함
4. 해설은 오답 이유도 함께 설명 (기출 해설 스타일 참고)
5. 영어 문장은 자연스럽고 실제 시험에 나올 법한 수준으로

=== 출력 형식 ===
각 문제를 아래 형식으로 출력:

【문제 N】
[발문]
발문 내용

[보기/지문]
① ...
② ...
③ ...
④ ...
⑤ ...

[정답] ④

[해설]
해설 내용

---
"""

            with st.spinner("AI가 기출 패턴을 분석하여 문제를 생성 중입니다..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    result = response.content[0].text

                    # 세션에 저장
                    if "history" not in st.session_state:
                        st.session_state.history = []
                    st.session_state.history.append({
                        "unit": selected_unit,
                        "sub": selected_sub,
                        "type": selected_type,
                        "count": num_questions,
                        "result": result,
                    })

                    st.success("✅ 문제 생성 완료!")
                    st.markdown("---")
                    st.markdown("### 📄 생성된 문제")

                    # 파싱하여 문제별 표시
                    problems = result.split("【문제")
                    for i, prob in enumerate(problems):
                        if prob.strip() and prob.strip()[0].isdigit():
                            st.markdown(f'<div class="question-box">', unsafe_allow_html=True)
                            st.markdown(f"**【문제{prob[:50].split('】')[0]}】**")

                            sections = prob.split("[")
                            full_text = "【문제" + prob
                            # 발문/보기/정답/해설 파싱
                            parts = {}
                            for tag in ["발문", "보기/지문", "정답", "해설"]:
                                if f"[{tag}]" in full_text:
                                    start = full_text.index(f"[{tag}]") + len(f"[{tag}]")
                                    next_tags = [f"[{t}]" for t in ["발문", "보기/지문", "정답", "해설"] if f"[{t}]" in full_text[start:]]
                                    if next_tags:
                                        end = full_text.index(next_tags[0], start)
                                        parts[tag] = full_text[start:end].strip()
                                    else:
                                        parts[tag] = full_text[start:].replace("---","").strip()

                            if "발문" in parts:
                                st.markdown(f"**{parts['발문']}**")
                            if "보기/지문" in parts:
                                st.markdown(parts["보기/지문"])
                            if "정답" in parts:
                                st.markdown(f'<div class="answer-box">✅ <b>정답:</b> {parts["정답"]}</div>', unsafe_allow_html=True)
                            if "해설" in parts:
                                st.markdown(f'<div class="explanation-box">💡 <b>해설:</b><br>{parts["해설"]}</div>', unsafe_allow_html=True)

                            st.markdown("</div>", unsafe_allow_html=True)
                            st.markdown("")

                    # 참고 기출 표시
                    with st.expander("📎 참고한 기출 문제 보기"):
                        for i, q in enumerate(ref_samples):
                            st.markdown(f"**기출 {i+1}** | {q['u']} > {q['s']} | {q['t']}")
                            st.markdown(f"- 발문: {q['q']}")
                            st.markdown(f"- 정답: {q['a']}")
                            st.markdown("---")

                    # 다운로드
                    st.download_button(
                        "⬇️ 생성된 문제 다운로드 (.txt)",
                        data=result.encode("utf-8"),
                        file_name=f"generated_{selected_unit}_{selected_type}.txt",
                        mime="text/plain",
                    )

                except Exception as e:
                    st.error(f"오류 발생: {e}")


# ════════════════════════════════════════════════
# TAB 2: 기출 문제 탐색
# ════════════════════════════════════════════════
with tab2:
    st.markdown("### 기출 문제 탐색 및 검색")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_unit = st.selectbox("대단원 필터", ["전체"] + SORTED_UNITS, key="filter_unit")
    with col_f2:
        filter_type = st.selectbox("문제유형 필터", ["전체"] + SORTED_TYPES, key="filter_type")
    with col_f3:
        search_kw = st.text_input("키워드 검색", placeholder="예) 관계대명사, 현재완료...")

    filtered = QUESTIONS
    if filter_unit != "전체":
        filtered = [q for q in filtered if q["u"] == filter_unit]
    if filter_type != "전체":
        filtered = [q for q in filtered if q["t"] == filter_type]
    if search_kw:
        kw = search_kw.lower()
        filtered = [q for q in filtered if kw in q["q"].lower() or kw in q["s"].lower() or kw in q["c"].lower()]

    st.markdown(f"**검색 결과: {len(filtered)}문제**")

    for i, q in enumerate(filtered[:30]):  # 최대 30개 표시
        with st.expander(f"[{q['u']} > {q['s']}] {q['t']} — {q['q'][:50]}..."):
            st.markdown(f"**발문:** {q['q']}")
            if q["c"]:
                st.markdown("**보기/지문:**")
                st.markdown(q["c"])
            st.markdown(f'<div class="answer-box">✅ <b>정답:</b> {q["a"]}</div>', unsafe_allow_html=True)
            if q["e"]:
                st.markdown(f'<div class="explanation-box">💡 <b>해설:</b> {q["e"]}</div>', unsafe_allow_html=True)

    if len(filtered) > 30:
        st.info(f"상위 30개만 표시됩니다. 필터를 좁혀서 검색하세요.")


# ════════════════════════════════════════════════
# TAB 3: 생성 기록
# ════════════════════════════════════════════════
with tab3:
    st.markdown("### 이번 세션 생성 기록")

    if "history" not in st.session_state or not st.session_state.history:
        st.info("아직 생성된 문제가 없습니다. 'AI 문제 생성' 탭에서 문제를 생성해보세요.")
    else:
        for i, h in enumerate(reversed(st.session_state.history)):
            with st.expander(f"생성 #{len(st.session_state.history)-i} | {h['unit']} | {h['type']} | {h['count']}문제"):
                st.markdown(h["result"])
                st.download_button(
                    "⬇️ 다운로드",
                    data=h["result"].encode("utf-8"),
                    file_name=f"questions_{h['unit']}_{i}.txt",
                    mime="text/plain",
                    key=f"dl_{i}",
                )
