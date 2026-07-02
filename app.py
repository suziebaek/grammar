import streamlit as st
import random
from pathlib import Path
import google.generativeai as genai
from openai import OpenAI, AzureOpenAI
import pandas as pd
import re
import time
import io
from docx import Document # 🚀 [추가] 워드 다운로드를 위한 라이브러리 (pip install python-docx 필요)
from docx.shared import Pt  # 🚀 [추가] 폰트 크기(Pt) 조절을 위한 모듈
from validator import validate_question_llm, validate_batch_llm  # <--- 이 줄이 반드시 있어야 합니다!
from datetime import datetime
from prompts import build_generation_prompt as build_prompt_h
from prompts_e import build_generation_prompt_e


TOPIC_LIST = [
    "고대 역사", "우주 탐사", "심해 생물", "인공지능", 
    "미술수업", "스포츠 과학", "농업", "음악사", 
    "경제학", "기후 변화", "건축 공학", "야생 동물 보호",
    "지구 온난화", "일상 생활", "심리학", "학교 생활", "문학",
    "윤리", "언어학", "로봇", "환경", "지리", "종교", "소셜 미디어", "요리"
    
]

# ── 🚀 [수정] 난이도 세부 조합 (A, B, C) 64가지 경우의 수 사전 계산 ──
ALL_COMBS = [(a, b, c) for a in (0, 1, 2, 3) for b in (0, 1, 2, 3) for c in (0, 1, 2, 3)]
EASY_COMBS = [c for c in ALL_COMBS if sum(c) <= 2]       # 하: 0~2점 (10가지)
MID_COMBS = [c for c in ALL_COMBS if 3 <= sum(c) <= 6]   # 중: 3~6점 (44가지)
HARD_COMBS = [c for c in ALL_COMBS if sum(c) >= 7]       # 상: 7~9점 (10가지)
# 🚀 [추가] <u> 태그 인식해서 워드에 밑줄 긋는 헬퍼 함수

def add_paragraph_with_tags(doc_or_element, text):
    p = doc_or_element.add_paragraph()
    # <u>태그 단위로 텍스트 쪼개기
    parts = re.split(r'(<u>.*?</u>)', text)
    for part in parts:
        if part.startswith('<u>') and part.endswith('</u>'):
            run = p.add_run(part[3:-4]) # <u> </u> 떼어내고 알맹이만
            run.underline = True        # 워드 밑줄 속성 ON
        else:
            p.add_run(part)
            
# 🚀 [수정] 기존 create_word_document 함수 통째로 교체
def create_word_document(history_data, is_multiple=False):
    doc = Document()
    
    # 🚀 [추가] 챕터(생성정보) 글자 크기를 10pt로 강제하는 헬퍼 함수
    def add_custom_heading(text):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.font.size = Pt(10) # 글자 크기 10
        run.bold = True
        
    # 🚀 [추가] 워드에 쓸 때 [발문], [보기/지문] 등 브라켓을 싹 지우는 함수
    def clean_and_add_text(text):
        clean_text = text.replace("[발문]\n", "").replace("[보기/지문]\n", "").replace("[정답]\n", "").replace("[해설]\n", "")
        add_paragraph_with_tags(doc, clean_text.strip())

    if not is_multiple:
        entry = history_data
        add_custom_heading(f"생성 정보: {entry['major']} > {entry['mid']} > {entry['minor']}")
        doc.add_paragraph(f"난이도: {entry['difficulty']}")
        
        prev_type = None
# 기존: add_paragraph_with_tags(doc, r['text'])

# 🚀 단일 세트 처리 부분 (수정 후)
            for r in entry["results"]:
                if r['type'] != prev_type:
                    doc.add_heading(f"🟦 {r['type']} 유형", level=1)
                    prev_type = r['type']
                # UI용 text 대신 다운로드용 dl_text 삽입
                add_paragraph_with_tags(doc, r.get('dl_text', r['text']))


    else:
        doc.add_heading("전체 생성 문제 통합본", 0)
        for i, h in enumerate(history_data):
            add_custom_heading(f"[세트 {i+1}] {h['major']} > {h['mid']} > {h['minor']}")
            doc.add_paragraph(f"난이도: {h['difficulty']}")
            
            prev_type = None
# 🚀 다중 세트(전체) 처리 부분 (수정 후)
            for r in h["results"]:
                if r['type'] != prev_type:
                    doc.add_heading(f"🟦 {r['type']} 유형", level=2) 
                    prev_type = r['type']
                # UI용 text 대신 다운로드용 dl_text 삽입
                add_paragraph_with_tags(doc, r.get('dl_text', r['text']))
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ── 🎯 전역 설정: 구글 시트 탭별 GID URL 하드코딩 ────────────────────────
# [H레벨 시트 URL]
QUESTIONS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=939067680#gid=939067680"
CONCEPTS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=0#gid=0"

# 🚀 [추가] [E레벨 시트 URL] (선생님이 만드신 E레벨 전용 시트 URL로 교체하세요!)
E_QUESTIONS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=939067680#gid=939067680"
E_CONCEPTS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1gSMH96-BB8sjs4FbNy8bb_KSnP8zOpBQPQ_6Q4ylZ90/edit?gid=0#gid=0"

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="영어 기출 문제 생성기",
    page_icon="📝",
    layout="wide",
)

BASE = Path(__file__).parent
# 선지 재정렬
def sort_options(passage_text, ans_text, exp_text):
    match = re.search(r'(.*?)(①.*)', passage_text, re.DOTALL)
    if not match: return passage_text, ans_text, exp_text
    
    passage, opts_raw = match.group(1), match.group(2)
    opts = re.split(r'([①-⑤])', opts_raw)[1:]
    
    if len(opts) != 10: return passage_text, ans_text, exp_text
    
    old_opt_dict = {opts[i]: opts[i+1].strip() for i in range(0, len(opts), 2)}
    ans_match = re.search(r'[①-⑤]', ans_text)
    old_ans = ans_match.group(0) if ans_match else None
    
    # 텍스트 길이를 기준으로 예전 번호(키)들을 정렬
    old_keys = list(old_opt_dict.keys())
    sorted_old_keys = sorted(old_keys, key=lambda k: len(old_opt_dict[k]))
    
    markers = ['①', '②', '③', '④', '⑤']
    old_to_new = {old_k: markers[i] for i, old_k in enumerate(sorted_old_keys)}
    
    # 1. 보기 텍스트 재구성
    new_opts_str = "\n"
    for i, old_k in enumerate(sorted_old_keys):
        new_opts_str += f"{markers[i]} {old_opt_dict[old_k]}\n"
        
    # 2. 정답 번호 재구성
    new_ans = old_to_new.get(old_ans, ans_text) if old_ans else ans_text
    
    # 3. 해설 내 번호 일괄 치환 (충돌 방지용 임시 태그 사용)
    new_exp_text = exp_text
    for old_k in old_keys:
        new_exp_text = new_exp_text.replace(old_k, f"__TEMP_{old_k}__")
    for old_k, new_k in old_to_new.items():
        new_exp_text = new_exp_text.replace(f"__TEMP_{old_k}__", new_k)
        
    return passage + new_opts_str.strip(), new_ans, new_exp_text
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
        options=["anthropic/claude-sonnet-4.6", "anthropic/claude-opus-4.8", "openai/gpt-5.5", "openai/gpt-5.1", "google/gemini-3.1-pro-preview"]
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
# [여기서부터 복사하세요]
        if "Azure" in detected_platform:
            azure_endpoint = st.text_input("Azure Endpoint URL", placeholder="https://YOUR_RESOURCE.openai.azure.com/")
            
    # ── 사이드바: 레벨 선택 UI 추가 ──
    st.markdown("---")
    st.markdown("### 🎚️ 타겟 레벨 선택")
    selected_level = st.radio(
        "출제할 문제의 난이도 레벨을 선택하세요.", 
        ["H 레벨", "E 레벨"]
    )
    IS_E_LEVEL = selected_level == "E 레벨"

# ── 사전 DB 로드 (캐싱) ──
# (사이드바 블록이 끝난 후, 제일 먼저 데이터를 불러와야 합니다!)
H_QUESTIONS, H_CONCEPTS = load_gsheets_dual_db(QUESTIONS_SHEET_URL, CONCEPTS_SHEET_URL)
E_QUESTIONS, E_CONCEPTS = load_gsheets_dual_db(E_QUESTIONS_SHEET_URL, E_CONCEPTS_SHEET_URL)

# ── 선택된 레벨에 따라 전역 변수(소켓) 스위칭 ──
if IS_E_LEVEL:
    QUESTIONS = E_QUESTIONS
    CONCEPTS = E_CONCEPTS
    build_generation_prompt = build_generation_prompt_e
else:
    QUESTIONS = H_QUESTIONS
    CONCEPTS = H_CONCEPTS
    build_generation_prompt = build_prompt_h
# [여기까지 복사해서 덮어쓰세요]

# (이 아래로는 기존 코드 그대로 유지)
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
        
        minor_options = [item["minor"] for item in minor_items if item["minor"]] if minor_items else []
        
        if minor_options:
            selected_minors = st.multiselect("③ 소분류 (복수 선택 가능)", minor_options, default=minor_options, key="minor")
            
            if not selected_minors:
                selected_minor_label = "선택 안 됨"
                diff = ""
                point_text = ""
                st.warning("소분류를 1개 이상 선택하세요.")
            elif len(selected_minors) == 1:
                selected_minor_label = selected_minors[0]
                selected_item = next((x for x in minor_items if x["minor"] == selected_minor_label), None)
                diff = selected_item["difficulty"] if selected_item else ""
                diff_class = f"diff-{diff}" if diff else ""
                point_text = selected_item.get("point", "")
                
                st.markdown(f'④ 개념의 난이도: <span class="diff-badge {diff_class}">{diff if diff else "미분류"}</span>', unsafe_allow_html=True)
                if point_text:
                    with st.expander("💡 출제 포인트 보기"):
                        st.markdown(point_text)
            else:
                selected_minor_label = ", ".join(selected_minors)
                diff = "복합"
                selected_items = [x for x in minor_items if x["minor"] in selected_minors]
                point_text = "\n\n".join([f"[{x['minor']}]\n{x.get('point', '')}" for x in selected_items if x.get("point")])
                
                st.markdown(f'④ 개념의 난이도: <span class="diff-badge diff-중상">복합 출제</span>', unsafe_allow_html=True)
                with st.expander("💡 복합 출제 포인트 보기"):
                    st.markdown(point_text)
        else:
            selected_minor_label = ""
            selected_minors = []
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

        # ────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**📊 난이도 배정**")
        
        st.caption("배정 방식 선택")
        t_col1, t_col2, t_col3 = st.columns([2.5, 1, 6.5])
        with t_col1: 
            st.markdown("<div style='text-align:right; margin-top:4px; font-weight:bold; color:#475569;'>🤖 자동</div>", unsafe_allow_html=True)
        with t_col2: 
            is_manual = st.toggle("모드", value=False, key="auto_mode", label_visibility="collapsed")
        with t_col3: 
            st.markdown("<div style='margin-top:4px; font-weight:bold; color:#475569;'>🛠️ 수동</div>", unsafe_allow_html=True)

        is_disabled = not is_manual

        st.caption("난이도 활성화")
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1: st.toggle("🔴 상", value=True, key="btn_high", disabled=is_disabled)
        with btn_col2: st.toggle("🔵 중", value=True, key="btn_mid", disabled=is_disabled)
        with btn_col3: st.toggle("🟢 하", value=True, key="btn_low", disabled=is_disabled)
        
        st.caption("문항 수 할당")
        num_col1, num_col2, num_col3 = st.columns(3)
        with num_col1: val_high = st.number_input("상 (개)", min_value=0, max_value=20, value=3, key="num_high", disabled=is_disabled)
        with num_col2: val_mid = st.number_input("중 (개)", min_value=0, max_value=20, value=4, key="num_mid", disabled=is_disabled)
        with num_col3: val_low = st.number_input("하 (개)", min_value=0, max_value=20, value=3, key="num_low", disabled=is_disabled)

        if not is_manual:
            final_high, final_mid, final_low = 3, 4, 3
            st.info("🤖 **[자동 모드]** 기본값(상3, 중4, 하3)으로 배정됩니다.")
        else:
            final_high, final_mid, final_low = val_high, val_mid, val_low
            
        # 🚀 [수정] 변수명을 직관적으로 바꾸고 안내 문구를 '총합'의 의미로 변경
        total_num = final_high + final_mid + final_low
        
        if is_manual:
            st.success(f"✅ 선택한 유형에 **총 {total_num}개**의 문제가 골고루 배정됩니다.")
        # ────────────────────────────────────────────────────────

        st.markdown('</div>', unsafe_allow_html=True)

        ref_pool = [q for q in QUESTIONS if selected_major in q["u"] or selected_mid in q.get("s","")]
        if not ref_pool:
            ref_pool = QUESTIONS
        st.info(f"📎 참고 기출: {len(ref_pool)}문제 ('{selected_major}' 관련)")
            
# ── 생성 버튼 ─────────────────────────────────────────
    st.markdown("---")
    gen_col1, gen_col2, gen_col3 = st.columns([2.5, 1.5, 1])
    with gen_col1:
        generate_btn = st.button("🚀 문제 생성하기", use_container_width=True)
    with gen_col2:
        use_validator = st.toggle("🛡️ LLM 검증기 작동", value=False, help="AI가 논리적 오류를 검수합니다.")
    with gen_col3:
        clear_btn = st.button("🗑️ 결과 초기화", use_container_width=True)

    if clear_btn:
        st.session_state.pending = []
        st.rerun()

    # ── 생성 실행 ─────────────────────────────────────────
    if generate_btn:
        total_num = final_high + final_mid + final_low
        safe_api_key = raw_api_key.strip() if raw_api_key else ""
        
        if total_num == 0:
            st.error("⚠️ 생성할 문제 개수가 0개입니다. 난이도별 문항 수를 1개 이상 배정해주세요.")
        elif not safe_api_key:
            st.error("⚠️ 사이드바에 통합 API Key를 입력해주세요.")
        elif not selected_types:
            st.error("⚠️ 문제 유형을 하나 이상 선택해주세요.")
        else:
            batch_results = []
            progress = st.progress(0, text="생성 중...")
            total = len(selected_types)
            
            client = None
            is_google_native = False
            
            if safe_api_key.startswith("sk-or-"):
                client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=safe_api_key)
            elif safe_api_key.startswith("AIzaSy"):
                genai.configure(api_key=safe_api_key)
                is_google_native = True
            elif len(safe_api_key) == 32 or "azure" in safe_api_key.lower():
                try:
                    client = AzureOpenAI(api_key=safe_api_key, api_version="2024-02-15-preview", azure_endpoint=azure_endpoint)
                except NameError:
                    st.error("Azure 연결을 위한 엔드포인트 URL을 입력해주세요.")
            else:
                client = OpenAI(api_key=safe_api_key)

# 🚀 [수정] 레벨별 난이도 배정 메커니즘 분리
            if IS_E_LEVEL:
                # E레벨 (기존 스케일 0~9점 유지)
                EASY_POOL = [c for c in ALL_COMBS if sum(c) <= 2]       # 하 (0~2)
                MID_POOL  = [c for c in ALL_COMBS if 3 <= sum(c) <= 6]  # 중 (3~6)
                HARD_POOL = [c for c in ALL_COMBS if sum(c) >= 7]       # 상 (7~9)
            else:
                # H레벨 (최대 7점 캡 적용)
                EASY_POOL = [c for c in ALL_COMBS if sum(c) <= 2]       # 하 (0~2)
                MID_POOL  = [c for c in ALL_COMBS if 3 <= sum(c) <= 5]  # 중 (3~5)
                HARD_POOL = [c for c in ALL_COMBS if 6 <= sum(c) <= 7]  # 상 (6~7) 캡

            diff_targets = []
            for _ in range(final_high): diff_targets.append({"level": "상", "comb": random.choice(HARD_POOL)})
            for _ in range(final_mid):  diff_targets.append({"level": "중", "comb": random.choice(MID_POOL)})
            for _ in range(final_low):  diff_targets.append({"level": "하", "comb": random.choice(EASY_POOL)})
            
            allocations = {t: [] for t in selected_types}
            for i, diff_dict in enumerate(diff_targets):
                allocations[selected_types[i % len(selected_types)]].append(diff_dict)

            random.shuffle(TOPIC_LIST)
            topic_index = 0
            
            # 🚀 [추가] 유형이 바뀌어도 문제 번호가 계속 이어지도록 전역 카운터 설정
            global_q_num = 1 

            # 🚀 루프: 선택한 문제 유형별로 순회
            for idx, qtype in enumerate(selected_types):
                type_diffs = allocations[qtype]
                if not type_diffs: continue 
                
                num_for_this_type = len(type_diffs)
                progress.progress((idx) / total, text=f"[{idx+1}/{total}] '{qtype}' 유형 {num_for_this_type}문제 생성 중...")

                # 1. 기출 참고 데이터 준비
                type_matched = [q for q in QUESTIONS if q["t"] == qtype]
                unit_matched = [q for q in QUESTIONS if selected_major in q["u"]]
                qtype_pool = type_matched if len(type_matched) >= 3 else (unit_matched if unit_matched else QUESTIONS)
                ref_samples = random.sample(qtype_pool, min(6, len(qtype_pool)))
                ref_text = "\n\n".join([f"[기출 {i+1}]\n문제유형: {q['t']}\n발문: {q['q']}\n보기/지문: {q['c']}\n정답: {q['a']}\n해설: {q['e']}" for i, q in enumerate(ref_samples)])

                # 2. 통합개념 로직
                integration_rule = ""
                if len(selected_minors) > 1:
                    integration_rule = f"12. [복합 출제 지시 (필수)]: 이번 세트는 여러 소분류 개념이 합쳐진 복합 테스트입니다. [역할 B]에 제시된 출제 포인트들을 반드시 골고루 활용하여 절대 특정 개념에만 편중되지 않도록 창작하세요.\n"
                
                # 3. 난이도 상세 조건 문자열 생성 (소재 강제 주입 및 🚀연속 번호 적용)
                q_assignments = ""
                for d_dict in type_diffs:
                    lvl = d_dict["level"]
                    a, b, c = d_dict["comb"]
                    topic = TOPIC_LIST[topic_index % len(TOPIC_LIST)]
                    topic_index += 1                    
                    
                    # 🚀 [수정] i+1 대신 global_q_num을 사용하여 번호 누적
                    q_assignments += f"【문제 {global_q_num}】 타겟 난이도: [{lvl}] (조건: A={a}점, B={b}점, C={c}점) | 강제 지문 소재: [{topic}]\n"
                    global_q_num += 1

                # 4. 분리된 파일에서 프롬프트 불러오기
                prompt = build_generation_prompt(
                    ref_text=ref_text,
                    selected_major=selected_major,
                    selected_mid=selected_mid,
                    selected_minor_label=selected_minor_label,
                    point_text=point_text,
                    qtype=qtype,
                    num_for_this_type=num_for_this_type,
                    extra=extra,
                    q_assignments=q_assignments,
                    integration_rule=integration_rule
                )

# 5. 생성 및 배치 검증
                try:
                    if is_google_native:
                        # 🚀 Thinking 옵션은 그대로 유지합니다 (토큰 폭주 방지)
                        model = genai.GenerativeModel(
                            "gemini-3.1-pro-preview",
                            generation_config=genai.types.GenerationConfig(
                                thinking_config=genai.types.ThinkingConfig(
                                    thinking_level="high"
                                )
                            )
                        )
                        response = model.generate_content(prompt)
                        
                        # 🚀 [수정] 전체 텍스트를 통째로 가져오지 않고, '마지막 최종 답변 파트'만 추출합니다.
                        try:
                            # 응답 파트들(parts) 중 맨 마지막(-1) 텍스트만 꺼내옴
                            result_text = response.candidates[0].content.parts[-1].text
                        except Exception:
                            # 구조가 다를 경우를 대비한 안전망 (폴백)
                            result_text = response.text
                            
                    else:
                        response = client.chat.completions.create(
                            model=selected_model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.75,
                            max_tokens=7000
                        )
                        result_text = response.choices[0].message.content

                    # ... (이후 결과 쪼개기 및 검증 루프 동일) ...
# 🚀 [추가] 마크다운 이스케이프 및 HTML 공백 강제 세탁
                    if result_text:
                        result_text = result_text.replace(r"\_", "_").replace("&nbsp;", " ")

                    # 🚀 [핵심 방어 코드] AI 응답이 None(빈 값)으로 올 경우 에러를 강제로 발생시켜 안전하게 예외 처리함
                    if result_text is None:
                        raise Exception("AI가 텍스트 대신 빈 값을 반환했습니다. (안전 필터 차단 또는 서버 일시 오류)")

                    problems = result_text.split("【문제")
                    
                    if use_validator:
                        st.write("DEBUG: 검증기 호출 시작...")
                        batch_feedback = validate_batch_llm(
                            full_text=result_text,
                            client=client,
                            is_google_native=is_google_native,
                            target_model="google/gemini-3.1-pro-preview",
                            use_llm=use_validator
                        )
                        st.write("DEBUG: 검증기 호출 완료.")
                    else:
                        batch_feedback = {}
                    
                    for i, prob_text in enumerate(problems[1:]):
                        prob_text = prob_text.strip()
                        if not prob_text: continue
                        full_text = "【문제" + prob_text
                        is_valid, feedback = batch_feedback.get(i+1, (True, "PASS"))
                        
                        # 🚀 [추가] 다운로드 파일에도 적용되도록 '데이터 자체'를 영구 정렬
                        parts = {}
                        tags = ["발문", "보기/지문", "정답", "해설"]
                        for tag in tags:
                            key = f"[{tag}]"
                            if key in full_text:
                                start = full_text.index(key) + len(key)
                                nexts = [f"[{t}]" for t in tags if f"[{t}]" in full_text[start:]]
                                end = full_text.index(nexts[0], start) if nexts else len(full_text)
                                parts[tag] = full_text[start:end].replace("---", "").strip()
                        
if "보기/지문" in parts and "정답" in parts and "해설" in parts:
                            new_passage, new_ans, new_exp = sort_options(parts["보기/지문"], parts["정답"], parts["해설"])
                            
                            # 문제 번호만 안전하게 추출
                            num_match = re.search(r'^(.*?)\n', prob_text)
                            num_str = num_match.group(1).replace('】', '').strip() if num_match else f"{i+1}"
                            
                            # 1. 화면 UI 표시용 (기존 유지: 파싱을 위해 괄호 필요)
                            full_text = f"【문제 {num_str}】\n[발문]\n{parts.get('발문', '')}\n\n[보기/지문]\n{new_passage}\n\n[정답]\n{new_ans}\n\n[해설]\n{new_exp}\n"
                            
                            # 🚀 2. 다운로드용 텍스트 (브라켓 모두 제거 & 문제와 발문 한 줄 결합)
                            # 예: "문제4. 빈칸에 들어갈 말로 적절한 것은?"
                            dl_text = f"문제{num_str}. {parts.get('발문', '').strip()}\n\n{new_passage.strip()}\n\n정답: {new_ans.strip()}\n해설: {new_exp.strip()}\n"
                        else:
                            # 안전망: 파싱 실패 시 원본에서 괄호만 강제 제거
                            full_text = "【문제" + prob_text
                            dl_text = full_text.replace("【", "").replace("】", ".").replace("[발문]\n", "").replace("[보기/지문]\n", "").replace("[정답]", "정답:").replace("[해설]", "해설:")

                        batch_results.append({
                            "type": qtype, 
                            "text": full_text, 
                            "dl_text": dl_text, # 👈 다운로드 전용 텍스트 추가
                            "is_valid": is_valid, 
                            "feedback": feedback
                        })

                except Exception as e:
                    batch_results.append({
                        "type": qtype, 
                        "text": f"[통신오류] {str(e)}", 
                        "is_valid": False, 
                        "feedback": "통신 실패"
                    })
            
            # 🚀 [여기서부터 중요!] 
            # 위의 except 블록이 끝난 후, 들여쓰기를 앞으로 당겨서 for 루프와 위치를 맞춥니다.
# 🚀 [수정] 이전에 제가 실수로 빼먹은 difficulty와 count를 다시 추가합니다.
            entry = {
                "major": selected_major,
                "mid": selected_mid,
                "minor": selected_minor_label,
                "difficulty": f"총 {total_num}문제 (상{final_high}/중{final_mid}/하{final_low})",
                "types": selected_types,
                "count": total_num,
                "results": batch_results,
            }
            st.session_state.history.append(entry)
            st.session_state.pending = [entry]
            
            st.rerun()

            # ⬆️ (기존 코드) 여기까지가 생성 및 저장 완료 부분입니다.

    # 🚀 [복구] 여기서부터가 날아갔던 결과 화면 출력 코드입니다! (붙여넣기)
    # ── 결과 표시 ─────────────────────────────────────────
    if st.session_state.pending:
        entry = st.session_state.pending[-1]
        st.markdown("---")
        st.markdown(f"### 📄 생성 결과 — {entry['major']} > {entry['mid']} > {entry['minor']} ({entry.get('difficulty', '')})")

        prev_type = None # 이전 유형 추적용 변수 추가
        for res in entry["results"]:
            # 🚀 이전 문항과 유형이 다를 때만 대제목 출력
            if res['type'] != prev_type:
                st.markdown(f"### 🟦 【{res['type']}】 유형")
                prev_type = res['type']
            
            if not res.get("is_valid", True):
                st.error(f"⚠️ **검증 실패 사유:** {res.get('feedback')}")
            else:
                st.success("✅ **검증 통과**")

            raw = str(res.get("text", ""))
            
            # 통신 에러 UI
            if raw.startswith("[통신오류]"):
                st.error("⚠️ 통신 에러가 발생하여 생성이 중단되었습니다.")
                st.warning(raw)
                continue 
            problems = raw.split("【문제")
            
            # 🚀 [수정] 들여쓰기 교정
            if len(problems) <= 1:
                st.warning("⚠️ 양식이 깨졌거나 렌더링 오류가 발생했습니다. 원본을 확인하세요.")
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
                    st.markdown(f"**{parts['발문']}**", unsafe_allow_html=True)
                if "보기/지문" in parts:
                    st.markdown(parts["보기/지문"], unsafe_allow_html=True)
                if "정답" in parts:
                    st.markdown(f'<div class="answer-box">✅ <b>정답:</b> {parts["정답"]}</div>', unsafe_allow_html=True)
                if "해설" in parts:
                    st.markdown("💡 **해설:**")
                    st.markdown(parts["해설"].replace("\n", "  \n"))
                st.markdown('</div>', unsafe_allow_html=True)
            
            if not valid_problem_found:
                st.markdown(raw.replace("\n", "  \n"))



# ── 루프 끝 ──
        
        # 🚀 [수정] for 루프가 모두 끝난 뒤 '단 한 번만' 실행되도록 들여쓰기를 맞춥니다.
        st.markdown("---")
        set_text = f"[{entry['major']} > {entry['mid']} > {entry['minor']}] {entry.get('difficulty', '')}\n\n"
# 기존: set_text += "\n\n".join(f"【{r['type']}】\n\n{r.get('text', '')}" for r in entry["results"])
        
        # 🚀 이렇게 교체 (유형별 제목은 남기고, 문제 내용은 괄호 없는 버전으로)
        set_text = f"[{entry['major']} > {entry['mid']} > {entry['minor']}] {entry.get('difficulty', '')}\n\n"
        prev_dl_type = None
        for r in entry["results"]:
            if r['type'] != prev_dl_type:
                set_text += f"\n🟦 {r['type']} 유형\n\n"
                prev_dl_type = r['type']
            set_text += f"{r.get('dl_text', r['text'])}\n\n"
            
        # 날짜, 모델명 파싱 및 파일명 조합
        now_str = datetime.now().strftime("%y%m%d")
        safe_model = selected_model.split('/')[-1] 
        f_name = f"{entry['major']}_{entry['mid']}_{now_str}_{safe_model}"
    
        dl_col1, dl_col2 = st.columns(2)
        unique_key = len(st.session_state.history)  # 중복 방지를 위한 고유 번호
        
        with dl_col1:
            st.download_button(
                "⬇️ 방금 만든 문제 다운로드 (.txt)",
                data=set_text.encode("utf-8"),
                file_name=f"{f_name}.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"dl_current_txt_{unique_key}"  # 중복 에러 완벽 차단
            )
        with dl_col2:
            st.download_button(
                "📄 방금 만든 문제 다운로드 (.docx)",
                data=create_word_document(entry, is_multiple=False),
                file_name=f"{f_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"dl_current_docx_{unique_key}" # 중복 에러 완벽 차단
            )
# ════════════════════════════════════════════════════════
# TAB 2 : 기출 문제 탐색
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
# TAB 3 : 생성 기록
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 📋 생성 기록")

    if not st.session_state.history:
        st.info("아직 생성된 문제가 없습니다.")
    else:
        # 🚀 [수정 1] 전체 통합 다운로드 (txt / docx 분리)
        all_combined = ""
        for i, h in enumerate(st.session_state.history):
            all_combined += f"\n{'='*70}\n"
            all_combined += f"[세트 {i+1}] {h['major']} > {h['mid']} > {h['minor']} | 난이도: {h['difficulty']}\n"
            all_combined += f"{'='*70}\n\n"
            for r in h["results"]:
                all_combined += f"【{r['type']} 유형】\n\n{r['text']}\n\n"

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ 전체 기록 통합 다운로드 (.txt)",
                data=all_combined.encode("utf-8"),
                file_name="전체_생성문제.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_history_all_txt"
            )
        with c2:
            st.download_button(
                "📄 전체 기록 통합 다운로드 (.docx)",
                data=create_word_document(st.session_state.history, is_multiple=True),
                file_name="전체_생성문제.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_history_all_docx"
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

                # 기존 파일명 변수 교체
                set_f_name = f"{datetime.now().strftime('%y%m%d')}_{selected_model.split('/')[-1]}_{h['major']}_{h['mid']}"
                
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.download_button(
                        f"⬇️ 세트 {idx} 다운로드 (.txt)",
                        data=set_text.encode("utf-8"),
                        file_name=f"{set_f_name}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"dl_history_set_txt_{idx}",
                    )
                with sc2:
                    st.download_button(
                        f"📄 세트 {idx} 다운로드 (.docx)",
                        data=create_word_document(h, is_multiple=False),
                        file_name=f"{set_f_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"dl_history_set_docx_{idx}",
                    )
