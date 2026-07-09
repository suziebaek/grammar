from __future__ import annotations  # Python 3.9 호환: `int | None` 표기를 문자열로 지연 평가

# flag_checker.py
# ------------------------------------------------------------------
# 등급 경계값 / 신뢰도 경고 / 조합 이상 같은 플래그 판정은 A+B+C 합산,
# M(대분류 개수) 계산처럼 단순 산수인데도, 프롬프트 안에서는 LLM이
# 창작과 동시에 직접 계산하게 되어 있어 누락되기 쉬운 부분이었습니다.
#
# 이 모듈은 생성된 문항 텍스트의 [난이도 산출 내역] 줄을 파싱해서
# 규칙 기반으로 플래그를 다시 계산합니다. LLM이 [플래그 내역]에 쓴
# 내용은 "1차 판단"으로만 참고하고, 여기서 계산한 결과를 신뢰합니다.
#
# 사용 예 (app.py에서):
#   from flag_checker import verify_question_flags
#   result = verify_question_flags(question_text)
#   if result.mismatches:
#       # UI에 경고 표시 / 로그 기록 등
# ------------------------------------------------------------------

import re
from dataclasses import dataclass, field


META_PATTERN = re.compile(
    r"A=(?P<a>\d)점.*?"
    r"B=(?P<b>\d)점.*?"
    r"C=(?P<c>\d)점.*?"
    r"D=(?P<d>\d)점",
    re.DOTALL,
)

DB_UNREGISTERED_MARK = "DB 미등록"


@dataclass
class FlagResult:
    a: int | None = None
    b: int | None = None
    c: int | None = None
    d: int | None = None
    base_total: int | None = None  # A+B+C
    expected_flags: list = field(default_factory=list)
    llm_reported_flags: str = ""
    mismatches: list = field(default_factory=list)  # LLM이 놓친 플래그 목록


def _extract_meta_scores(question_text: str):
    match = META_PATTERN.search(question_text)
    if not match:
        return None
    return {k: int(v) for k, v in match.groupdict().items()}


def _extract_reported_flags(question_text: str) -> str:
    match = re.search(r"\[플래그 내역\]:?\s*(.+)", question_text)
    return match.group(1).strip() if match else ""


def compute_expected_flags(a: int, b: int, c: int, is_db_unregistered: bool = False) -> list[str]:
    """규칙 기반으로 플래그를 재계산합니다 (prompts_common.FLAG_RULES와 1:1 대응)."""
    flags = []
    total = a + b + c

    # 2) 등급 경계값
    if total in (2, 3, 6, 7):
        flags.append(f"등급 경계값 (총점={total})")

    # 3) 신뢰도 경고
    if a == 3 and is_db_unregistered:
        flags.append("신뢰도 경고 (A=3 + DB 미등록)")
    if b == 3:
        flags.append("신뢰도 경고 (B=3)")
    if c == 3:
        flags.append("신뢰도 경고 (C=3)")

    # 4) 조합 이상
    if a == 0 and total >= 5:
        flags.append(f"조합 이상 (A=0, 총점={total}≥5)")
    if a == 3 and total <= 4:
        flags.append(f"조합 이상 (A=3, 총점={total}≤4)")

    return flags


def verify_question_flags(question_text: str) -> FlagResult:
    """단일 문항 텍스트를 검증합니다. META 라인이 없으면 빈 결과를 반환합니다."""
    scores = _extract_meta_scores(question_text)
    if scores is None:
        return FlagResult()

    is_db_unregistered = DB_UNREGISTERED_MARK in question_text
    expected = compute_expected_flags(
        scores["a"], scores["b"], scores["c"], is_db_unregistered
    )
    reported = _extract_reported_flags(question_text)

    # LLM이 "특이사항 없음"이라고 했는데 코드 계산상 플래그가 있어야 하면 mismatch로 기록
    mismatches = []
    if expected and ("특이사항 없음" in reported or not reported):
        mismatches = expected

    return FlagResult(
        a=scores["a"], b=scores["b"], c=scores["c"], d=scores["d"],
        base_total=scores["a"] + scores["b"] + scores["c"],
        expected_flags=expected,
        llm_reported_flags=reported,
        mismatches=mismatches,
    )


def verify_all_questions(all_generated_dict: dict) -> dict:
    """{q_num: FlagResult} 형태로 전체 문항을 검증합니다. app.py의 검수 단계 뒤에 붙여 쓰세요."""
    return {q_num: verify_question_flags(text) for q_num, text in all_generated_dict.items()}
