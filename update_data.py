import os
import time
import json
import requests
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import yfinance as yf

# 忽略 SSL 憑證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# 1. 定義資產與顯示順序
yf_assets = {
    "全球指數": {
        "標普 500": "^GSPC", 
        "道瓊工業": "^DJI", 
        "納斯達克": "^IXIC", 
        "費城半導體": "^SOX", 
        "日經 225": "^N225", 
        "韓國 KOSPI": "^KS11",
        "英國富時 100": "^FTSE",
        "德國 DAX": "^GDAXI",
        "法國 CAC 40": "^FCHI"
    },
    "台股市場": {
        "台股加權指數": "^TWII"
    },
    "台股權值股": {
        "台積電 (2330)": "2330.TW",
        "聯發科 (2454)": "2454.TW",
        "台達電 (2308)": "2308.TW",
        "鴻海 (2317)": "2317.TW",
        "日月光投控 (3711)": "3711.TW"
    },
    "美股科技股": {
        "輝達 (NVDA)": "NVDA", 
        "台積電 ADR (TSM)": "TSM", 
        "博通 (AVGO)": "AVGO",
        "超微 (AMD)": "AMD",
        "蘋果 (AAPL)": "AAPL",
        "微軟 (MSFT)": "MSFT",
        "Google (GOOGL)": "GOOGL",
        "亞馬遜 (AMZN)": "AMZN",
        "Meta (META)": "META",
        "特斯拉 (TSLA)": "TSLA"
    },
    "外匯市場": {
        "USD/TWD": "USDTWD=X", 
        "美元指數 (DXY)": "DX-Y.NYB", 
        "人民幣 (USD/CNY)": "USDCNY=X", 
        "歐元 (EUR/USD)": "EURUSD=X", 
        "日圓 (USD/JPY)": "USDJPY=X", 
        "英鎊 (GBP/USD)": "GBPUSD=X"
    },
    "美債殖利率": {
        "10年期": "^TNX", 
        "30年期": "^TYX"
    },
    "原物料": {
        "黃金": "GC=F", 
        "白銀": "SI=F", 
        "銅": "HG=F", 
        "鈀金": "PA=F",
        "布蘭特原油": "BZ=F", 
        "WTI原油": "CL=F",
        "黃豆期貨": "ZS=F",
        "小麥期貨": "ZW=F",
        "玉米期貨": "ZC=F"
    }
}

# 2. 預先抓取基準大盤指數（納斯達克、台股加權）近一年收盤價，供個股對比使用
benchmarks = {}
for b_key, b_ticker in [("US", "^IXIC"), ("TW", "^TWII")]:
    try:
        b_hist = yf.Ticker(b_ticker).history(period="1y").dropna(subset=['Close'])
        b_hist.index = b_hist.index.strftime('%Y-%m-%d')
        benchmarks[b_key] = b_hist['Close']
    except Exception as e:
        print(f"Benchmark {b_ticker} error: {e}")

# 輔助函式：格式化大額財務數字
def fmt_large_num(val, is_tw=False):
    if val is None or val != val:
        return None
    val = float(val)
    if is_tw:
        return f"NT$ {val / 1e8:,.2f} 億"
    else:
        if abs(val) >= 1e9:
            return f"$ {val / 1e9:,.2f} B"
        elif abs(val) >= 1e6:
            return f"$ {val / 1e6:,.2f} M"
        return f"$ {val:,.0f}"

# 輔助函式：從 yfinance 擷取最新一季財報與關鍵指標
def get_stock_financials(tk, ticker):
    is_tw = ".TW" in ticker
    fin_data = {
        "period": "最新季度",
        "revenue": "無資料",
        "net_income": "無資料",
        "eps": "無資料",
        "gross_margin": "無資料",
        "operating_margin": "無資料",
        "pe_ratio": "無資料",
        "yoy_growth": "無資料"
    }
    try:
        info = tk.info or {}
        if info.get("trailingEps") is not None:
            fin_data["eps"] = f"{info.get('trailingEps'):.2f}"
        if info.get("grossMargins") is not None:
            fin_data["gross_margin"] = f"{info.get('grossMargins') * 100:.2f}%"
        if info.get("operatingMargins") is not None:
            fin_data["operating_margin"] = f"{info.get('operatingMargins') * 100:.2f}%"
        if info.get("trailingPE") is not None:
            fin_data["pe_ratio"] = f"{info.get('trailingPE'):.2f}x"
        if info.get("revenueGrowth") is not None:
            fin_data["yoy_growth"] = f"{info.get('revenueGrowth') * 100:+.2f}%"

        q_inc = tk.quarterly_income_stmt
        if q_inc is not None and not q_inc.empty:
            latest_col = q_inc.columns[0]
            fin_data["period"] = str(latest_col)[:10]
            
            for rev_key in ['Total Revenue', 'Operating Revenue']:
                if rev_key in q_inc.index:
                    rev_str = fmt_large_num(q_inc.loc[rev_key, latest_col], is_tw)
                    if rev_str: fin_data["revenue"] = rev_str
                    break
                    
            for ni_key in ['Net Income', 'Net Income Common Stockholders']:
                if ni_key in q_inc.index:
                    ni_str = fmt_large_num(q_inc.loc[ni_key, latest_col], is_tw)
                    if ni_str: fin_data["net_income"] = ni_str
                    break
                    
            for eps_key in ['Diluted EPS', 'Basic EPS']:
                if eps_key in q_inc.index:
                    val = q_inc.loc[eps_key, latest_col]
                    if val is not None and val == val:
                        fin_data["eps"] = f"{float(val):.2f} (單季)"
                    break
    except Exception as e:
        print(f"Financial extraction error for {ticker}: {e}")
    return fin_data

# 輔助函式：抓取 Google News RSS 近期新聞標題（作為基礎資訊與備援）
def fetch_rss_news(name, ticker):
    clean_name = name.split('(')[0].strip()
    query = f"{clean_name} OR {ticker.replace('.TW', '')}"
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headlines = []
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall('.//item')[:5]:
                title = item.find('title').text if item.find('title') is not None else ''
                pub_date = item.find('pubDate').text[:16] if item.find('pubDate') is not None else ''
                if title:
                    headlines.append({"title": title, "date": pub_date})
    except Exception:
        pass
    return headlines

# 輔助函式：呼叫 Gemini 2.5 Flash + Google Search 聯網整理利多利空、財報與公開說明
def generate_market_intelligence(name, ticker, category, price_str, pct, fin_data, headlines):
    is_stock = category in ["台股權值股", "美股科技股"]
    news_context = "\n".join([f"- {h['title']} ({h['date']})" for h in headlines]) if headlines else "無近期RSS標題"
    
    if GEMINI_API_KEY:
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            if is_stock:
                prompt = f"""你是一位頂尖買方機構產業研究員。請透過 Google 搜尋針對「{name} ({ticker})」（最新報價 {price_str}，單日漲跌幅 {pct:+.2f}%）進行最新基本面與催化劑整理。
系統抓取之基礎財報數據：{json.dumps(fin_data, ensure_ascii=False)}
近期新聞參考：
{news_context}

請嚴格以 JSON 格式回傳以下 4 個欄位（繁體中文，務必具體、量化、不講空話）：
{{
  "bull_factors": ["近期具體利多或上漲催化劑1", "具體利多2"],
  "bear_factors": ["近期具體利空、風險或下跌壓力1", "具體利空2"],
  "earnings_note": "最新一季財報表現與法說會重點（若近期開財報請列出營收/EPS/毛利率亮點與下季Guidance展望；若無則總結最近一期財報表現，約60-100字）",
  "announcements": "公司近期發布之公開說明、重大訊息、資本支出、新產品進度或管理層聲明（約50-90字）"
}}"""
            else:
                prompt = f"""你是一位總體經濟與跨資產研究員。請透過 Google 搜尋針對「{name} ({ticker})」（最新報價 {price_str}，單日漲跌幅 {pct:+.2f}%）整理近期走勢原因。
近期新聞參考：
{news_context}

請嚴格以 JSON 格式回傳以下欄位（繁體中文，具體精煉）：
{{
  "bull_factors": ["近期支撐價格或利多因素1", "因素2"],
  "bear_factors": ["近期壓抑價格或利空風險因素1", "因素2"],
  "earnings_note": "",
  "announcements": "近期關鍵總經數據公布、央行政策動向或供需市場重要事件摘要（約50-80字）"
}}"""
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.2}
            }
            res = requests.post(api_url, json=payload, timeout=25)
            if res.status_code == 200:
                res_json = res.json()
                text_out = ""
                for part in res_json.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "text" in part:
                        text_out += part["text"]
                start_idx = text_out.find('{')
                end_idx = text_out.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    parsed = json.loads(text_out[start_idx:end_idx+1])
                    time.sleep(1) # 避免 API 瞬間頻率過高
                    return {
                        "bull_factors": parsed.get("bull_factors", []),
                        "bear_factors": parsed.get("bear_factors", []),
                        "earnings_note": parsed.get("earnings_note", ""),
                        "announcements": parsed.get("announcements", ""),
                        "news_list": headlines
                    }
        except Exception as e:
            print(f"Gemini API error for {name}: {e}")

    # 若未設定 GEMINI_API_KEY 或連線逾時，自動使用新聞標題與財報數據產生摘要
    bulls = [h["title"] for h in headlines[:2]] if headlines else [f"跟隨{category}整體資金與產業趨勢波動"]
    bears = [h["title"] for h in headlines[2:4]] if len(headlines) > 2 else ["留意短線技術面乖離與總經利率政策不確定性"]
    e_note = f"最近財報季度 ({fin_data['period']})：營收 {fin_data['revenue']}，稅後淨利 {fin_data['net_income']}，EPS {fin_data['eps']}，毛利率 {fin_data['gross_margin']}，營收年增率 {fin_data['yoy_growth']}。" if is_stock else ""
    ann = headlines[0]["title"] if headlines else "近期無重大異常公開訊息，建議關注下期財報與法說會指引。"
    
    return {
        "bull_factors": bulls,
        "bear_factors": bears,
        "earnings_note": e_note,
        "announcements": ann,
        "news_list": headlines
    }

dashboard_data = {}

# 3. 遍歷所有資產，抓取報價、1年歷史走勢、大盤對比與深度分析
for category, tickers in yf_assets.items():
    dashboard_data[category] = []
    for name, ticker in tickers.items():
        try:
            print(f"正在處理: {name} ({ticker})...")
            tk = yf.Ticker(ticker)
            hist_1y = tk.history(period="1y").dropna(subset=['Close'])
            if len(hist_1y) < 2:
                continue
                
            today = float(hist_1y['Close'].iloc[-1])
            yesterday = float(hist_1y['Close'].iloc[-2])
            
            # 強制校正美債殖利率，確保數值永遠落在合理的 1% ~ 15% 真實殖利率區間
            scale_factor = 1.0
            if category == "美債殖利率":
                while today > 15:
                    today /= 10.0
                    yesterday /= 10.0
                    scale_factor /= 10.0
                while today < 0.8 and today > 0:
                    today *= 10.0
                    yesterday *= 10.0
                    scale_factor *= 10.0
            
            diff_val = today - yesterday
            pct = (diff_val / yesterday) * 100
            sign = "+" if diff_val > 0 else ""
            
            if category == "美債殖利率":
                price_str = f"{today:.2f}%"
                diff_str = f"{sign}{diff_val:.2f}"
            elif category == "外匯市場":
                price_str = f"{today:.3f}"
                diff_str = f"{sign}{diff_val:.3f}"
            else:
                price_str = f"{today:.2f}"
                diff_str = f"{sign}{diff_val:.2f}"
            
            # 抓取當日 5 分鐘 K 線製作卡片上的迷你走勢圖 (Sparkline)
            sparkline = []
            try:
                intra = tk.history(period="1d", interval="5m").dropna(subset=['Close'])
                if len(intra) > 5:
                    raw_pts = [float(x) * scale_factor for x in intra['Close'].tolist()]
                    step = max(1, len(raw_pts) // 25)
                    sparkline = [round(x, 4) for x in raw_pts[::step]]
                else:
                    sparkline = [round(float(x) * scale_factor, 4) for x in hist_1y['Close'].tail(5).tolist()]
            except Exception:
                sparkline = [round(float(x) * scale_factor, 4) for x in hist_1y['Close'].tail(5).tolist()]

            # 整理近一年完整走勢 (Dates & Prices)
            hist_1y.index = hist_1y.index.strftime('%Y-%m-%d')
            dates_1y = hist_1y.index.tolist()
            prices_1y = [round(float(x) * scale_factor, 3) for x in hist_1y['Close'].tolist()]
            
            # 計算近一年累計漲跌幅
            year_change_pct = round(((prices_1y[-1] - prices_1y[0]) / prices_1y[0]) * 100, 2) if prices_1y[0] != 0 else 0

            # 若為美股或台股個股，對齊大盤近一年走勢進行對比
            benchmark_info = None
            if category == "美股科技股" and "US" in benchmarks:
                b_series = benchmarks["US"].reindex(hist_1y.index).ffill().bfill()
                benchmark_info = {
                    "name": "納斯達克指數 (NASDAQ)",
                    "prices": [round(float(x), 2) for x in b_series.tolist()]
                }
            elif category == "台股權值股" and "TW" in benchmarks:
                b_series = benchmarks["TW"].reindex(hist_1y.index).ffill().bfill()
                benchmark_info = {
                    "name": "台股加權指數 (TAIEX)",
                    "prices": [round(float(x), 2) for x in b_series.tolist()]
                }

            # 抓取個股財務數據與近期新聞/AI分析
            is_stock = category in ["台股權值股", "美股科技股"]
            fin_data = get_stock_financials(tk, ticker) if is_stock else None
            headlines = fetch_rss_news(name, ticker)
            intel = generate_market_intelligence(name, ticker, category, price_str, pct, fin_data, headlines)

            dashboard_data[category].append({
                "id": ticker,
                "name": name,
                "category": category,
                "is_stock": is_stock,
                "price": price_str,
                "diff": diff_str,
                "change": round(pct, 2),
                "year_change": year_change_pct,
                "sparkline": sparkline,
                "history_1y": {
                    "dates": dates_1y,
                    "prices": prices_1y,
                    "benchmark": benchmark_info
                },
                "financials": fin_data,
                "analysis": intel
            })
        except Exception as e:
            print(f"Error {name}: {e}")

# 4. 抓取證交所三大法人近 30 個交易日歷史數據與最新買賣超
twse_success = False
twse_date_label = ""
twse_chips = []

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/zh/trading/foreign/bfi82u.html',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
}

tw_now = datetime.utcnow() + timedelta(hours=8)
chip_history = {"dates": [], "foreign": [], "trust": [], "dealer": []}

# 往回搜尋最近 25 天內的開盤日，建立法人買賣超趨勢圖與最新數據
for i in range(25):
    target_date = (tw_now - timedelta(days=i)).strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate={target_date}"
    try:
        res = session.get(url, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            twse_data = res.json()
            if twse_data.get('stat') == 'OK' and twse_data.get('data'):
                f_val, t_val, d_val = 0, 0, 0
                for row in twse_data['data']:
                    r_name = str(row[0]).strip()
                    diff_s = str(row[3]).replace(',', '').replace(' ', '').strip()
                    if not diff_s or diff_s == '-':
                        continue
                    diff = int(float(diff_s))
                    if '外資' in r_name: f_val += diff
                    elif '投信' in r_name: t_val += diff
                    elif '自營商' in r_name: d_val += diff
                
                if f_val != 0 or t_val != 0 or d_val != 0:
                    f_yi = round(f_val / 100_000_000, 2)
                    t_yi = round(t_val / 100_000_000, 2)
                    d_yi = round(d_val / 100_000_000, 2)
                    d_fmt = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
                    
                    chip_history["dates"].insert(0, d_fmt)
                    chip_history["foreign"].insert(0, f_yi)
                    chip_history["trust"].insert(0, t_yi)
                    chip_history["dealer"].insert(0, d_yi)
                    
                    if not twse_success:
                        twse_date_label = f"{target_date[:4]}/{target_date[4:6]}/{target_date[6:]}"
                        twse_success = True
                    if len(chip_history["dates"]) >= 15:
                        break
    except Exception:
        pass

if twse_success and len(chip_history["dates"]) > 0:
    fmt = lambda v: f"+{v} 億" if v > 0 else f"{v} 億"
    f_latest = chip_history["foreign"][-1]
    t_latest = chip_history["trust"][-1]
    d_latest = chip_history["dealer"][-1]
    
    chip_configs = [
        ("外資買賣超", f_latest, chip_history["foreign"], "外資近期買賣超動向反映國際資金與匯率配置趨勢。"),
        ("投信買賣超", t_latest, chip_history["trust"], "投信買賣超反映國內主動型基金與被動型 ETF 申贖及季底作帳動向。"),
        ("自營商買賣超", d_latest, chip_history["dealer"], "自營商買賣超包含自行買賣與權證避險部位，反映短線市場交投熱度。")
    ]
    
    for c_name, c_latest, c_series, c_desc in chip_configs:
        twse_chips.append({
            "id": c_name,
            "name": c_name,
            "category": "台股籌碼",
            "is_stock": False,
            "price": fmt(c_latest),
            "change": 1 if c_latest > 0 else (-1 if c_latest < 0 else 0),
            "sparkline": c_series[-10:],
            "history_1y": {
                "dates": chip_history["dates"],
                "prices": c_series,
                "benchmark": None
            },
            "financials": None,
            "analysis": {
                "bull_factors": [f"最新單日買賣超金額：{fmt(c_latest)}", f"近 {len(c_series)} 個交易日累積淨額：{fmt(round(sum(c_series), 2))}"],
                "bear_factors": ["需同步留意台指期未平倉口數與新台幣匯率波動對籌碼延續性的影響"],
                "earnings_note": "",
                "announcements": c_desc,
                "news_list": []
            }
        })
else:
    for c_name in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
        twse_chips.append({"id": c_name, "name": c_name, "price": "連線失敗", "change": 0})

# 將三大法人附加到「台股市場」的台股加權指數後面
final_dashboard_data = {}
for k, v in dashboard_data.items():
    if k == "台股市場":
        section_title = f"台股市場 (籌碼日期: {twse_date_label})" if twse_date_label else "台股市場"
        final_dashboard_data[section_title] = v + twse_chips
    else:
        final_dashboard_data[k] = v

tw_time_str = tw_now.strftime("%Y-%m-%d %H:%M")

output_content = f"const lastUpdate = '{tw_time_str}';\nconst data = {json.dumps(final_dashboard_data, ensure_ascii=False)};"
with open('data.js', 'w', encoding='utf-8') as f:
    f.write(output_content)
print("更新完成！")
