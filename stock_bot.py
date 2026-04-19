import requests
import re
import json
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import threading
from groq import Groq
from google import genai

TELEGRAM_TOKEN = "8687415968:AAFtvdYKVgqWwmY0HNbc6_WCLpSfTHZ8uvU"
CHAT_ID = "8529427533"
KST = ZoneInfo("Asia/Seoul")

KIS_APP_KEY = "PSKNO82FXZvlQPvYxUCEJqskgun77KkEnBm1"
KIS_SECRET  = "rvSfXqgJOUdsUQHIrbU+Fug8jsyJgK7Q+IEgCBVrsVbed9e7npMYg46FDx7agDJakoIAozLwArVLz4mG8QHNs0RIZzpkVVhyqJxL71NWDxKEonWSrEyKnmWqyW4AzqEhd+wq4t0ks/oy1LIsF6SuvrkqsWUO2VUKav8DqQDpuUKUo9WZsx8="
KIS_ACCOUNT = "73921841"
KIS_BASE    = "https://openapi.koreainvestment.com:9443"
GROQ_API_KEY   = "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"
GEMINI_API_KEY = "AIzaSyCdFBCjUhipN9FS_4tixpuW3bedW-5Gqm4"

HELP_MSG = """🤖 주식 분석 봇 사용법

📊 분석 명령어
/전체 - KOSPI+KOSDAQ 전체 분석
/장기 - 장기투자 추천
/수급 - 외인/기관 수급 분석
/업종 반도체 - 업종별 분석

🔍 종목 직접 분석
/종목 005930
/종목 삼성전자

💬 자유 질문 (AI 답변)
삼성전자 매수해도 될까?
SK하이닉스 전망 알려줘

❓ /도움말 - 이 메시지 다시 보기
⏰ 매시간 자동 알림 (평일 9~20시)
💰 15:30, 18:00 수급 분석"""

_kis_token = None
_kis_token_expires = None
_analysis_cache = {}

def get_kis_token():
    global _kis_token, _kis_token_expires
    now = datetime.now(KST)
    if _kis_token and _kis_token_expires and now < _kis_token_expires:
        return _kis_token
    res = requests.post(f"{KIS_BASE}/oauth2/tokenP", json={
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_SECRET
    }).json()
    _kis_token = res.get("access_token")
    _kis_token_expires = now + timedelta(hours=23)
    return _kis_token

def kis_headers(tr_id):
    return {
        "authorization": f"Bearer {get_kis_token()}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_SECRET,
        "tr_id": tr_id,
    }

def get_current_price(ticker):
    try:
        res = requests.get(f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=kis_headers("FHKST01010100"),
            params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}).json()
        return int(res["output"]["stck_prpr"])
    except Exception:
        return None

def get_ohlcv(ticker, days=120):
    end = datetime.now(KST).strftime("%Y%m%d")
    start = (datetime.now(KST) - timedelta(days=days)).strftime("%Y%m%d")
    return stock.get_market_ohlcv_by_date(start, end, ticker)

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss))

def analyze(ticker):
    try:
        df = get_ohlcv(ticker)
        if len(df) < 20:
            return None
        close = df["종가"]
        last = df.iloc[-1]
        ma5  = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(df) >= 60 else None
        vol_ratio = df["거래량"].iloc[-1] / df["거래량"].iloc[-20:].mean()
        rsi = calc_rsi(close).iloc[-1]
        atr = (df["고가"] - df["저가"]).rolling(14).mean().iloc[-1]
        low_52w = close.min()
        high_52w = close.max()
        vol_trend = df["거래량"].iloc[-20:].mean() / df["거래량"].iloc[-40:-20].mean() if len(df) >= 40 else 1
        realtime = get_current_price(ticker)
        current = realtime if realtime else last["종가"]
        return {
            "ticker": ticker,
            "name": stock.get_market_ticker_name(ticker),
            "current": current,
            "ma5": ma5, "ma20": ma20, "ma60": ma60,
            "vol_ratio": vol_ratio, "rsi": rsi,
            "high_52w": high_52w, "low_52w": low_52w,
            "atr": atr, "vol_trend": vol_trend,
        }
    except Exception:
        return None

def classify(info, market="KOSPI"):
    if not info:
        return None, None, None
    p, atr = info["current"], info["atr"]
    ma20_gap = (p - info["ma20"]) / info["ma20"] * 100 if info["ma20"] else 999
    vol_min = 1.0 if market == "KOSDAQ" else 0.5
    vol_max = 4.0 if market == "KOSDAQ" else 3.0
    momentum_vol = 2.0 if market == "KOSDAQ" else 1.5
    is_safe = (
        info["ma5"] > info["ma20"] and
        (info["ma60"] is not None and p > info["ma60"]) and
        35 <= info["rsi"] <= 60 and
        vol_min <= info["vol_ratio"] <= vol_max and
        0 <= ma20_gap <= 3.0
    )
    is_momentum = (
        info["vol_ratio"] >= momentum_vol and
        info["rsi"] >= 50 and
        info["current"] >= info["high_52w"] * 0.85 and
        info["ma5"] > info["ma20"]
    )
    is_longterm = (
        info["ma60"] is not None and p > info["ma60"] and
        40 <= info["rsi"] <= 55 and
        info["vol_trend"] >= 1.1 and
        p >= info["low_52w"] * 1.2 and
        info["ma5"] > info["ma20"]
    )
    if is_safe:
        return "safe", round(p + atr * 2), round(p - atr * 1)
    if is_momentum:
        return "momentum", round(p + atr * 3), round(p - atr * 1.5)
    if is_longterm:
        return "longterm", round(p * 1.15), round(p * 0.93)
    return None, None, None

def extract_ticker(text):
    codes = re.findall(r'\b\d{6}\b', text)
    if codes:
        return codes[0]
    now = datetime.now(KST)
    days_back = 3 if now.weekday() in [5, 6] else 1
    search_date = (now - timedelta(days=days_back)).strftime("%Y%m%d")
    for market in ["KOSPI", "KOSDAQ"]:
        for t in stock.get_market_ticker_list(search_date, market=market):
            name = stock.get_market_ticker_name(t)
            if name in text or text in name:
                return t
    return None

def get_investor_data(ticker):
    try:
        res = requests.get(f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-investor",
            headers=kis_headers("FHKST01010900"),
            params={
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": ticker,
                "fid_begin_date": (datetime.now(KST) - timedelta(days=7)).strftime("%Y%m%d"),
                "fid_end_date": datetime.now(KST).strftime("%Y%m%d"),
            }).json()
        output = res.get("output", [])
        if not output:
            return None
        foreign_days = [int(x.get("frgn_ntby_qty", 0)) for x in output[:5]]
        organ_days   = [int(x.get("orgn_ntby_qty", 0)) for x in output[:5]]
        return {
            "foreign_today": foreign_days[0],
            "foreign_2d": foreign_days[1] if len(foreign_days) > 1 else 0,
            "foreign_3d": foreign_days[2] if len(foreign_days) > 2 else 0,
            "organ_today": organ_days[0],
            "organ_2d": organ_days[1] if len(organ_days) > 1 else 0,
            "organ_3d": organ_days[2] if len(organ_days) > 2 else 0,
            "foreign_consecutive": sum(1 for x in foreign_days if x > 0),
            "organ_consecutive": sum(1 for x in organ_days if x > 0),
            "both_buy_today": foreign_days[0] > 0 and organ_days[0] > 0,
        }
    except Exception:
        return None

def get_float_shares(ticker):
    try:
        res = requests.get(f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/search-stock-info",
            headers=kis_headers("CTPF1002R"),
            params={"PDNO": ticker, "PRDT_TYPE_CD": "300"}).json()
        return int(res["output"].get("lstg_stqt", 1))
    except Exception:
        return 1

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def chat_with_ai(user_msg):
    groq_client = Groq(api_key=GROQ_API_KEY)
    try:
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "system",
                "content": '한국 주식 질문 분류기. JSON만 반환: {"intent":"deep_analysis|simple_query|general","ticker":"종목코드or null","name":"종목명or null"}'
            }, {"role": "user", "content": user_msg}],
            temperature=0, max_tokens=100
        )
        text = re.sub(r'```json|```', '', res.choices[0].message.content).strip()
        intent_data = json.loads(text)
    except Exception:
        intent_data = {"intent": "general", "ticker": None, "name": None}

    intent = intent_data.get("intent", "general")
    ticker = intent_data.get("ticker") or extract_ticker(user_msg)
    context = ""
    if ticker:
        now_ts = datetime.now(KST).timestamp()
        if ticker in _analysis_cache:
            cached_time, cached_ctx = _analysis_cache[ticker]
            if now_ts - cached_time < 300:
                context = cached_ctx
        if not context:
            info = analyze(ticker)
            if info:
                category, target, stop = classify(info)
                if not target:
                    target = round(info["current"] + info["atr"] * 2)
                    stop = round(info["current"] - info["atr"])
                inv = get_investor_data(ticker)
                supply = ""
                if inv:
                    supply = f" 외인{inv['foreign_consecutive']}일{'매수' if inv['foreign_today']>0 else '매도'}/기관{inv['organ_consecutive']}일{'매수' if inv['organ_today']>0 else '매도'}"
                context = f"종목:{info['name']}({ticker}) 현재가:{info['current']:,}원 목표가:{target:,}원 손절가:{stop:,}원 RSI:{info['rsi']:.1f} 거래량:{info['vol_ratio']:.1f}배 MA5:{info['ma5']:,.0f} MA20:{info['ma20']:,.0f}{supply}"
                _analysis_cache[ticker] = (now_ts, context)

    if intent in ("general", "simple_query"):
        try:
            res = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{
                    "role": "system",
                    "content": f"한국 주식 전문 AI. 날짜:{datetime.now(KST).strftime('%Y-%m-%d')}. {f'데이터:{context}' if context else ''} 투자는 본인 책임임을 명시하세요."
                }, {"role": "user", "content": user_msg}],
                temperature=0.7, max_tokens=500
            )
            return res.choices[0].message.content
        except Exception as e:
            return f"응답 오류: {e}"
    else:
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"한국 주식 전문 AI. 날짜:{datetime.now(KST).strftime('%Y-%m-%d')} 데이터:{context} 질문:{user_msg} 상세분석/목표가/손절가/추천의견 제공. 투자는 본인 책임."
            response = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return response.text
        except Exception:
            try:
                res = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": f"한국 주식 전문 AI. 날짜:{datetime.now(KST).strftime('%Y-%m-%d')}. 데이터:{context}. 투자는 본인 책임."}, {"role": "user", "content": user_msg}],
                    temperature=0.7, max_tokens=800
                )
                return res.choices[0].message.content
            except Exception as e:
                return f"응답 오류: {e}"

def format_result(title, safe_list, momentum_list, longterm_list=None):
    lines = [f"📊 {title}\n", "🛡 안전 추천 종목"]
    if safe_list:
        for s in safe_list:
            lines += [f"• {s['name']}({s['ticker']})",
                      f"  현재가: {s['current']:,}원",
                      f"  익절목표: {s['target']:,}원 (+{s['upside']:.1f}%)",
                      f"  손절가격: {s['stop']:,}원 (-{s['downside']:.1f}%)",
                      f"  추천이유: RSI {s['rsi']:.0f}, 이평선 정배열", ""]
    else:
        lines.append("  해당 종목 없음")
    lines += ["\n🚀 상승 추천 종목"]
    if momentum_list:
        for s in momentum_list:
            lines += [f"• {s['name']}({s['ticker']})",
                      f"  현재가: {s['current']:,}원",
                      f"  익절목표: {s['target']:,}원 (+{s['upside']:.1f}%)",
                      f"  손절가격: {s['stop']:,}원 (-{s['downside']:.1f}%)",
                      f"  추천이유: 거래량 {s['vol_ratio']:.1f}배 급증, 고가 근접", ""]
    else:
        lines.append("  해당 종목 없음")
    if longterm_list is not None:
        lines += ["\n📈 장기투자 추천 종목"]
        if longterm_list:
            for s in longterm_list:
                lines += [f"• {s['name']}({s['ticker']})",
                          f"  현재가: {s['current']:,}원",
                          f"  목표가: {s['target']:,}원 (+15%)",
                          f"  손절가격: {s['stop']:,}원 (-7%)",
                          f"  추천이유: 거래량 증가추세, 60일선 위 안정", ""]
        else:
            lines.append("  해당 종목 없음")
    return "\n".join(lines)

def _collect(tickers, market="KOSPI"):
    safe_list, momentum_list, longterm_list = [], [], []
    for ticker in tickers:
        info = analyze(ticker)
        category, target, stop = classify(info, market)
        if category:
            entry = {**info, "target": target, "stop": stop,
                     "upside": (target - info["current"]) / info["current"] * 100,
                     "downside": (info["current"] - stop) / info["current"] * 100}
            if category == "safe": safe_list.append(entry)
            elif category == "momentum": momentum_list.append(entry)
            else: longterm_list.append(entry)
    return (
        sorted(safe_list, key=lambda x: abs(x["rsi"] - 50))[:3],
        sorted(momentum_list, key=lambda x: x["vol_ratio"], reverse=True)[:3],
        sorted(longterm_list, key=lambda x: x["vol_trend"], reverse=True)[:3],
    )

def run_all():
    today = datetime.now(KST).strftime("%Y%m%d")
    kospi = stock.get_market_ticker_list(today, market="KOSPI")
    kosdaq = stock.get_market_ticker_list(today, market="KOSDAQ")
    safe_k, mom_k, long_k = _collect(kospi[:300], "KOSPI")
    safe_q, mom_q, long_q = _collect(kosdaq[:100], "KOSDAQ")
    safe_list = (safe_k + safe_q)[:3]
    momentum_list = (mom_k + mom_q)[:3]
    longterm_list = (long_k + long_q)[:3]
    msg = format_result(f"한국주식 분석 [{datetime.now(KST).strftime('%m/%d %H:%M')}]",
                        safe_list, momentum_list, longterm_list)
    send_telegram(msg)

def run_longterm():
    today = datetime.now(KST).strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market="KOSPI")
    _, _, longterm_list = _collect(tickers[:300])
    lines = [f"📈 장기투자 추천 [{datetime.now(KST).strftime('%m/%d %H:%M')}]\n"]
    if longterm_list:
        for s in longterm_list:
            lines += [f"• {s['name']}({s['ticker']})",
                      f"  현재가: {s['current']:,}원",
                      f"  목표가: {s['target']:,}원 (+15%)",
                      f"  손절가격: {s['stop']:,}원 (-7%)",
                      f"  추천이유: 거래량 증가추세, 60일선 위 안정", ""]
    else:
        lines.append("  해당 종목 없음")
    send_telegram("\n".join(lines))

def analyze_sector(keyword):
    today = datetime.now(KST).strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market="KOSPI")
    matched = [t for t in tickers if keyword in stock.get_market_ticker_name(t)][:30]
    if not matched:
        send_telegram(f"'{keyword}' 업종 종목을 찾을 수 없어요.\n\n" + HELP_MSG)
        return
    safe_list, momentum_list, longterm_list = _collect(matched)
    msg = format_result(f"{keyword} 업종 분석", safe_list, momentum_list, longterm_list)
    send_telegram(msg)

def analyze_single(query):
    ticker = None
    if query.isdigit() and len(query) == 6:
        ticker = query
    else:
        now = datetime.now(KST)
        days_back = 3 if now.weekday() in [5, 6] else 1
        search_date = (now - timedelta(days=days_back)).strftime("%Y%m%d")
        for market in ["KOSPI", "KOSDAQ"]:
            for t in stock.get_market_ticker_list(search_date, market=market):
                name = stock.get_market_ticker_name(t)
                if query in name or name in query:
                    ticker = t
                    break
            if ticker: break
    if not ticker:
        send_telegram(f"'{query}' 종목을 찾을 수 없어요.")
        return
    info = analyze(ticker)
    if not info:
        send_telegram(f"'{query}' 데이터를 가져올 수 없어요.")
        return
    p, atr = info["current"], info["atr"]
    category, target, stop = classify(info)
    if info["rsi"] > 70: signal = "🔴 매도 추천 (RSI 과매수)"
    elif info["rsi"] < 30: signal = "🟢 매수 추천 (RSI 과매도)"
    elif category in ("safe", "momentum", "longterm"): signal = "🟢 매수 추천"
    elif info["ma5"] < info["ma20"]: signal = "🔴 매도 추천 (이평선 역배열)"
    else: signal = "🟡 중립 (관망)"
    
    if not target:
        target = round(p + atr * 2)
        stop = round(p - atr * 1)
    upside = (target - p) / p * 100
    downside = (p - stop) / p * 100
    inv = get_investor_data(ticker)
    supply_lines = ""
    if inv:
        float_shares = get_float_shares(ticker)
        f_3d = inv["foreign_today"] + inv.get("foreign_2d", 0) + inv.get("foreign_3d", 0)
        o_3d = inv["organ_today"] + inv.get("organ_2d", 0) + inv.get("organ_3d", 0)
        f_ratio = abs(f_3d) / float_shares * 100 if float_shares else 0
        o_ratio = abs(o_3d) / float_shares * 100 if float_shares else 0
        f_sig = f"매수 ({f_3d:,}주, {f_ratio:.3f}%)" if f_3d > 0 else f"매도 ({abs(f_3d):,}주, {f_ratio:.3f}%)"
        o_sig = f"매수 ({o_3d:,}주, {o_ratio:.3f}%)" if o_3d > 0 else f"매도 ({abs(o_3d):,}주, {o_ratio:.3f}%)"
        supply_lines = f"\n\n💰 외인/기관 수급 (최근 3일)\n외인: {f_sig}\n기관: {o_sig}"
    
    msg = f"🔍 {info['name']}({ticker}) 분석\n\n현재가: {p:,}원\n신호: {signal}\n\n익절목표: {target:,}원 (+{upside:.1f}%)\n손절가격: {stop:,}원 (-{downside:.1f}%)\n\nRSI: {info['rsi']:.1f}\n거래량: {info['vol_ratio']:.1f}배\n52주 고가: {info['high_52w']:,}원\n52주 저가: {info['low_52w']:,}원{supply_lines}"
    send_telegram(msg)

def get_investor_supply_analysis():
    today = datetime.now(KST).strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market="KOSPI")
    double_buy, consecutive = [], []
    for ticker in tickers[:200]:
        try:
            inv = get_investor_data(ticker)
            if not inv: continue
            float_shares = get_float_shares(ticker)
            f_3d = inv["foreign_today"] + inv.get("foreign_2d", 0) + inv.get("foreign_3d", 0)
            o_3d = inv["organ_today"] + inv.get("organ_2d", 0) + inv.get("organ_3d", 0)
            f_ratio = abs(f_3d) / float_shares * 100 if float_shares else 0
            o_ratio = abs(o_3d) / float_shares * 100 if float_shares else 0
            name = stock.get_market_ticker_name(ticker)
            price = get_current_price(ticker) or 0
            if inv["both_buy_today"] and (f_ratio + o_ratio) > 0.1:
                double_buy.append({"name": name, "ticker": ticker, "price": price, "total_ratio": f_ratio + o_ratio, "f_ratio": f_ratio, "o_ratio": o_ratio})
            if inv["foreign_consecutive"] >= 3 or inv["organ_consecutive"] >= 3:
                consecutive.append({"name": name, "ticker": ticker, "price": price, "f_days": inv["foreign_consecutive"], "o_days": inv["organ_consecutive"]})
        except: continue
    
    double_buy = sorted(double_buy, key=lambda x: x["total_ratio"], reverse=True)[:5]
    consecutive = sorted(consecutive, key=lambda x: max(x["f_days"], x["o_days"]), reverse=True)[:5]
    lines = [f"💰 외인/기관 수급 분석 [{datetime.now(KST).strftime('%m/%d %H:%M')}]\n", "🤝 쌍끌이 매수 종목"]
    for s in double_buy: lines.append(f"• {s['name']}({s['ticker']}) {s['price']:,}원 (+{s['f_ratio']:.2f}% / +{s['o_ratio']:.2f}%)")
    lines.append("\n📅 연속 매수 종목 (3일+)")
    for s in consecutive: lines.append(f"• {s['name']}({s['ticker']}) {s['price']:,}원 (외인{s['f_days']}일 / 기관{s['o_days']}일)")
    send_telegram("\n".join(lines))

def handle_commands():
    offset = 0
    send_telegram("✅ 봇 시작!\n\n" + HELP_MSG)
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30"
            res = requests.get(url).json()
            for update in res.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {}).get("text", "")
                if not msg: continue
                if not msg.startswith("/"):
                    send_telegram(chat_with_ai(msg))
                    continue
                parts = msg[1:].split(" ", 1)
                cmd = parts[0]
                arg = parts[1] if len(parts) > 1 else ""
                if cmd in ("도움말", "help"): send_telegram(HELP_MSG)
                elif cmd == "전체": run_all()
                elif cmd == "장기": run_longterm()
                elif cmd == "수급": get_investor_supply_analysis()
                elif cmd == "종목" and arg: analyze_single(arg.strip())
                elif cmd == "업종" and arg: analyze_sector(arg.strip())
        except Exception as e: print(f"오류: {e}")
        time.sleep(1)

def auto_analysis():
    while True:
        now = datetime.now(KST)
        if now.weekday() < 5 and 9 <= now.hour <= 20:
            if now.minute == 0: run_all()
            if (now.hour == 15 and now.minute == 30) or (now.hour == 18 and now.minute == 0):
                get_investor_supply_analysis()
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=auto_analysis, daemon=True).start()
    handle_commands()
STOSKEOF
