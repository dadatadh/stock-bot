# 한국 주식 자동 분석 텔레그램 봇

## 기능
- 매시간 KOSPI/KOSDAQ 자동 분석 (평일 9~20시)
- 외인/기관 수급 분석 (15:30, 18:00)
- AI 기반 종목 질의응답 (Groq + Gemini)
- 종목 직접 분석 (현재가, 익절가, 손절가, 매수/매도 신호)

## 명령어
- /전체 - KOSPI+KOSDAQ 전체 분석
- /장기 - 장기투자 추천
- /수급 - 외인/기관 수급 분석
- /업종 반도체 - 업종별 분석
- /종목 005930 - 종목 직접 분석
- 자유 질문 가능 (AI 답변)

## 설치
1. .env 파일 생성 후 API 키 입력
2. pip install -r requirements.txt
3. python3 stock_bot.py

## 필요 API
- 텔레그램 봇 토큰
- 한국투자증권 KIS API
- Groq API
- Google Gemini API
