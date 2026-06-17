"""
DB 업데이트 스크립트
엑셀 파일 수정 후 이 스크립트를 실행하면 JSON DB가 갱신됩니다.

사용법:
    python update_db.py
"""
import pandas as pd
import json
from pathlib import Path

BASE = Path(__file__).parent

def update_questions():
    """past_questions_완성.xlsx -> questions_db.json"""
    path = BASE / "past_questions_완성.xlsx"
    df = pd.read_excel(path, sheet_name="중2")
    df = df.fillna("")
    df.columns = [c.strip() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        records.append({
            "u": str(row.get("대단원", "")).strip(),
            "s": str(row.get("소단원", "")).strip(),
            "t": str(row.get("문제유형", "")).strip(),
            "q": str(row.get("발문", "")).strip(),
            "c": str(row.get("보기/ 지문", "")).strip(),
            "a": str(row.get("정답", "")).strip(),
            "e": str(row.get("해설", "")).strip(),
        })

    out = BASE / "questions_db.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    print(f"✅ 기출 DB 업데이트: {len(records)}문제 → {out}")


def update_concepts():
    """concept_list_difficulty.xlsx -> concept_hierarchy.json"""
    path = BASE / "concept_list_difficulty.xlsx"
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    df['문법항목(대)'] = df['문법항목(대)'].ffill()
    df['문법항목(중)'] = df['문법항목(중)'].ffill()

    hierarchy = {}
    for _, row in df.iterrows():
        major = str(row['문법항목(대)']).strip()
        mid   = str(row['문법항목(중)']).strip()
        minor = str(row['문법항목(소)']).strip() if pd.notna(row['문법항목(소)']) else ''
        diff  = str(row['난이도']).strip() if pd.notna(row['난이도']) else ''
        point = str(row['출제포인트']).strip() if pd.notna(row['출제포인트']) else ''

        if major == 'nan':
            continue
        if major not in hierarchy:
            hierarchy[major] = {}
        if mid not in hierarchy[major]:
            hierarchy[major][mid] = []
        hierarchy[major][mid].append({
            'minor': minor,
            'difficulty': diff,
            'point': point,   # 전체 저장
        })

    out = BASE / "concept_hierarchy.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)
    print(f"✅ 개념 계층 DB 업데이트: {len(hierarchy)}개 대분류 → {out}")


if __name__ == "__main__":
    update_questions()
    update_concepts()
    print("\n✅ 모든 DB 업데이트 완료!")
