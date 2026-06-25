import json

def validate_question_llm(full_text, client, is_google_native, target_model, use_llm=True):
    if not use_llm:
        return True, "검증 생략"

    # 🚀 오직 논리적 오류만 판단하도록 프롬프트 단순화
    val_prompt = f"""
    아래 영어 문법 문제의 정답과 해설을 검토해.
    정답란에 적힌 정답이 해설 내용과 논리적으로 일치하는지 확인해.
    
    [문제 내용]
    {full_text}
    
    [검토 기준]
    - 정답 번호와 해설의 근거가 일치하면 PASS
    - 정답 번호와 해설이 논리적으로 모순되면 FAIL
    
    응답은 오직 'PASS' 또는 'FAIL:사유' 로만 답해.
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
        # 통신 에러 시엔 무조건 통과시키거나 에러를 리턴해 로직을 끊어버림
        return False, f"검증기 API 오류: {str(e)}"
