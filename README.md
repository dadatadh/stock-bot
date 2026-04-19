cat > ~/README.md << 'READMEEOF'
  # 📈 한국 주식 자동 분석 텔레그램 봇

  ![Python](https://img.shields.io/badge/Python-3.12-blue)
  ![AWS EC2](https://img.shields.io/badge/AWS-EC2-orange)
  ![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)
  ![Groq](https://img.shields.io/badge/AI-Groq%20%2B%20Gemini-green)

  > KOSPI/KOSDAQ 전 종목을 매시간 자동 분석하고, AI 기반 종목 질의응답을 제공하는 텔레그램 봇

  ---

  ## 🏗 아키텍처

  텔레그램 메시지
      ↓
  [Stage 1] Groq LLaMA - 인텐트 분류 (단순조회 / 심층분석)
      ↓
  [Stage 2] Python - 실시간 데이터 수집
      ├── 한국투자증권 KIS API: 실시간 현재가
      ├── pykrx: RSI, 이동평균선, ATR, 거래량 (직접 계산)
      └── 외인/기관 수급 데이터
      ↓
  [Stage 3] Gemini 2.5 Flash (심층분석) / Groq (단순조회)
      ↓
  텔레그램 답변 전송

  ---

  ## ✨ 주요 기능

  ### 자동 분석
  - ⏰ 매시간 KOSPI+KOSDAQ 자동 분석 (평일 9~20시)
  - 💰 15:30, 18:00 외인/기관 수급 분석 자동 발송
  - 📊 안전 종목 / 상승 종목 / 장기투자 종목 3가지 분류

  ### 종목 분석
  - 현재가, 익절목표가, 손절가 자동 계산 (ATR 기반)
  - RSI, 이동평균선(5/20/60일), 거래량 분석
  - 외인/기관 3일 누적 수급 + 유통주식수 대비 비중

  ### 수급 분석
  - 쌍끌이 매수 종목 감지 (외인+기관 동시 매수)
  - 연속 매수 종목 추적 (3일 이상)

  ### AI 질의응답
  - 자연어로 종목 질문 가능
  - Groq (단순조회) + Gemini (심층분석) 하이브리드
  - 5분 캐싱으로 API 한도 절약

  ---

  ## 🛠 기술 스택

  | 분류 | 기술 |
  |------|------|
  | 서버 | AWS EC2 (Ubuntu 24.04) |
  | 언어 | Python 3.12 |
  | 주식 데이터 | 한국투자증권 KIS API, pykrx |
  | AI | Groq (LLaMA 3.3 70B), Google Gemini 2.5 Flash |
  | 알림 | Telegram Bot API |
  | 분석 지표 | RSI, MA5/20/60, ATR, 거래량, 외인/기관 수급 |

  ---

  ## 📱 텔레그램 명령어

  | 명령어 | 설명 |
  |--------|------|
  | `/전체` | KOSPI+KOSDAQ 전체 분석 |
  | `/장기` | 장기투자 추천 종목 |
  | `/수급` | 외인/기관 수급 분석 |
  | `/업종 반도체` | 업종별 분석 |
  | `/종목 005930` | 종목 코드로 직접 분석 |
  | `/종목 삼성전자` | 종목명으로 직접 분석 |
  | 자유 질문 | AI가 실시간 데이터 기반으로 답변 |

  ---

  ## ⚙️ 설치 방법

  1. 레포지토리 클론
  ```bash
  git clone https://github.com/dadatadh/stock-bot.git
  cd stock-bot

  2. 패키지 설치

  pip install -r requirements.txt

  3. .env 파일 생성

  TELEGRAM_TOKEN=your_token
  CHAT_ID=your_chat_id
  KIS_APP_KEY=your_kis_app_key
  KIS_SECRET=your_kis_secret
  KIS_ACCOUNT=your_account
  GROQ_API_KEY=your_groq_key
  GEMINI_API_KEY=your_gemini_key

  4. 실행

  python3 stock_bot.py

  ──────────────────────────────────────────────────────────────────────────────────────────────────────

  📋 필요 API

  - 텔레그램 BotFather (https://t.me/BotFather)
  - 한국투자증권 KIS Developers (https://apiportal.koreainvestment.com)
  - Groq Console (https://console.groq.com)
  - Google AI Studio (https://aistudio.google.com)

  ──────────────────────────────────────────────────────────────────────────────────────────────────────

  │ ⚠️ 본 봇은 투자 참고용이며, 모든 투자 결정과 손실은 본인 책임입니다.
