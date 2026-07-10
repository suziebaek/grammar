import base64
import io
import os
import tempfile

import pandas as pd
import streamlit as st

from parser import parse_chapter_map, parse_question_doc, match_cell_id
from xlsx_builder import build_workbook, WRAP_UP_COLUMNS
from assets_data import TEMPLATE_XLSX_B64, CHAPTER_DEF_DOCX_B64

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def default_template_bytes():
    return io.BytesIO(base64.b64decode(TEMPLATE_XLSX_B64))


def default_chapter_bytes():
    return io.BytesIO(base64.b64decode(CHAPTER_DEF_DOCX_B64))

st.set_page_config(page_title="p-Learning 콘텐츠 적재 변환기", layout="wide")

st.title("📚 워드 문제 → 엑셀(wrap_up_item) 변환기")
st.caption("문제은행 워드 문서만 올리면, 정해진 챕터/셀 구조에 맞춰 엑셀 적재 양식으로 자동 변환합니다.")

with st.sidebar:
    st.header("문제 문서 업로드")
    question_files = st.file_uploader(
        "문제은행 워드 문서 (여러 개 선택 가능)", type=["docx"], accept_multiple_files=True
    )
    default_level_scope = st.selectbox("level_scope 기본값", ["H", "E", "HE"], index=0)
    run = st.button("🔄 변환 실행", type="primary", use_container_width=True)

    with st.expander("⚙️ 고급 설정 (템플릿/챕터 구조가 바뀐 경우에만 사용)"):
        st.caption("기본적으로 앱에 내장된 최신 엑셀 템플릿과 챕터/셀 정의 문서를 사용합니다. "
                   "구조가 바뀌었을 때만 아래에 새 파일을 올려 이번 변환에 한해 덮어쓸 수 있습니다.")
        template_override = st.file_uploader("엑셀 템플릿 덮어쓰기 (.xlsx)", type=["xlsx"], key="tmpl_override")
        chapter_override = st.file_uploader("챕터/셀 정의 문서 덮어쓰기 (.docx)", type=["docx"], key="chap_override")
        level = st.selectbox("챕터 문서의 level", ["H", "E"], index=0)

if "result" not in st.session_state:
    st.session_state.result = None

if run:
    if not question_files:
        st.error("문제은행 워드 문서를 1개 이상 업로드해 주세요.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            chapter_path = chapter_override if chapter_override is not None else default_chapter_bytes()
            template_path = template_override if template_override is not None else default_template_bytes()

            chapters, cells, lookup = parse_chapter_map(chapter_path, level=level)

            wrap_up_rows = []
            unmatched = []
            parse_warnings = []

            for qf in question_files:
                qpath = os.path.join(tmp, qf.name)
                with open(qpath, "wb") as f:
                    f.write(qf.getbuffer())

                parsed = parse_question_doc(qpath)
                header = parsed["header"]
                chapter_id, cell_id = match_cell_id(
                    header.get("chapter_title"), header.get("cell_name"), lookup
                )

                if not cell_id:
                    unmatched.append({
                        "파일명": qf.name,
                        "챕터(문서상)": header.get("chapter_title"),
                        "셀(문서상)": header.get("cell_name"),
                    })

                for w in parsed.get("warnings", []):
                    parse_warnings.append({"파일명": qf.name, "내용": w})

                for q in parsed["questions"]:
                    row = {col: None for col in WRAP_UP_COLUMNS}
                    row.update({
                        "cell_id": cell_id,
                        "difficulty": q.get("difficulty"),
                        "level_scope": default_level_scope,
                        "question_type": q.get("question_type"),
                        "content_question": q.get("content_question"),
                        "content_choice_1": q.get("content_choice_1"),
                        "content_choice_2": q.get("content_choice_2"),
                        "content_choice_3": q.get("content_choice_3"),
                        "content_choice_4": q.get("content_choice_4"),
                        "content_choice_5": q.get("content_choice_5"),
                        "content_answer": q.get("content_answer"),
                        "content_text_prompt": q.get("content_text_prompt"),
                        "explanation": q.get("explanation"),
                    })
                    wrap_up_rows.append(row)

            output_path = os.path.join(tmp, "output.xlsx")
            build_workbook(template_path, chapters, cells, wrap_up_rows, output_path)
            with open(output_path, "rb") as f:
                output_bytes = f.read()

        st.session_state.result = {
            "chapters": chapters,
            "cells": cells,
            "wrap_up_rows": wrap_up_rows,
            "unmatched": unmatched,
            "parse_warnings": parse_warnings,
            "output_bytes": output_bytes,
        }

result = st.session_state.result
if result:
    st.success(
        f"챕터 {len(result['chapters'])}개 · 셀 {len(result['cells'])}개 · "
        f"문제 {len(result['wrap_up_rows'])}개 변환 완료"
    )

    if result["unmatched"]:
        st.warning("⚠️ cell_id 매칭에 실패한 문서가 있습니다. 문서 첫 줄의 챕터/셀 이름 표기를 확인해 주세요.")
        st.dataframe(pd.DataFrame(result["unmatched"]), use_container_width=True)

    if result["parse_warnings"]:
        st.warning("⚠️ 일부 문항이 형식 문제로 제외되었습니다 (예: 정답 표기 누락). 원본 문서를 확인해 주세요.")
        st.dataframe(pd.DataFrame(result["parse_warnings"]), use_container_width=True)

    st.subheader("wrap_up_item 미리보기")
    df = pd.DataFrame(result["wrap_up_rows"])
    st.dataframe(df, use_container_width=True)

    st.download_button(
        "⬇️ 변환된 엑셀 다운로드",
        data=result["output_bytes"],
        file_name="content_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
else:
    st.info("왼쪽에서 문제은행 워드 문서를 업로드하고 '변환 실행'을 눌러주세요.")
    st.markdown("""
**기본 동작**
- 엑셀 템플릿과 챕터/셀 정의 문서는 앱에 내장되어 있어 따로 올릴 필요가 없습니다.
- 문제은행 워드 문서만 올리면 자동으로 cell_id를 찾아 매칭합니다.
  - `생성 정보: 챕터명 > 셀명 > 설명` 헤더가 있는 문서 → 그대로 매칭
  - 헤더 없이 첫 줄이 셀 이름만 있는 자유 형식 문서(예: "자동사") → 셀 이름만으로 고유하게
    찾아지면 자동 매칭, 동명의 셀이 여러 챕터에 있으면 매칭 실패로 표시됩니다.

**현재 지원 범위**
- 객관식(multiple_choice) 문제 자동 파싱 (🚨 검수 플래그는 무시하고 본문만 추출)
- "문제 N." 블록 형식과, 번호 없이 지시문("~고르시오.", "~것은?")으로 문항이 구분되는
  자유 형식 문서를 모두 지원합니다.
- 정답 표기가 없는 문항은 자동으로 제외되고 경고로 표시됩니다.
- 단답형(short_answer) / 영작(essay) 문제는 아직 실제 샘플 문서가 없어 자동 파싱 로직이 없습니다.

**템플릿/챕터 구조가 바뀌었다면**
- 사이드바 "⚙️ 고급 설정"에서 새 파일을 올리면 이번 변환에 한해 내장 파일 대신 사용됩니다.
- 계속 새 버전을 기본으로 쓰려면 `assets/template.xlsx`, `assets/chapter_def.docx`를 교체한 뒤
  `python build_assets.py`를 실행해 `assets_data.py`를 다시 생성하고 함께 배포하세요.
""")
