# prompts_e.py — E레벨(응용/완성형 지문 허용) 문항 생성 프롬프트
# 공통 페르소나/루브릭/규칙은 prompts_common.py에 있고, 여기서는
# E레벨 고유 규칙만 정의합니다. 반환값은 (system_prompt, user_prompt) 튜플입니다.

from prompts_common import (
    QUESTION_INSTRUCTIONS,
    build_system_prompt,
    build_user_prompt,
    build_retry_system_prompt,  # 🚀 누락되었던 재생성 system 함수 추가
    build_retry_user_prompt,    # 🚀 누락되었던 재생성 user 함수 추가
)

E_LEVEL_RULES = """\
- [지문 창작] 기출의 문장 뼈대는 모방하되, 주어/어휘/상황을 완전히 새로운 내용으로
  창작하세요.
- [지문 길이 및 난이도] E레벨 세트에서는 문항의 깊이를 더하기 위해 완성형 지문 생성이 허용됩니다.
  할당된 D조건(0~2점)에 맞추어 지문 유무와 길이를 조정하세요. 지문을 생성하는 문제(D=1, 2)의
  경우 각 문장은 Lexile 850L ~950L 범위에서 작성하되, 과도하게 길어지지 않도록 최대 5~7문장
  이내로 구성하세요.
- [선지 정렬] 선지 길이순 정렬은 시스템이 자동으로 처리하므로, 내용의 논리성에만
  집중하세요."""


def build_generation_prompt_e(
    ref_text, selected_major, selected_mid, selected_minor_label, point_text,
    qtype, num_for_this_type, extra, q_assignments, integration_rule,
):
    """E레벨 생성 프롬프트. (system_prompt, user_prompt) 튜플을 반환합니다."""
    system_prompt = build_system_prompt(level_rules=E_LEVEL_RULES, integration_rule=integration_rule)
    user_prompt = build_user_prompt(
        ref_text=ref_text, selected_major=selected_major, selected_mid=selected_mid,
        selected_minor_label=selected_minor_label, point_text=point_text, qtype=qtype,
        num_for_this_type=num_for_this_type, extra=extra, q_assignments=q_assignments,
    )
    return system_prompt, user_prompt


# 🚀 E레벨 전용 반려 문항 재생성 함수 추가
def build_retry_prompt(failed_items, point_text):
    """반려 문항 재생성 프롬프트. (system_prompt, user_prompt) 튜플을 반환합니다."""
    return build_retry_system_prompt(), build_retry_user_prompt(failed_items, point_text)
