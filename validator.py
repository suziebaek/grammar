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
