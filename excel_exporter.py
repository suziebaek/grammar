# excel_exporter.py
import pandas as pd
import io
import re

def create_excel_document(history_data, is_multiple, is_e_level, concepts_dict):
    """wrap_up_item 양식에 맞춘 엑셀 생성 전용 모듈"""
    data = []
    # 단일 세트인지 전체 기록인지에 따라 리스트화
    entries = history_data if is_multiple else [history_data]
    
    # level_scope 설정 (E 또는 H)
    level_char = "E" if is_e_level else "H"
    
    for entry in entries:
        major_name = entry.get('major', '')
        mid_name = entry.get('mid', '')
        
        # 1. cell_id 산출 (예: GR-H-CH01-C1)
        majors = list(concepts_dict.keys())
        major_idx = majors.index(major_name) + 1 if major_name in majors else 1
        
        mids = list(concepts_dict.get(major_name, {}).keys())
        mid_idx = mids.index(mid_name) + 1 if mid_name in mids else 1
        
        cell_id = f"GR-{level_char}-CH{major_idx:02d}-C{mid_idx}"
        
        for r in entry["results"]:
            parts = r.get("parsed_parts", {}) 
            
            # 2. 난이도 변환 (상->H, 중->M, 하->L)
            diff_kr = r.get("group_header", "").replace("🟦", "").replace("【", "").replace("】", "").replace("난이도", "").strip()
            diff_map = {"상": "H", "중": "M", "하": "L"}
            difficulty = diff_map.get(diff_kr, "M")
            
            # 3. [보기/지문] 파싱
            passage_text = parts.get("보기/지문", "")
            match = re.search(r'(.*?)(①.*?②.*?③.*?④.*?⑤.*)', passage_text, re.DOTALL)
            
            if match:
                content_text_prompt = match.group(1).strip()
                opts_raw = match.group(2)
                opts = re.split(r'[①-⑤]', opts_raw)[1:]
                c1 = opts[0].strip() if len(opts) > 0 else ""
                c2 = opts[1].strip() if len(opts) > 1 else ""
                c3 = opts[2].strip() if len(opts) > 2 else ""
                c4 = opts[3].strip() if len(opts) > 3 else ""
                c5 = opts[4].strip() if len(opts) > 4 else ""
            else:
                content_text_prompt = passage_text
                c1 = c2 = c3 = c4 = c5 = ""
                
            # 4. 정답 기호 -> 숫자 변환
            ans_raw = parts.get("정답", "")
            ans_nums = []
            for idx, marker in enumerate(['①', '②', '③', '④', '⑤'], 1):
                if marker in ans_raw:
                    ans_nums.append(str(idx))
            if not ans_nums:
                ans_nums = re.findall(r'\d+', ans_raw)
            content_answer = ", ".join(ans_nums)
            
            # 5. 최종 데이터 조립
            row = {
                "semester": "2026-가을",
                "level_scope": level_char,
                "cell_id": cell_id,
                "difficulty": difficulty,
                "question_type": "multiple_choice",
                "content_question": parts.get("발문", "").strip(),
                "content_text_prompt": content_text_prompt,
                "content_choice_1": c1,
                "content_choice_2": c2,
                "content_choice_3": c3,
                "content_choice_4": c4,
                "content_choice_5": c5,
                "content_answer": content_answer,
                "explanation": parts.get("해설", "").strip(),
                "expected_answer": "",
                "content_condition_1": "",
                "content_condition_2": "",
                "content_condition_3": "",
                "external_ref": ""
            }
            data.append(row)
            
    df = pd.DataFrame(data)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="wrap_up_item", index=False)
    
    return bio.getvalue()
