import json

def validate_question_llm(full_text, client, is_google_native, target_model, use_llm=True):
    if not use_llm:
        return True, "PASS"

    # AI에게 오직 'PASS' 또는 'FAIL'만 하라고 지시합니다.
    val_prompt = f"""
    당신은 영어 문제 검수 위원입니다. 아래 문제의 정답과 해설이 논리적으로 일치하는지 판단하세요.
    [문제]
    {full_text}
    
    [판단 기준]
    - 정답과 해설이 논리적으로 모순 없으면 "PASS"
    - 정답이 틀렸거나, 해설과 정답 번호가 안 맞으면 "FAIL: [이유]"
    
    응답은 오직 'PASS' 혹은 'FAIL:...' 형태로만 하세요.
    """
    
    try:
        if is_google_native:
            response = client.generate_content(val_prompt)
            result = response.text.strip()
        else:
            response = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": val_prompt}],
                temperature=0.0
            )
            result = response.choices[0].message.content.strip()

        if "FAIL" in result:
            return False, result
        return True, "PASS"
    except Exception as e:
        return False, f"FAIL: 통신 오류 ({str(e)})"
def validate_batch_llm(full_text, client, is_google_native, target_model, use_llm=True):
    if not use_llm:
        return {i: (True, "PASS") for i in range(1, 20)} # 임시 넉넉한 인덱스

val_prompt = f"""
    [문제 세트]
    {full_text}
    
    [명령]
    각 문제의 PASS/FAIL 여부만 판별해.
    
    [출력 규칙 - 반드시 준수]
    - "문제 N: P" 또는 "문제 N: F: 사유" 형식으로만 출력해.
    - P는 PASS, F는 FAIL을 의미해.
    - 1번 문제부터 순서대로 한 줄에 하나씩만 작성해.
    - 부연 설명, 서론, 결론 절대 금지. 
    - 예시:
    문제 1: P
    문제 2: F: 오답해설 틀림
    """
    
    try:
        if is_google_native:
            response = client.generate_content(val_prompt)
            result = response.text
        else:
            response = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": val_prompt}],
                temperature=0.0
            )
            result = response.choices[0].message.content
            
        # 결과 파싱 (문제 번호별로 딕셔너리 생성)
        batch_map = {}
        for line in result.split('\n'):
            if "문제" in line and (":" in line):
                try:
                    parts = line.split(":", 1)
                    idx = int(parts[0].replace("문제", "").strip())
                    status = parts[1].strip()
                    is_valid = "FAIL" not in status
                    batch_map[idx] = (is_valid, status)
                except: continue
        return batch_map
    except Exception as e:
        return {}
