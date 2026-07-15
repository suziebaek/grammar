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
            
            # 2. 난이도 변환 (프로그램이 애초에 배정한 정확한 난이도 활용)
            # 🚀 [선생님 아이디어 적용] 텍스트 파싱을 버리고, app.py에서 넘겨준 raw_diff 사용!
            diff_kr = r.get("raw_diff", "중") 
            diff_map = {"상": "H", "중": "M", "하": "L"}
            difficulty = diff_map.get(diff_kr, "M")
            
            # 3. [보기/지문] 파싱
            passage_text = ""
            for key in ["보기/지문", "보기", "지문", "선택지"]:
                if key in parts and parts[key]:
                    passage_text = parts[key]
                    break
            
            # 🚀 [선생님 아이디어 적용] 지문 속 원문자에 낚이지 않는 줄바꿈(Line-by-Line) 탐색
            lines = passage_text.split('\n')
            prompt_lines = []
            opts_text = ""
            found_opts_start = False
            
            for i, line in enumerate(lines):
                # 앞뒤 공백을 자르고 맨 첫 글자가 '①' 인지 확인 (지문 중간에 섞인 ① 완벽 무시)
                if not found_opts_start and line.strip().startswith('①'):
                    found_opts_start = True
                    # 여기서부터 마지막 줄까지는 모두 선지로 간주하여 하나로 합침
                    opts_text = "\n".join(lines[i:])
                    break
                else:
                    prompt_lines.append(line)
            
            content_text_prompt = "\n".join(prompt_lines).strip()
            
            # 선지 1~5번 추출
            c1 = c2 = c3 = c4 = c5 = ""
            if found_opts_start:
                # 선지 블록 안에서 ①~⑤ 기호를 기준으로 쪼갬
                opts = re.split(r'[①-⑤]', opts_text)[1:]
                c1 = opts[0].strip() if len(opts) > 0 else ""
                c2 = opts[1].strip() if len(opts) > 1 else ""
                c3 = opts[2].strip() if len(opts) > 2 else ""
                c4 = opts[3].strip() if len(opts) > 3 else ""
                c5 = opts[4].strip() if len(opts) > 4 else ""
            else:
                # 혹시라도 줄바꿈 없이 ①이 등장한 극한의 예외 상황을 위한 방어막
                match = re.search(r'(.*?)(①.*?②.*?③.*?④.*?⑤.*)', passage_text, re.DOTALL)
                if match:
                    content_text_prompt = match.group(1).strip()
                    opts = re.split(r'[①-⑤]', match.group(2))[1:]
                    c1 = opts[0].strip() if len(opts) > 0 else ""
                    c2 = opts[1].strip() if len(opts) > 1 else ""
                    c3 = opts[2].strip() if len(opts) > 2 else ""
                    c4 = opts[3].strip() if len(opts) > 3 else ""
                    c5 = opts[4].strip() if len(opts) > 4 else ""
                else:
                    content_text_prompt = passage_text
                
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
