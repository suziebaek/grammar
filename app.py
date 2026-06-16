import streamlit as st
import json
import random
from pathlib import Path
import google.generativeai as genai

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="영어 기출 문제 생성기",
    page_icon="📝",
    layout="wide",
)

# ── 데이터 로드 ───────────────────────────────────────────
BASE = Path(__file__).parent

@st.cache_data
def load_questions():
    with open(BASE / "questions_db.json", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_concepts():
    with open(BASE / "concept_hierarchy.json", encoding="utf-8") as f:
        return json.load(f)

QUESTIONS = load_questions()
CONCEPTS  = load_concepts()

# 문제 유형 목록
PRIMARY_TYPES = [
    "어법상 맞는 것", "어법상 옳은 것", "어법상 옳지 않은 것",
    "빈칸 채우기", "개수 고르기", "올바른 영작",
    "어법상 어색한 것", "어법상 바른 것", "바르게 짝지어진 것",
]
ALL_TYPES = sorted(set(q["t"] for q in QUESTIONS if q["t"]))
SORTED_TYPES = [t for t in PRIMARY_TYPES if t in ALL_TYPES] + \
               [t for t in ALL_TYPES if t not in PRIMARY_TYPES]

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
  .main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
    color: white; padding: 1.8rem 2.5rem; border-radius: 12px; margin-bottom: 1.5rem;
  }
  .main-header h1 { margin: 0; font-size: 1.8rem; }
  .main-header p  { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.95rem; }
  .section-card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 1.2rem 1.5rem; margin-bottom: 0.8rem;
  }
  .question-box {
    background: white; border-left: 4px solid #2d6a9f;
    border-radius: 8px; padding: 1.4rem; margin: 0.8rem 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }
  .answer-box {
    background: #f0fdf4; border: 1px solid #86efac;
    border-radius: 8px; padding: 0.8rem 1.2rem; margin-top: 0.6rem;
  }
  .explanation-box {
    background: #fffbeb; border: 1px solid #fcd34d;
    border-radius: 8px; padding: 0.8rem 1.2rem; margin-top: 0.4rem;
  }
  .stat-box {
    background: white; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 0.8rem; text-align: center;
  }
  .stat-box .num   { font-size: 1.8rem; font-weight: 700; color: #2d6a9f; }
  .stat-box .label { font-size: 0.8rem; color: #64748b; }
  .diff-badge {
    display: inline-block; border-radius: 20px;
    padding: 0.15rem 0.7rem; font-size: 0.8rem; font-weight: 600; margin-left: 0.4rem;
  }
  .diff-하   { background:#dbeafe; color:#1e40af; }
  .diff-중   { background:#dcfce7; color:#166534; }
  .diff-중상 { background:#fef9c3; color:#854d0e; }
  .diff-상   { background:#fee2e2; color:#991b1b; }
  .batch-card {
    background: #f0f9ff; border: 1px solid #bae6fd;
    border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 0.6rem;
  }
  .stButton > button {
    background: linear-gradient(135deg, #1e3a5f, #2d6a9f);
    color: white; border: none; border-radius: 8px;
    padding: 0.55rem 1.5rem; font-size: 0.95rem; font-weight: 600;
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

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    api_key = st.text_input("Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")
    st.markdown("### 📊 DB 현황")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="stat-box"><div class="num">{len(QUESTIONS)}</div><div class="label">기출 문제</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-box"><div class="num">{len(CONCEPTS)}</div><div class="label">대분류</div></div>', unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**📚 문법 대분류**")
    for major in CONCEPTS:
        total = sum(len(v) for v in CONCEPTS[major].values())
        st.markdown(f"- {major} ({total}개 소개념)")
    st.markdown("---")
    st.markdown("**🔄 DB 업데이트 방법**")
    st.info(
        "1. 엑셀 파일 수정 후 저장\n"
        "2. 터미널에서 실행:\n"
        "```\npython update_db.py\n```\n"
        "3. 앱 재시작 (우측 상단 ⋮ → Rerun)"
    )

# ── 세션 초기화 ───────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # [{unit, mid, minor, diff, types, count, results:[{type, text}]}]
if "pending" not in st.session_state:
    st.session_state.pending = []   # 현재 배치에 추가 중인 항목들

# ── 탭 ───────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🤖 AI 문제 생성", "📚 기출 문제 탐색", "📋 생성 기록"])


# ════════════════════════════════════════════════════════
# TAB 1 : AI 문제 생성
# ════════════════════════════════════════════════════════
with tab1:

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── 왼쪽: 개념 선택 ────────────────────────────────────
    with col_left:
        st.markdown("### 📖 문법 개념 선택")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        # 대분류
        major_list = list(CONCEPTS.keys())
        selected_major = st.selectbox("① 대분류", major_list, key="major")

        # 중분류
        mid_list = list(CONCEPTS[selected_major].keys())
        selected_mid = st.selectbox("② 중분류", mid_list, key="mid")

        # 소분류
        minor_items = CONCEPTS[selected_major][selected_mid]
        minor_labels = [item["minor"] for item in minor_items if item["minor"]]
        if minor_labels:
            selected_minor_label = st.selectbox("③ 소분류", minor_labels, key="minor")
            # 난이도 자동 표시
            selected_item = next((x for x in minor_items if x["minor"] == selected_minor_label), None)
            if selected_item:
                diff = selected_item["difficulty"]
                diff_class = f"diff-{diff}" if diff else ""
                st.markdown(
                    f'④ 난이도: <span class="diff-badge {diff_class}">{diff if diff else "미분류"}</span>',
                    unsafe_allow_html=True
                )
                if selected_item.get("point"):
                    with st.expander("💡 출제 포인트 보기"):
                        st.markdown(selected_item["point"])
        else:
            selected_minor_label = ""
            selected_item = None
            diff = ""

        st.markdown('</div>', unsafe_allow_html=True)

        # ── 추가 요청사항 ──────────────────────────────────
        st.markdown("### ✏️ 추가 요청사항")
        extra = st.text_area(
            "추가 요청",
            placeholder="예) 난이도 상으로 함정 선지 포함\n예) 스포츠 주제로, 강남구 기출 스타일",
            height=100,
            label_visibility="collapsed",
        )

    # ── 오른쪽: 문제 유형 & 개수 ───────────────────────────
    with col_right:
        st.markdown("### 📋 문제 유형 & 개수")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        st.markdown("**문제 유형 선택 (복수 가능)**")
        selected_types = st.multiselect(
            "유형",
            SORTED_TYPES,
            default=["어법상 맞는 것"],
            label_visibility="collapsed",
        )

        st.markdown("**유형별 생성 개수**")
        num_per_type = st.slider("개수", 1, 10, 5)

        st.markdown('</div>', unsafe_allow_html=True)

        # 기출 참고 현황
        ref_pool = [q for q in QUESTIONS if selected_major in q["u"] or selected_mid in q.get("s","")]
        if not ref_pool:
            ref_pool = QUESTIONS
        st.info(f"📎 참고 기출: {len(ref_pool)}문제 ('{selected_major}' 관련)")

        # 생성할 문제 요약
        if selected_types:
            st.markdown("**생성 예정**")
            for t in selected_types:
                st.markdown(f"- {t} × {num_per_type}문제")
            st.markdown(f"**→ 총 {len(selected_types) * num_per_type}문제**")

    # ── 생성 버튼 ─────────────────────────────────────────
    st.markdown("---")
    gen_col1, gen_col2 = st.columns([3, 1])
    with gen_col1:
        generate_btn = st.button("🚀 문제 생성하기", use_container_width=True)
    with gen_col2:
        clear_btn = st.button("🗑️ 결과 초기화", use_container_width=True)

    if clear_btn:
        st.session_state.pending = []
        st.rerun()

    # ── 생성 실행 ─────────────────────────────────────────
    if generate_btn:
        if not api_key:
            st.error("사이드바에 Gemini API Key를 입력해주세요.")
        elif not selected_types:
            st.error("문제 유형을 하나 이상 선택해주세요.")
        else:
            ref_samples = random.sample(ref_pool, min(5, len(ref_pool)))
            ref_text = "\n\n".join([
                f"[기출 {i+1}]\n문제유형: {q['t']}\n발문: {q['q']}\n보기/지문: {q['c']}\n정답: {q['a']}\n해설: {q['e']}"
                for i, q in enumerate(ref_samples)
            ])

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

            batch_results = []
            progress = st.progress(0, text="생성 중...")
            total = len(selected_types)

            for idx, qtype in enumerate(selected_types):
                progress.progress((idx) / total, text=f"[{idx+1}/{total}] '{qtype}' 유형 생성 중...")

                concept_info = ""
                if selected_item:
                    concept_info = f"\n출제 포인트: {selected_item.get('point','')[:400]}"

                prompt = f"""당신은 강남구 중학교 영어 시험 문제 전문 출제자입니다.
아래 기출 문제들의 스타일, 발문 형식, 선지 구성 방식을 정확히 분석하여 응용 문제를 출제하세요.

=== 참고 기출 문제 ===
{ref_text}

=== 출제 조건 ===
- 문법 대분류: {selected_major}
- 문법 중분류: {selected_mid}
- 문법 소분류: {selected_minor_label}
- 난이도: {diff if diff else '미지정'}{concept_info}
- 문제 유형: {qtype}
- 생성 개수: {num_per_type}개
- 추가 요청: {extra if extra else '없음'}

=== 출제 규칙 ===
1. 기출 문제와 동일한 발문 스타일 사용 (예: "밑줄 친 부분이 어법상 맞는 것은?")
2. 선지는 ①②③④⑤ 형식으로 5개 구성
3. 각 문제마다 반드시 [정답]과 [해설] 포함
4. 해설은 오답 이유도 함께 설명 (기출 해설 스타일 참고)
5. 영어 문장은 자연스럽고 실제 시험에 나올 법한 수준으로
6. 소분류 개념에 정확히 집중하여 출제할 것

=== 출력 형식 (반드시 준수) ===
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
                try:
                    response = model.generate_content(prompt)
                    batch_results.append({"type": qtype, "text": response.text})
                except Exception as e:
                    batch_results.append({"type": qtype, "text": f"[오류] {e}"})

            progress.progress(1.0, text="✅ 생성 완료!")

            # 세션에 저장
            entry = {
                "major": selected_major,
                "mid": selected_mid,
                "minor": selected_minor_label,
                "difficulty": diff,
                "types": selected_types,
                "count": num_per_type,
                "results": batch_results,
            }
            st.session_state.history.append(entry)
            st.session_state.pending = [entry]

    # ── 결과 표시 ─────────────────────────────────────────
    if st.session_state.pending:
        entry = st.session_state.pending[-1]
        st.markdown("---")
        st.markdown(f"### 📄 생성 결과 — {entry['major']} > {entry['mid']} > {entry['minor']}")

        for res in entry["results"]:
            with st.expander(f"📌 [{res['type']}] 유형 문제", expanded=True):
                raw = res["text"]
                problems = raw.split("【문제")
                for prob in problems:
                    prob = prob.strip()
                    if not prob or not prob[0].isdigit():
                        continue
                    full = "【문제" + prob
                    parts = {}
                    tags = ["발문", "보기/지문", "정답", "해설"]
                    for tag in tags:
                        key = f"[{tag}]"
                        if key in full:
                            start = full.index(key) + len(key)
                            nexts = [f"[{t}]" for t in tags if f"[{t}]" in full[start:]]
                            end = full.index(nexts[0], start) if nexts else len(full)
                            parts[tag] = full[start:end].replace("---", "").strip()

                    st.markdown('<div class="question-box">', unsafe_allow_html=True)
                    num_part = prob[:10].split("】")[0]
                    st.markdown(f"**【문제{num_part}】**")
                    if "발문" in parts:
                        st.markdown(f"**{parts['발문']}**")
                    if "보기/지문" in parts:
                        st.markdown(parts["보기/지문"])
                    if "정답" in parts:
                        st.markdown(f'<div class="answer-box">✅ <b>정답:</b> {parts["정답"]}</div>', unsafe_allow_html=True)
                    if "해설" in parts:
                        st.markdown(f'<div class="explanation-box">💡 <b>해설:</b><br>{parts["해설"]}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

        # 통합 다운로드
        combined = f"[생성 정보]\n단원: {entry['major']} > {entry['mid']} > {entry['minor']}\n난이도: {entry['difficulty']}\n\n"
        combined += "\n\n" + "="*60 + "\n\n".join(
            f"【{r['type']} 유형】\n\n{r['text']}" for r in entry["results"]
        )
        st.download_button(
            "⬇️ 생성된 문제 전체 다운로드 (.txt)",
            data=combined.encode("utf-8"),
            file_name=f"{entry['major']}_{entry['minor']}_문제.txt",
            mime="text/plain",
        )


# ════════════════════════════════════════════════════════
# TAB 2 : 기출 문제 탐색
# ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 기출 문제 탐색")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        f_major = st.selectbox("대분류 필터", ["전체"] + list(CONCEPTS.keys()), key="f_major")
    with fc2:
        all_q_types = sorted(set(q["t"] for q in QUESTIONS if q["t"]))
        f_type = st.selectbox("문제유형 필터", ["전체"] + all_q_types, key="f_type")
    with fc3:
        kw = st.text_input("키워드", placeholder="예) 관계대명사, 현재완료")

    filtered = QUESTIONS
    if f_major != "전체":
        filtered = [q for q in filtered if f_major in q["u"]]
    if f_type != "전체":
        filtered = [q for q in filtered if q["t"] == f_type]
    if kw:
        kl = kw.lower()
        filtered = [q for q in filtered if kl in q["q"].lower() or kl in q["s"].lower() or kl in q["c"].lower()]

    st.markdown(f"**검색 결과: {len(filtered)}문제**")
    for q in filtered[:30]:
        with st.expander(f"[{q['u']} > {q['s']}] {q['t']} — {q['q'][:50]}..."):
            st.markdown(f"**발문:** {q['q']}")
            if q["c"]:
                st.markdown("**보기/지문:**")
                st.markdown(q["c"])
            st.markdown(f'<div class="answer-box">✅ <b>정답:</b> {q["a"]}</div>', unsafe_allow_html=True)
            if q["e"]:
                st.markdown(f'<div class="explanation-box">💡 <b>해설:</b> {q["e"]}</div>', unsafe_allow_html=True)
    if len(filtered) > 30:
        st.info("상위 30개만 표시됩니다. 필터를 좁혀 검색하세요.")


# ════════════════════════════════════════════════════════
# TAB 3 : 생성 기록
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 생성 기록")

    if not st.session_state.history:
        st.info("아직 생성된 문제가 없습니다.")
    else:
        # 전체 통합 다운로드
        all_combined = ""
        for i, h in enumerate(st.session_state.history):
            all_combined += f"\n{'='*70}\n"
            all_combined += f"[세트 {i+1}] {h['major']} > {h['mid']} > {h['minor']} | 난이도: {h['difficulty']}\n"
            all_combined += f"{'='*70}\n\n"
            for r in h["results"]:
                all_combined += f"【{r['type']} 유형】\n\n{r['text']}\n\n"

        st.download_button(
            "⬇️ 전체 생성 기록 통합 다운로드 (.txt)",
            data=all_combined.encode("utf-8"),
            file_name="전체_생성문제.txt",
            mime="text/plain",
            use_container_width=True,
        )
        st.markdown("---")

        for i, h in enumerate(reversed(st.session_state.history)):
            idx = len(st.session_state.history) - i
            label = f"세트 {idx} | {h['major']} > {h['minor']} | {', '.join(h['types'])} | 각 {h['count']}문제"
            with st.expander(label):
                for r in h["results"]:
                    st.markdown(f"**▶ {r['type']} 유형**")
                    st.markdown(r["text"])
                    st.markdown("---")

                # 이 세트 개별 다운로드
                set_text = f"[{h['major']} > {h['mid']} > {h['minor']}] 난이도: {h['difficulty']}\n\n"
                set_text += "\n\n".join(f"【{r['type']}】\n\n{r['text']}" for r in h["results"])
                st.download_button(
                    f"⬇️ 세트 {idx} 다운로드",
                    data=set_text.encode("utf-8"),
                    file_name=f"세트{idx}_{h['minor']}.txt",
                    mime="text/plain",
                    key=f"dl_set_{idx}",
                )
