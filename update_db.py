"""
기출 문제 DB 업데이트 스크립트
엑셀 파일을 수정한 후 이 스크립트를 실행하면 questions_db.json이 갱신됩니다.

사용법:
    python update_db.py
"""
import pandas as pd
import json
from pathlib import Path

BASE = Path(__file__).parent
EXCEL_PATH = BASE / "past_questions_완성.xlsx"
JSON_PATH  = BASE / "questions_db.json"

def update():
    df = pd.read_excel(EXCEL_PATH, sheet_name="중2")
    df = df.fillna("")
    # 컬럼명 공백 제거
    df.columns = [c.strip() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        records.append({
            "u": str(row.get("대단원", "")).strip(),
            "s": str(row.get("소단원", "")).strip(),
            "t": str(row.get("문제유형", "")).strip(),
            "q": str(row.get("발문", "")).strip(),
            "c": str(row.get("보기/ 지문", "")).strip()[:300],
            "a": str(row.get("정답", "")).strip(),
            "e": str(row.get("해설", "")).strip()[:250],
        })

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"✅ DB 업데이트 완료: {len(records)}개 문제 → {JSON_PATH}")

if __name__ == "__main__":
    update()
