# prompts.py — H레벨(고난도/무지문) 문항 생성 프롬프트
# 공통 페르소나/루브릭/규칙은 prompts_common.py에 있고, 여기서는
# H레벨 고유 규칙만 정의합니다. 반환값은 (system_prompt, user_prompt) 튜플입니다.

from prompts_common import (
    QUESTION_INSTRUCTIONS,
    build_system_prompt,
    build_user_prompt,
    build_retry_system_prompt,
    build_retry_user_prompt,
)

H_LEVEL_RULES = """\
- [지문 길이 및 난이도] H레벨 세트에서는 완성형 지문 생성을 엄격히 금지하며, 반드시 무지문
  또는 단문 형태(D=0점) 규칙을 준수해야 합니다.
- [지문 길이 세부규칙] 문제 구성 시 각 문장(혹은 보기 선지)은 Lexile 850L 이하, Longman
  High Beginning~Low Intermediate, K-5 어휘 수준에 12단어 이내 길이로 짧고 명확하게
  생성하세요. 할당받은 '문법 개념 표현'을 위해서만 부분적으로 850L 이상의 문장을 허용합니다."""


def build_generation_prompt(
    ref_text, selected_major, selected_mid, selected_minor_label, point_text,
    qtype, num_for_this_type, extra, q_assignments, integration_rule,
):
    """H레벨 생성 프롬프트. (system_prompt, user_prompt) 튜플을 반환합니다."""
    system_prompt = build_system_prompt(level_rules=H_LEVEL_RULES, integration_rule=integration_rule)
    user_prompt = build_user_prompt(
        ref_text=ref_text, selected_major=selected_major, selected_mid=selected_mid,
        selected_minor_label=selected_minor_label, point_text=point_text, qtype=qtype,
        num_for_this_type=num_for_this_type, extra=extra, q_assignments=q_assignments,
    )
    return system_prompt, user_prompt


def build_retry_prompt(failed_items, point_text):
    """반려 문항 재생성 프롬프트. (system_prompt, user_prompt) 튜플을 반환합니다."""
    return build_retry_system_prompt(), build_retry_user_prompt(failed_items, point_text)
