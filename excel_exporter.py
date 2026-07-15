# excel_exporter.py
import pandas as pd
import io
import re

def create_excel_document(history_data, is_multiple, is_e_level, concepts_dict):
    data = []
    entries = history_data if is_multiple else [history_data]
    level_char = "E" if is_e_level else "H"
    
    for entry in entries:
        major_name = entry.get('major', '')
        mid_name = entry.get('mid', '')
        
        # 1. cell_id 산출 (GR-H-CH01-C1 형태)
        majors = list(concepts_dict.keys())
        major_idx = majors.index(major_name) + 1 if major_name in majors else 1
        
        mids = list(concepts_dict.get(major_name, {}).keys())
        mid_idx = mids.index(mid_name) + 1 if mid_name in mids else 1
        
        cell_id = f"GR-{level_char}-CH{major_idx:02d}-C{mid_idx}"
        
        for r in entry["results"]:
            parts = r.get("parsed_parts", {})
            
            # 2. 난이도 매핑
            diff_kr = r.get("raw_diff", "중").strip()
            diff_map = {"상": "H", "중": "M", "하": "L"}
            difficulty = diff_map.get(diff_kr, "M")
            
            # 3. 문제 유형 및 발문
            question_type = "multiple_choice"
            content_question = r.get("clean_question", "").strip()
            if not content_question:
                content_question = parts.get("발문", "다음 중 어법상 올바른 문장을 고르시오.").strip()
            
            # 4. [지문 vs 선지] 철통 분리 알고리즘
            passage_text = r.get("clean_passage", "").strip()
            if not passage_text:
                for k in ["보기/지문", "보기", "지문", "선택지"]:
                    if k in parts and parts[k]:
                        passage_text = parts[k].strip()
                        break
            
            content_text_prompt = ""
            c1 = c2 = c3 = c4 = c5 = ""
            
            if passage_text:
                # 줄바꿈 단위로 쪼개어 검사
                lines = passage_text.split('\n')
                prompt_lines = []
                choices = []
                
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    # 🚀 [선생님 아이디어 적용] 줄의 첫 시작이 원문자(①~⑤)인 경우만 '진짜 선지'로 인정
                    if re.match(r'^[①-⑤]', stripped):
                        # 원문자 기호 제거 후 알맹이만 선지 배열에 추가
                        cleaned_choice = re.sub(r'^[①-⑤]\s*', '', stripped).strip()
                        choices.append(cleaned_choice)
                    else:
                        # 선지 시작 전이나 예문 내의 텍스트(중간에 ①이 섞였어도 통과됨)는 모두 지문으로 수집
                        prompt_lines.append(line)
                
                content_text_prompt = "\n".join(prompt_lines).strip()
                
                # 추출된 선지들을 1~5번에 순서대로 배정
                c1 = choices[0] if len(choices) > 0 else ""
                c2 = choices[1] if len(choices) > 1 else ""
                c3 = choices[2] if len(choices) > 2 else ""
                c4 = choices[3] if len(choices) > 3 else ""
                c5 = choices[4] if len(choices) > 4 else ""
                
                # 🚀 만약 줄바꿈 인식이 안 되어 선지를 하나도 못 발라냈을 경우, 2차 예비 패턴 가동
                if not choices:
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

            # 5. 정답 번호 숫자로 치환
            ans_raw = r.get("clean_answer", "").strip()
            if not ans_raw:
                ans_raw = parts.get("정답", "")
            
            ans_nums = []
            for idx, marker in enumerate(['①', '②', '③', '④', '⑤'], 1):
                if marker in ans_raw:
                    ans_nums.append(str(idx))
            if not ans_nums:
                ans_nums = re.findall(r'\d+', ans_raw)
            content_answer = ", ".join(ans_nums)
            
            # 6. 해설 및 메타데이터 정리
            explanation = r.get("clean_explanation", "").strip()
            if not explanation:
                explanation = parts.get("해설", "").strip()
            
            # 7. 최종 엑셀 레코드 조립 (wrap_up_item 포맷 100% 일치)
            row = {
                "semester": "2026-가을",
                "level_scope": level_char,
                "cell_id": cell_id,
                "difficulty": difficulty,
                "question_type": question_type,
                "content_question": content_question,
                "content_text_prompt": content_text_prompt,
                "content_choice_1": c1,
                "content_choice_2": c2,
                "content_choice_3": c3,
                "content_choice_4": c4,
                "content_choice_5": c5,
                "content_answer": content_answer,
                "explanation": explanation,
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
