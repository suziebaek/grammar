import streamlit as st
import random
from pathlib import Path
import google.generativeai as genai
from openai import OpenAI, AzureOpenAI
import pandas as pd
import re
import time

# ── 🎯 전역 설정: 구글 시트 탭별 GID URL 하드코딩 ────────────────────────
QUESTIONS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=939067680#gid=939067680"
CONCEPTS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=0#gid=0"

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="영어 기출 문제 생성기",
    page_icon="📝",
    layout="wide",
)

BASE = Path(__file__).parent

# ── 데이터 로드 함수 (구글 시트 전용) ────────────────────────────────────────
@st.cache_data(ttl=180)
def load_gsheets_dual_db(q_url, c_url):
    try:
        def convert_to_csv_url(url):
            sheet_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            gid_match = re.search(r'gid=([0-9]+)', url)
            if sheet_id_match:
                sheet_id = sheet_id_match.group(1)
                gid = gid_match.group(1) if gid_match else "0"
                # 캐시 무력화 파라미터 포함
                return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}&dummy={int(time.time())}"
            return url

        df_questions = pd.read_csv(convert_to_csv_url(q_url)).fillna('')
        df_concepts = pd.read_csv(convert_to_csv_url(c_url)).fillna('')
        
        # 열 이름 공백 제거
        df_questions.columns = [str(c).strip() for c in df_questions.columns]
        df_concepts.columns = [str(c).strip() for c in df_concepts.columns]
        
        if '대분류' not in df_questions.columns:
            st.error("🚨 기출DB를 제대로 읽어오지 못했습니다. 구글 시트 공유 권한을 확인해 주세요.")
            return [], {}

        # 난이도 열 탐색
        diff_col = next((col for col in df_questions.columns if '난이도' in col), None)

        # 1. 'questions_db' 탭 파싱
        questions_pool = []
        for _, row in df_questions.iterrows():
            q_type = str(row.get('문제유형', '')).strip()
            if not q_type:
                continue
                
            q_diff = ""
            if diff_col:
                val = str(row.get(diff_col, '')).strip()
                if "상" in val: q_diff = "상"
                elif "중" in val: q_diff = "중"
                elif "하" in val: q_diff = "하"

            questions_pool.append({
                "u": str(row.get('대분류', '')).strip(),
                "s": str(row.get('소분류', '')).strip(),
                "t": q_type,
                "q": str(row.get('발문', '')).strip(),
                "c": str(row.get('보기', '')).strip(),
                "a": str(row.get('정답', '')).strip(),
                "e": str(row.get('해설', '')).strip(),
                "d": q_diff
            })

        # 2. 'concept_hierarchy' 탭 파싱
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
        st.error(f"🚨 데이터 로드 중 치명적 오류 발생: {e}")
        return [], {}

# ── 사이드바 ───────────────────────────────────────────────────
with st.sidebar:
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

# ── DB 할당 (구글 시트 단일 모드) ──
QUESTIONS, CONCEPTS = load_gsheets_dual_db(QUESTIONS_SHEET_URL, CONCEPTS_SHEET_URL)
    


PRIMARY_TYPES = [
    "어법상 맞는 것", "어법상 옳은 것", "어법상 옳지 않은 것",
    "빈칸 채우기", "개수 고르기", "올바른 영작",
    "어법상 어색한 것", "어법상 바른 것", "바르게 짝지어진 것",
]
ALL_TYPES = sorted(set(q["t"] for q in QUESTIONS if q["t"]))
SORTED_TYPES = [t for t in PRIMARY_TYPES if t in ALL_TYPES] + \
               [t for t in ALL_TYPES if t not in PRIMARY_TYPES]

# 🚀 파이썬이 데이터를 어떻게 읽었는지 직접 확인하는 디버그 뷰 추가
with st.sidebar:
    with st.expander("🛠️ 데이터 매핑 디버그 확인"):
        st.write(TYPE_DIFF_MAP)

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
  }
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
        
        # 🚀 수정됨: '통합개념'을 리스트 맨 앞에 강제 삽입하여 기본값으로 만듦
        minor_labels = ["통합개념"] + [item["minor"] for item in minor_items if item["minor"]] if minor_items else []
        
        if minor_labels:
            selected_minor_label = st.selectbox("③ 소분류", minor_labels, key="minor")
            
            # [통합개념]이 선택되었을 때의 처리
            if selected_minor_label == "통합개념":
                diff = "통합"
                # 해당 중분류 아래의 모든 소분류 출제 포인트를 하나로 길게 합침
                point_text = "\n\n".join([f"[{x['minor']}]\n{x.get('point', '')}" for x in minor_items if x.get("point")])
                
                st.markdown(f'④ 개념의 난이도: <span class="diff-badge diff-중상">통합 출제</span>', unsafe_allow_html=True)
                with st.expander("💡 통합 출제 포인트 보기"):
                    st.markdown(point_text)
                    
            # [특정 단일 개념]이 선택되었을 때의 처리 (기존과 동일)
            else:
                selected_item = next((x for x in minor_items if x["minor"] == selected_minor_label), None)
                if selected_item:
                    diff = selected_item["difficulty"]
                    diff_class = f"diff-{diff}" if diff else ""
                    point_text = selected_item.get("point", "")
                    
                    st.markdown(f'④ 개념의 난이도: <span class="diff-badge {diff_class}">{diff if diff else "미분류"}</span>', unsafe_allow_html=True)
                    if point_text:
                        with st.expander("💡 출제 포인트 보기"):
                            st.markdown(point_text)
                else:
                    diff = ""
                    point_text = ""
        else:
            selected_minor_label = ""
            diff = ""
            point_text = ""

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

        safe_default = ["어법상 맞는 것"] if "어법상 맞는 것" in SORTED_TYPES else (SORTED_TYPES[:1] if SORTED_TYPES else None)

        selected_types = st.multiselect(
            "유형",
            SORTED_TYPES,
            default=safe_default,
            label_visibility="collapsed",
        )

        st.markdown("**유형별 생성 개수**")
        num_per_type = st.slider("개수", 1, 10, 1)
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

# 🚀 수정됨: Scheme B 로직 (통합개념일 경우 AI에게 강력한 골고루 출제 지시 추가)
                integration_rule = ""
                if selected_minor_label == "통합개념":
                    integration_rule = "7. [통합 출제 지시 (필수)]: 이번 세트는 여러 소분류 개념이 합쳐진 '통합개념' 테스트입니다. [역할 B]에 제시된 여러 출제 포인트들을 반드시 골고루 활용하여 문제를 창작하세요. 한 문제 안에 여러 개념을 섞어도 좋고, 각 문제마다 다른 개념을 사용해도 좋습니다. 절대 특정 한두 가지 개념에만 편중되어 출제하지 마세요.\n"
                prompt = f"""당신은 대한민국 강남권 최고 수준의 영어 내신 출제위원입니다.

=== [역할 A] 기출문제 벤치마킹 ===
아래 기출문제를 통해 발문 형식, 선지 구성 방식, 보기 스타일을 완벽하게 모방하세요.
{ref_text}

=== [역할 B] 출제 타겟 개념 ===
- 대분류: {selected_major}
- 중분류: {selected_mid}
- 소분류: {selected_minor_label}
- 난이도: {diff if diff else '미지정'}
- 핵심 출제 포인트: {point_text}

=== 출제 조건 ===
- 문제 유형: {qtype}
- 생성 개수: {num_per_type}개
- 추가 요청: {extra if extra else '없음'}

=== ★ 출제 규칙 ===
1. [지문 창작]: 기출의 문장 뼈대는 모방하되, 주어/어휘/상황(예: 과학, 역사, 시사 등)을 완전히 새로운 고등 모의고사 수준의 문장으로 창작하세요.
2. [치명적 오답 설계]: 'cans', 'musted' 같이 존재하지 않는 유치한 단어를 지어내는 것을 엄격히 금지합니다.
3. 오답(함정)을 만들 때는 주어와 동사 사이를 멀리 떨어뜨리거나 구문 분석을 요하도록 교묘하게 설계하세요.
4. 선지는 ①②③④⑤ 형식으로 5개 구성, 각 문제마다 [정답]과 [해설]을 포함하세요.
5. [해설 작성 규칙]: 해설에 "이 문제는 ~을 묻고 있다", "이것은 ~를 유도한 함정이다" 같은 출제자의 의도를 설명하는 메타적 코멘트를 절대 금지합니다. 오직 문법적 팩트에 기반한 건조하고 명확한 해설만 작성하세요.
6. [무결성 자체 검토]: 출력하기 전, ①보기 개수와 정답 번호가 일치하는지, ②정답 번호와 해설에서 설명하는 내용이 정확히 일치하는지 스스로 점검하여 논리적 모순을 100% 제거하세요.
=== 출력 형식 (반드시 준수) ===
【문제 N】
[발문]
내용

[보기/지문]
① ...
② ...

[정답] 

[해설]
[정답 해설]: 정답인 이유를 문법적으로 명확히 설명.
[오답 분석]: 나머지 선지들이 왜 틀렸는지(혹은 왜 맞았는지) 각각 번호를 매겨 명확히 분석.

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
                    # 에러 발생 시 숨기지 않고 무조건 텍스트로 저장하여 화면에 띄웁니다!
                    batch_results.append({"type": qtype, "text": f"[오류] 출제 엔진 통신 실패: {str(e)}"})

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

    # ── 결과 표시 (중복 에러 원천 차단) ─────────────────────────────────────────
    if st.session_state.pending:
        entry = st.session_state.pending[-1]
        st.markdown("---")
        st.markdown(f"### 📄 생성 결과 — {entry['major']} > {entry['mid']} > {entry['minor']}")

        for res in entry["results"]:
            with st.expander(f"📌 [{res['type']}] 유형 문제", expanded=True):
                raw = res["text"]
                
                # 통신 에러가 발생하면 붉은 에러창 띄우기
                if raw.startswith("[오류]"):
                    st.error(raw)
                    continue
                
                problems = raw.split("【문제")
                
                # AI가 양식을 지키지 못했을 때 원본 무조건 보여주기
                if len(problems) <= 1:
                    st.warning("⚠️ 양식이 깨졌거나 통신 오류가 발생했습니다. 원본을 확인하세요.")
                    st.markdown(raw.replace("\n", "  \n"))
                    continue

                valid_problem_found = False
                for prob in problems:
                    prob = prob.strip()
                    if not prob or not prob[0].isdigit():
                        continue
                    
                    valid_problem_found = True
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
                
                if not valid_problem_found:
                    st.markdown(raw.replace("\n", "  \n"))

        # 다운로드 버튼
        combined = f"[생성 정보]\n단원: {entry['major']} > {entry['mid']} > {entry['minor']}\n난이도: {entry['difficulty']}\n\n"
        combined += "\n\n" + "="*60 + "\n\n".join(
            f"【{r['type']} 유형】\n\n{r['text']}" for r in entry["results"]
        )
        st.download_button(
            "⬇️ 생성된 문제 전체 다운로드 (.txt)",
            data=combined.encode("utf-8"),
            file_name=f"{entry['major']}_{entry['minor']}_문제.txt",
            mime="text/plain",
            key=f"dl_pending_tab1_safe_{len(st.session_state.history)}"
        )

# ════════════════════════════════════════════════════════
# TAB 2 : 기출 문제 탐색 (복구 완료)
# ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📚 기출 문제 탐색")

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
        with st.expander(f"[{q['u']} > {q['s']}] {q['t']} — {q['q'][:60]}..."):
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
# TAB 3 : 생성 기록 (복구 완료)
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 📋 생성 기록")

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
            key="dl_history_all"  # 🚀 중복 방지 고유 키
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
                    key=f"dl_history_set_{idx}",  # 🚀 중복 방지 고유 키
                )
