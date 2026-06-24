import json
import re

# 🚀 [수정] 파라미터 맨 끝에 use_llm=True 를 추가합니다.
def validate_question_llm(full_text, client, is_google_native, target_model, use_llm=True):
    """
    LLM을 이용해 생성된 문법 문제의 논리적 모순을 검증합니다.
    반환값: (is_valid: bool, feedback: str)
    """
    # ── 1단계: 파이썬 기반 하드 룰 검증 (형식 및 비용 절감) ──
    tags = ["①", "②", "③", "④", "⑤"]
    if not all(t in full_text for t in tags):
        return False, "5지선다 형식이 불완전합니다 (①~⑤ 누락)."
        
    ans_section = re.search(r'\[정답\](.*?)(?=\n\s*\[해설\]|\Z)', full_text, re.DOTALL)
    if not ans_section:
        return False, "[정답] 섹션을 찾을 수 없습니다."
        
    if "[정답 해설]" not in full_text or "[오답 분석]" not in full_text:
        return False, "해설 양식([정답 해설], [오답 분석])이 누락되었습니다."

    # 🚀 [추가] 토글이 꺼져있으면 여기서 즉시 합격 처리하고 LLM 호출 생략!
    if not use_llm:
        return True, "하드 룰 통과 (LLM 검증 생략)"


    # ── 2단계: LLM 기반 정밀 논리 검증 (LLM-as-a-Judge) ──
    val_prompt = f"""당신은 대한민국 최고 수준의 문법 문제 검수자(Validator)입니다.
아래 생성된 문제를 읽고, 논리적 오류가 없는지 엄격하게 평가하세요.

[검증 대상 문제]
{full_text}

[평가 기준]
1. 정답 일치: [정답] 란에 명시된 번호와 [해설]의 '정답 해설'에서 설명하는 정답 번호가 정확히 일치해야 합니다.
2. 논리적 모순: 오답 번호를 정답이라고 설명하거나, 두 개 이상의 선지를 복수 정답처럼 설명하는 치명적 오류가 없어야 합니다.
3. 무결성: 해설 내용이 문법적 팩트와 일치하며 문맥상 모순이 없어야 합니다.

위 기준을 모두 통과하면 passed를 true로, 하나라도 어긋나면 false로 설정하고 구체적인 feedback을 작성하세요.
반드시 아래 JSON 형식으로만 출력하세요. 마크다운(` ```json `) 기호 없이 순수 JSON 텍스트만 출력하세요.

{{
  "passed": true,
  "feedback": "문제 없음"
}}
"""
    try:
        if is_google_native:
            # Gemini 모드
            val_response = client.generate_content(val_prompt)
            val_raw = val_response.text
        else:
            # OpenAI / Azure / OpenRouter 모드
            val_response = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": val_prompt}],
                temperature=0.0,  # 검증은 창의성이 필요 없으므로 0.0 설정
                max_tokens=200    # 짧은 JSON만 받으므로 토큰 비용 최소화
            )
            val_raw = val_response.choices[0].message.content

        # 마크다운 태그 제거 및 JSON 파싱
        val_clean = val_raw.strip().strip("`").removeprefix("json").strip()
        val_data = json.loads(val_clean)
        
        passed = val_data.get("passed", False)
        feedback = val_data.get("feedback", "사유 없음")
        
        return passed, feedback
        
    except Exception as e:
        return False, f"검증기 API 통신 오류: {str(e)}"
