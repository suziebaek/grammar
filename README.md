# 📝 영어 기출 문제 생성기

강남구 중학교 기출 154문제 데이터 기반 AI 응용 문제 자동 생성 서비스

---

## 📁 프로젝트 구조

```
english_question_generator/
├── app.py                  # Streamlit 메인 앱
├── questions_db.json       # 기출 문제 DB (154문제)
├── past_questions_완성.xlsx # 원본 엑셀 파일
├── requirements.txt        # 패키지 목록
└── README.md
```

---

## 🚀 로컬 실행 방법

### 1. Python 환경 준비
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 앱 실행
```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## ☁️ 배포 방법 (Streamlit Cloud — 무료)

### 1. GitHub 저장소 생성
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ID/english-question-generator.git
git push -u origin main
```

### 2. Streamlit Cloud 배포
1. https://share.streamlit.io 접속
2. GitHub 계정 연결
3. Repository 선택 → `app.py` 선택
4. **Secrets 설정** (선택):  
   Settings → Secrets에 아래 추가하면 API 키 자동 입력 가능
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy 클릭 → 공유 링크 자동 생성

> 💡 배포 후 링크 하나로 동료 누구나 접속 가능

---

## 🔑 Anthropic API 키 발급

1. https://console.anthropic.com 접속
2. 회원가입 → API Keys → Create Key
3. 앱 사이드바에 입력하거나 Streamlit Secrets에 등록

---

## 💰 비용 안내

- Streamlit Cloud 호스팅: **무료**
- Anthropic API: 문제 1세트(3문제) 생성 시 약 **0.03~0.05달러** (약 40~70원)
- 월 1,000회 생성 기준 약 **40,000~70,000원** 예상

---

## 🔄 기출 문제 DB 업데이트

엑셀 파일(`past_questions_완성.xlsx`)을 업데이트한 후 아래 스크립트 실행:

```python
python update_db.py
```

---

## 📌 주요 기능

| 기능 | 설명 |
|------|------|
| AI 문제 생성 | 문법 단원 + 문제 유형 선택 → 기출 스타일 문제 자동 생성 |
| 기출 탐색 | 154개 기출 문제 필터링/검색 |
| 생성 기록 | 이번 세션 생성 기록 저장 및 다운로드 |
| 다운로드 | 생성된 문제 .txt 파일로 저장 |
