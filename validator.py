import json
import re

def validate_question_llm(full_text, client, is_google_native, target_model, use_llm=True):
    """
    LLM을 이용해 생성된 문법 문제의 논리적 모순을 검증합니다.
    (파이썬 기반 하드 룰 검증 완전 제거됨)
    """
    # 🚀 토글이 꺼져있으면 묻지도 따지지도 않고 무조건 100% 합격 처리!
    if not use_llm:
        return True, "LLM 검증 생략 (무조건 통과)"

    # ── LLM 기반 정밀 논리 검증 ──
    val_prompt = f"""당신은 대한민국 최고 수준의 문법 문제 검수자(Validator)입니다.
아래 생성된 문제를 읽고, 치명적인 논리적 오류가 없는지 평가하세요.

[검증 대상 문제]
{full_text}

[평가 기준]
1. 정답 일치: [정답] 란에 명시된 번호가 [정답 해설]의 논리와 완벽히 일치해야 합니다. (단, 해설에 정답 '번호'가 직접 명시되지 않았더라도, 내용상 정답을 정확히 서술하고 있다면 감점하지 마세요.)
2. 논리적 모순: 오답 번호를 정답이라고 잘못 설명하거나, 두 개 이상의 선지를 복수 정답처럼 모호하게 설명하는 치명적 오류가 없어야 합니다.

*주의사항*: AI가 문제를 창작하는 과정에서 사소한 어색함(양식 오류 등)이 있더라도, '치명적인 논리적 오류(정답 오류, 복수정답 등)'가 아니라면 반드시 passed를 true로 평가하세요. 너무 엄격한 잣대로 멀쩡한 문제를 폐기하지 마세요.
반드시 아래 JSON 형식으로만 출력하세요. 마크다운(` ```json `) 기호 없이 순수 JSON 텍스트만 출력하세요.

{{
  "passed": true,
  "feedback": "문제 없음"
}}
"""
    try:
        if is_google_native:
            val_response = client.generate_content(val_prompt)
            val_raw = val_response.text
        else:
            val_response = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": val_prompt}],
                temperature=0.0,
                max_tokens=200
            )
            val_raw = val_response.choices[0].message.content

        # 정규식을 이용해 JSON 중괄호 {...} 만 완벽하게 빼냅니다.
        json_match = re.search(r'\{.*\}', val_raw, re.DOTALL)
        if not json_match:
            return False, f"JSON 파싱 실패: {val_raw[:50]}..."
            
        val_clean = json_match.group(0)
        val_data = json.loads(val_clean)
        
        passed = val_data.get("passed", False)
        feedback = val_data.get("feedback", "사유 없음")
        
        return passed, feedback
        
    except Exception as e:
        return False, f"검증기 API 오류 발생: {str(e)}"
