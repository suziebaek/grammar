import streamlit as st
import json
import random
from pathlib import Path
import google.generativeai as genai
from openai import OpenAI, AzureOpenAI
import pandas as pd

# ── 🎯 전역 설정: 구글 시트 탭별 GID URL 하드코딩 ────────────────────────
# (선생님의 시트에서 각 탭을 클릭했을 때 나오는 '주소창의 전체 주소'를 각각 넣어주세요)
QUESTIONS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=939067680#gid=939067680"
CONCEPTS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=0#gid=0"

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="영어 기출 문제 생성기",
    page_icon="📝",
    layout="wide",
)

# ── 데이터 로드 함수 ────────────────────────────────────────
BASE = Path(__file__).parent

# [모드 1] 로컬 JSON 로드 (폴백용)
@st.cache_data
def load_json_db():
    try:
        with open(BASE / "questions_db.json", encoding="utf-8") as f:
            q = json.load(f)
        with open(BASE / "concept_hierarchy.json", encoding="utf-8") as f:
            c = json.load(f)
        return q, c
    except:
        return [], {}

# [모드 2] 멀티 탭 구글 시트 다이렉트 로드 (400 에러 원천 차단)
@st.cache_data(ttl=180)
def load_gsheets_dual_db(q_url, c_url):
    try:
        def convert_to_csv_url(url):
            return url.replace("/edit#gid=", "/export?format=csv&gid=").replace("/edit?usp=sharing", "/export?format=csv")

        df_questions = pd.read_csv(convert_to_csv_url(q_url)).fillna('')
        df_concepts = pd.read_csv(convert_to_csv_url(c_url)).fillna('')
        
        # 1. 'questions_db' 탭 파싱 (괄호 뺀 정확한 컬럼명 매칭)
        questions_pool = []
        for _, row in df_questions.iterrows():
            q_type = str(row.get('문제유형', '')).strip()
            if not q_type:
                continue
            questions_pool.append({
                "u": str(row.get('대분류', '')).strip(),
                "s": str(row.get('소분류', '')).strip(),
                "t": q_type,
                "q": str(row.get('발문', '')).strip(),
                "c": str(row.get('보기', '')).strip(),
                "a": str(row.get('정답', '')).strip(),
                "e": str(row.get('해설', '')).strip()
            })

        # 2. 'concept_hierarchy' 탭 파싱 (괄호 뺀 정확한 컬럼명 매칭)
        concepts_hierarchy = {}
        for _, row in df_concepts.iterrows():
            major = str(row.get('대분류', '')).strip()
            mid = str(row.get('중분류', '')).strip()
            minor = str(row.get('소분류', '')).strip()
            
            if not major or not mid:
                continue
                
            if major not in concepts_hierarchy:
                concepts_hierarchy[major] = {}
            if mid not in concepts_hierarchy[major]:
                concepts_hierarchy[major][mid] = []
                
            concepts_hierarchy[major][mid].append({
                "minor": minor,
                "difficulty": str(row.get('난이도', '')).strip(),
                "point": str(row.get('출제포인트', '')).strip()
            })
            
        return questions_pool, concepts_hierarchy
    except Exception as e:
        st.error(f"🚨 구글 시트 다이렉트 로드 실패: {e}")
        return [], {}

# ── 사이드바 ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🗄️ 데이터베이스 모드")
    db_mode = st.radio(
        "DB 연결 방식 선택", 
        ["로컬 JSON (Internal)", "Google Sheets (Cloud)"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### ⚙️ API 설정")
    raw_api_key = st.text_input(
        "🔑 통합 API Key 입력창", 
        type="password", 
        placeholder="OpenRouter, Google AI, Azure 키 입력"
    )
    
    selected_model = st.selectbox(
        "🤖 출제 인공지능 엔진 모델",
        options=["anthropic/claude-opus-4.8", "openai/gpt-5.1", "google/gemini-3.1-pro-preview"]
    )
    
    detected_platform = "대기 중..."
    if raw_api_key:
        if raw_api_key.startswith("sk-or-"):
            detected_platform = "🔗 OpenRouter 허브 모드"
        elif raw_api_key.startswith("AIzaSy"):
            detected_platform = "♊ Google AI Studio 모드"
        elif len(raw_api_key) == 32 or "azure" in raw_api_key.lower():
            detected_platform = "☁️ Microsoft Azure 모드"
        elif raw_api_key.startswith("sk-"):
            detected_platform = "🟢 OpenAI 직결 모드"
            
    if raw_api_key:
        st.caption(f"**활성화된 연결:** `{detected_platform}`")
        if "Azure" in detected_platform:
            azure_endpoint = st.text_input("Azure Endpoint URL", placeholder="https://YOUR_RESOURCE.openai.azure.com/")

# ── DB 할당 및 문제 유형 정렬 ──
if db_mode == "로컬 JSON (Internal)":
    QUESTIONS, CONCEPTS = load_json_db()
else:
    # 🚀 수정됨: 두 개의 URL을 각각 넘겨줍니다.
    QUESTIONS, CONCEPTS = load_gsheets_dual_db(QUESTIONS_SHEET_URL, CONCEPTS_SHEET_URL)
    
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

st.markdown("""
<div class="main-header">
  <h1>📝 영어 기출 문제 생성기</h1>
  <p>강남구 중학교 기출 154문제 데이터 기반 · AI 응용 문제 자동 생성 (클라우드/로컬 하이브리드)</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바 통계 ──
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📊 현재 로드된 DB 현황")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="stat-box"><div class="num">{len(QUESTIONS)}</div><div class="label">기출/참고 데이터</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-box"><div class="num">{len(CONCEPTS)}</div><div class="label">대분류</div></div>', unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**📚 문법 대분류**")
    for major in CONCEPTS:
        total = sum(len(v) for v in CONCEPTS[major].values())
        st.markdown(f"- {major} ({total}개 소개념)")

if "history" not in st.session_state:
    st.session_state.history = []
if "pending" not in st.session_state:
    st.session_state.pending = []

tab1, tab2, tab3 = st.tabs(["🤖 AI 문제 생성", "📚 기출 문제 탐색", "📋 생성 기록"])

# ════════════════════════════════════════════════════════
# TAB 1 : AI 문제 생성
# ════════════════════════════════════════════════════════
with tab1:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 📖 문법 개념 선택")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)

        major_list = list(CONCEPTS.keys()) if CONCEPTS else ["데이터 없음"]
        selected_major = st.selectbox("① 대분류", major_list, key="major")

        mid_list = list(CONCEPTS[selected_major].keys()) if CONCEPTS and selected_major in CONCEPTS else ["데이터 없음"]
        selected_mid = st.selectbox("② 중분류", mid_list, key="mid")

        minor_items = CONCEPTS[selected_major][selected_mid] if CONCEPTS and selected_major in CONCEPTS and selected_mid in CONCEPTS[selected_major] else []
        minor_labels = [item["minor"] for item in minor_items if item["minor"]]
        
        if minor_labels:
            selected_minor_label = st.selectbox("③ 소분류", minor_labels, key="minor")
            selected_item = next((x for x in minor_items if x["minor"] == selected_minor_label), None)
            if selected_item:
                diff = selected_item["difficulty"]
                diff_class = f"diff-{diff}" if diff else ""
                st.markdown(f'④ 개념의 난이도: <span class="diff-badge {diff_class}">{diff if diff else "미분류"}</span>', unsafe_allow_html=True)
                if selected_item.get("point"):
                    with st.expander("💡 출제 포인트 보기"):
                        st.markdown(selected_item["point"])
        else:
            selected_minor_label = ""
            selected_item = None
            diff = ""

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### ✏️ 추가 요청사항")
        extra = st.text_area(
            "추가 요청",
            placeholder="예) 난이도 상으로 함정 선지 포함\n예) 스포츠 주제로, 강남구 기출 스타일",
            height=100,
            label_visibility="collapsed",
        )

    with col_right:
        st.markdown("### 📋 문제 유형 & 개수")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("**문제 유형 선택 (복수 가능)**")

        # 🚀 에러 방지용 안전장치 (가장 완벽한 형태)
        safe_default = ["어법상 맞는 것"] if "어법상 맞는 것" in SORTED_TYPES else (SORTED_TYPES[:1] if SORTED_TYPES else None)

        selected_types = st.multiselect(
            "유형",
            SORTED_TYPES,
            default=safe_default,
            label_visibility="collapsed",
        )

        st.markdown("**유형별 생성 개수**")
        num_per_type = st.slider("개수", 1, 10, 5)
        st.markdown('</div>', unsafe_allow_html=True)

        ref_pool = [q for q in QUESTIONS if selected_major in q["u"] or selected_mid in q.get("s","")]
        if not ref_pool:
            ref_pool = QUESTIONS
        st.info(f"📎 참고 기출: {len(ref_pool)}문제 ('{selected_major}' 관련)")

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
        if not raw_api_key:
            st.error("⚠️ 사이드바에 통합 API Key를 입력해주세요.")
        elif not selected_types:
            st.error("⚠️ 문제 유형을 하나 이상 선택해주세요.")
        else:
            batch_results = []
            progress = st.progress(0, text="생성 중...")
            total = len(selected_types)
            
            client = None
            is_google_native = False
            
            if raw_api_key.startswith("sk-or-"):
                client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=raw_api_key)
            elif raw_api_key.startswith("AIzaSy"):
                genai.configure(api_key=raw_api_key)
                is_google_native = True
            elif len(raw_api_key) == 32 or "azure" in raw_api_key.lower():
                try:
                    client = AzureOpenAI(
                        api_key=raw_api_key,
                        api_version="2024-02-15-preview", 
                        azure_endpoint=azure_endpoint
                    )
                except NameError:
                    st.error("Azure 연결을 위한 엔드포인트 URL을 입력해주세요.")
            else:
                client = OpenAI(api_key=raw_api_key)

            for idx, qtype in enumerate(selected_types):
                progress.progress((idx) / total, text=f"[{idx+1}/{total}] '{qtype}' 유형 생성 중...")

                type_matched = [q for q in QUESTIONS if q["t"] == qtype]
                unit_matched = [q for q in QUESTIONS if selected_major in q["u"]]
                qtype_pool = type_matched if len(type_matched) >= 3 else (unit_matched if unit_matched else QUESTIONS)
                ref_samples = random.sample(qtype_pool, min(5, len(qtype_pool)))
                ref_text = "\n\n".join([
                    f"[기출 {i+1}]\n문제유형: {q['t']}\n발문: {q['q']}\n보기/지문: {q['c']}\n정답: {q['a']}\n해설: {q['e']}"
                    for i, q in enumerate(ref_samples)
                ])

                point_text = selected_item.get("point", "") if selected_item else ""

                prompt = f"""당신은 대한민국 강남권 최고 수준의 영어 내신 출제위원입니다.

=== [역할 A] 기출문제 벤치마킹 (형식 및 오답 설계 논리 카피) ===
아래 5개의 기출문제는 당신이 타겟으로 삼아야 할 '최고 수준의 퀄리티'를 보여줍니다.
단순히 번호 형식(①②③)만 베끼는 것이 아니라, **지문의 길이, 어휘의 난이도, 고등학생을 속이는 교묘한 오답(Distractor) 설계 논리, 그리고 논리적인 해설 방식까지 100% 완벽하게 모방(Copy)** 하세요.

[참고용 기출문제 5선]
{ref_text}

=== [역할 B] 출제 타겟 개념 (이 개념을 주제로 출제할 것) ===
- 대분류: {selected_major}
- 중분류: {selected_mid}
- 소분류: {selected_minor_label}
- 난이도: {diff if diff else '미지정'}
- 핵심 출제 포인트: {point_text}

=== 출제 조건 ===
- 문제 유형: {qtype}
- 생성 개수: {num_per_type}개
- 추가 요청: {extra if extra else '없음'}

=== ★ 객관식 선지 작성 절대 규칙 (치명적 출제 오류 방지) ★ ===
1. [역할 B]의 핵심 포인트를 기반으로 출제하되, 문장의 퀄리티는 [역할 A]를 닮아야 합니다.
2. "어법상 맞는 것을 고르시오" 유형: 정답인 1개 선지만 문법적으로 완벽해야 하며, 나머지 4개 선지는 반드시 논란의 여지가 없는 100% 명백한 문법적 오류(예: 자동사의 수동태 사용 등)를 포함해야 합니다.
3. "어법상 틀린 것을 고르시오" 유형: 정답인 1개 선지만 명백한 문법적 오류가 있어야 하며, 나머지 4개 선지는 완벽하게 올바른 문장이어야 합니다.
4. **[사후 정당화 절대 금지]**: 문법적으로 올바른 선지를 만들어 놓고 해설에서 "문맥상 어색하다", "병렬 구조라 생략해야 한다", "학습 포인트가 아니다" 등의 억지 핑계를 대며 오답 처리하는 것을 엄격히 금지합니다. 오답은 오직 '문법적 오류 팩트'로만 증명해야 합니다.
5. 'cans', 'musted' 처럼 존재하지 않는 유치한 단어를 지어내지 말고, 수식어구로 주어-동사 거리를 벌리는 등 구문 분석을 요하는 실전형 함정을 파세요.
6. 선지는 ①②③④⑤ 형식으로 5개 구성, 각 문제마다 [정답]과 [해설]을 포함하세요.

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
                    if is_google_native:
                        gemini_model_name = "gemini-1.5-pro" if "gemini" in selected_model.lower() else "gemini-1.5-pro"
                        model = genai.GenerativeModel(gemini_model_name)
                        response = model.generate_content(prompt)
                        result_text = response.text
                    else:
                        target_model = selected_model
                        if "sk-" in raw_api_key and not raw_api_key.startswith("sk-or-") and "gpt" not in selected_model:
                            target_model = "gpt-4o"
                            
                        response = client.chat.completions.create(
                            model=target_model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.75
                        )
                        result_text = response.choices[0].message.content

                    batch_results.append({"type": qtype, "text": result_text})
                except Exception as e:
                    batch_results.append({"type": qtype, "text": f"[오류] 출제 엔진 통신 실패: {e}"})

            progress.progress(1.0, text="✅ 생성 완료!")

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
            st.rerun()

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
                        st.markdown("💡 **해설:**")
                        st.markdown(parts["해설"].replace("\n", "  \n"))
                    st.markdown('</div>', unsafe_allow_html=True)

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

    def render_newlines(text: str) -> str:
        return text.replace("\n", "  \n")

    st.markdown(f"**검색 결과: {len(filtered)}문제**")
    for q in filtered[:30]:
        with st.expander(f"[{q['u']} > {q['s']}] {q['t']} — {q['q'][:60]}"):
            st.markdown(f"**발문:** {q['q']}")
            if q["c"]:
                st.markdown("**보기/지문:**")
                st.markdown(render_newlines(q["c"]))
            st.markdown(f'<div class="answer-box">✅ <b>정답:</b> {q["a"]}</div>', unsafe_allow_html=True)
            if q["e"]:
                st.markdown("💡 **해설:**")
                st.markdown(render_newlines(q["e"]))
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

                set_text = f"[{h['major']} > {h['mid']} > {h['minor']}] 난이도: {h['difficulty']}\n\n"
                set_text += "\n\n".join(f"【{r['type']}】\n\n{r['text']}" for r in h["results"])
                st.download_button(
                    f"⬇️ 세트 {idx} 다운로드",
                    data=set_text.encode("utf-8"),
                    file_name=f"세트{idx}_{h['minor']}.txt",
                    mime="text/plain",
                    key=f"dl_set_{idx}",
                )
