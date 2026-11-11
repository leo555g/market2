import os
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

# 2. 預先抓取大盤基準（納斯達克 ^IXIC、台股加權 ^TWII）近一年走勢，供個股對齊比較
benchmarks = {}
for b_key, b_ticker in [("US", "^IXIC"), ("TW", "^TWII")]:
    try:
        b_hist = yf.Ticker(b_ticker).history(period="1y").dropna(subset=['Close'])
        b_hist.index = b_hist.index.strftime('%Y-%m-%d')
        benchmarks[b_key] = b_hist['Close']
    except Exception as e:
        print(f"Benchmark {b_ticker} error: {e}")

# 輔助函式：格式化財務金額
def fmt_money(val, is_tw=False):
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

# 輔助函式：擷取個股最新一季財報數據（含雙重備援）
def extract_financials(tk, ticker):
    is_tw = ".TW" in ticker
    fin = {
        "period": "最近一季財報",
        "revenue": "N/A",
        "net_income": "N/A",
        "eps": "N/A",
        "gross_margin": "N/A",
        "operating_margin": "N/A",
        "pe_ratio": "N/A",
        "yoy_growth": "N/A",
        "raw_yoy": None,
        "raw_gm": None
    }
    try:
        info = tk.info or {}
        if info.get("trailingEps") is not None:
            fin["eps"] = f"{float(info['trailingEps']):.2f} (TTM)"
        if info.get("grossMargins") is not None:
            gm = float(info["grossMargins"]) * 100
            fin["gross_margin"] = f"{gm:.2f}%"
            fin["raw_gm"] = gm
        if info.get("operatingMargins") is not None:
            fin["operating_margin"] = f"{float(info['operatingMargins']) * 100:.2f}%"
        if info.get("trailingPE") is not None:
            fin["pe_ratio"] = f"{float(info['trailingPE']):.2f}x"
        elif info.get("forwardPE") is not None:
            fin["pe_ratio"] = f"{float(info['forwardPE']):.2f}x (預估)"
        if info.get("revenueGrowth") is not None:
            yoy = float(info["revenueGrowth"]) * 100
            fin["yoy_growth"] = f"{yoy:+.2f}%"
            fin["raw_yoy"] = yoy
        if info.get("totalRevenue") is not None:
            fin["revenue"] = fmt_money(info["totalRevenue"], is_tw) + " (TTM)"
        if info.get("netIncomeToCommon") is not None:
            fin["net_income"] = fmt_money(info["netIncomeToCommon"], is_tw) + " (TTM)"

        # 優先讀取最新單季損益表 (Quarterly Income Statement)
        q_stmt = tk.quarterly_income_stmt
        if q_stmt is not None and not q_stmt.empty:
            col0 = q_stmt.columns[0]
            fin["period"] = f"單季截至 {str(col0)[:10]}"
            
            # 單季營收與季對季/年對年比較
            for r_key in ['Total Revenue', 'Operating Revenue']:
                if r_key in q_stmt.index:
                    v0 = q_stmt.loc[r_key, col0]
                    m_str = fmt_money(v0, is_tw)
                    if m_str:
                        fin["revenue"] = m_str
                    # 若有去年同期欄位 (第5欄) 計算單季 YoY
                    if len(q_stmt.columns) >= 5:
                        v_yoy = q_stmt.loc[r_key, q_stmt.columns[4]]
                        if v0 and v_yoy and v_yoy == v_yoy and float(v_yoy) != 0:
                            q_yoy = ((float(v0) - float(v_yoy)) / abs(float(v_yoy))) * 100
                            fin["yoy_growth"] = f"{q_yoy:+.2f}%"
                            fin["raw_yoy"] = q_yoy
                    break

            # 單季稅後淨利
            for n_key in ['Net Income', 'Net Income Common Stockholders']:
                if n_key in q_stmt.index:
                    m_str = fmt_money(q_stmt.loc[n_key, col0], is_tw)
                    if m_str:
                        fin["net_income"] = m_str
                    break

            # 單季毛利計算毛利率
            if 'Gross Profit' in q_stmt.index and 'Total Revenue' in q_stmt.index:
                gp = q_stmt.loc['Gross Profit', col0]
                tr = q_stmt.loc['Total Revenue', col0]
                if gp and tr and gp == gp and tr == tr and float(tr) != 0:
                    q_gm = (float(gp) / float(tr)) * 100
                    fin["gross_margin"] = f"{q_gm:.2f}%"
                    fin["raw_gm"] = q_gm

            # 單季營業利益率
            if 'Operating Income' in q_stmt.index and 'Total Revenue' in q_stmt.index:
                oi = q_stmt.loc['Operating Income', col0]
                tr = q_stmt.loc['Total Revenue', col0]
                if oi and tr and oi == oi and tr == tr and float(tr) != 0:
                    fin["operating_margin"] = f"{(float(oi) / float(tr)) * 100:.2f}%"

            # 單季 EPS
            for e_key in ['Diluted EPS', 'Basic EPS']:
                if e_key in q_stmt.index:
                    eps_v = q_stmt.loc[e_key, col0]
                    if eps_v is not None and eps_v == eps_v:
                        fin["eps"] = f"{float(eps_v):.2f} (單季)"
                    break
    except Exception as e:
        print(f"Financial extraction warning for {ticker}: {e}")
    return fin

# 輔助函式：抓取 Google News RSS 最新新聞與公開訊息
def fetch_rss_news(name, ticker):
    clean_name = name.split('(')[0].strip()
    code_only = ticker.replace('.TW', '').replace('^', '').replace('=X', '').replace('=F', '')
    query = f'"{clean_name}" OR "{code_only}"'
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headlines = []
    try:
        res = requests.get(url, timeout=6)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall('.//item')[:6]:
                title = item.find('title').text if item.find('title') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                pub_date = item.find('pubDate').text[:16] if item.find('pubDate') is not None else ''
                if title:
                    headlines.append({"title": title, "link": link, "date": pub_date})
    except Exception:
        pass
    return headlines

# 輔助函式：結合量化技術指標、財報與新聞（及可選 Gemini API）產出深度多空分析與公開說明
def build_deep_analysis(name, ticker, category, prices_1y, bench_info, fin_data, headlines):
    is_stock = category in ["台股權值股", "美股科技股"]
    today = prices_1y[-1]
    yesterday = prices_1y[-2]
    day_pct = ((today - yesterday) / yesterday) * 100
    pct_5d = ((today - prices_1y[-5]) / prices_1y[-5]) * 100 if len(prices_1y) >= 5 else day_pct
    pct_20d = ((today - prices_1y[-20]) / prices_1y[-20]) * 100 if len(prices_1y) >= 20 else day_pct
    pct_1y = ((today - prices_1y[0]) / prices_1y[0]) * 100
    
    ma20 = sum(prices_1y[-20:]) / min(20, len(prices_1y))
    ma60 = sum(prices_1y[-60:]) / min(60, len(prices_1y))
    high_1y = max(prices_1y)
    low_1y = min(prices_1y)

    bulls = []
    bears = []

    # 1. 價格動能與均線位階量化判斷
    if today >= ma20:
        bulls.append(f"技術面維持多頭排列：最新報價站穩月線 (20MA: {ma20:.2f}) 之上，近5日累計變動 {pct_5d:+.2f}%。")
    else:
        bears.append(f"短線技術面承壓：最新報價跌破月線 (20MA: {ma20:.2f})，近5日累計變動 {pct_5d:+.2f}%，上方月線轉為反壓。")

    if today >= ma60:
        bulls.append(f"中長期趨勢偏多：持穩於季線 (60MA: {ma60:.2f}) 之上，近一年累計漲跌幅達 {pct_1y:+.2f}%。")
    else:
        bears.append(f"中期趨勢轉弱：目前位於季線 (60MA: {ma60:.2f}) 下方整理，距離近一年高點 ({high_1y:.2f}) 回檔約 {((today - high_1y)/high_1y)*100:.1f}%。")

    # 2. 相對大盤強弱度 (Alpha) 判斷
    if bench_info and len(bench_info["prices"]) == len(prices_1y):
        b_prices = bench_info["prices"]
        b_1y_pct = ((b_prices[-1] - b_prices[0]) / b_prices[0]) * 100
        alpha_1y = pct_1y - b_1y_pct
        b_20d_pct = ((b_prices[-1] - b_prices[-20]) / b_prices[-20]) * 100 if len(b_prices) >= 20 else 0
        alpha_20d = pct_20d - b_20d_pct
        
        if alpha_1y >= 0:
            bulls.append(f"長線跑贏大盤基準：近一年相較於{bench_info['name']} ({b_1y_pct:+.2f}%) 創造了 +{alpha_1y:.2f}% 的超額報酬 (Alpha)。")
        else:
            bears.append(f"長線相對大盤落後：近一年表現落後於{bench_info['name']} ({b_1y_pct:+.2f}%) 達 {alpha_1y:.2f}%。")
            
        if alpha_20d >= 0:
            bulls.append(f"近期資金相對青睞：近20個交易日表現優於{bench_info['name']}達 +{alpha_20d:.2f}%。")
        else:
            bears.append(f"近期資金動能偏弱：近20個交易日表現落後{bench_info['name']}達 {alpha_20d:.2f}%。")

    # 3. 個股財報基本面多空判斷
    earnings_note = ""
    if is_stock and fin_data:
        raw_yoy = fin_data.get("raw_yoy")
        raw_gm = fin_data.get("raw_gm")
        if raw_yoy is not None:
            if raw_yoy > 10:
                bulls.append(f"基本面營收強勁成長：最新財報營收年增率 (YoY) 高達 {raw_yoy:+.2f}%，營運規模持續擴張。")
            elif raw_yoy < 0:
                bears.append(f"基本面營收成長放緩：最新財報營收年增率為 {raw_yoy:+.2f}%，終端需求或出貨動能待回溫。")
        if raw_gm is not None and raw_gm > 40:
            bulls.append(f"高毛利護城河優勢：毛利率維持在 {raw_gm:.2f}% 的高檔水準，展現強勁產品定價權。")
            
        earnings_note = (
            f"【{fin_data['period']} 財報核心摘要】\n"
            f"• 營收表現：{fin_data['revenue']}（年增率 YoY：{fin_data['yoy_growth']}）\n"
            f"• 獲利能力：稅後淨利 {fin_data['net_income']}，每股盈餘 (EPS) {fin_data['eps']}\n"
            f"• 利潤率與估值：毛利率 {fin_data['gross_margin']}，營業利益率 {fin_data['operating_margin']}，目前本益比約 {fin_data['pe_ratio']}。"
        )

    # 4. 整合近期新聞催化劑與公開說明
    bull_kw = ['漲', '高', '買', '增', '優', '利多', '突破', '創', '旺', '強', '法說', '擴產', '訂單', '上調', '看好', '超預期', 'AI']
    bear_kw = ['跌', '低', '賣', '減', '砍', '利空', '壓', '弱', '憂', '降', '修正', '關稅', '通膨', '裁員', '下調', '風險']
    
    for h in headlines[:4]:
        t = h["title"]
        if any(k in t for k in bear_kw) and not any(k in t for k in ['無懼', '反彈']):
            bears.append(f"市場消息面關注：{t}")
        elif any(k in t for k in bull_kw):
            bulls.append(f"近期市場催化劑：{t}")

    if headlines:
        announcements = "【近期公司公開動態与市場焦點彙整】\n" + "\n".join([f"• {h['title']} ({h['date']})" for h in headlines[:3]])
    else:
        announcements = f"目前 {name} 價格處於 {today:.2f}（近一年區間 {low_1y:.2f} ~ {high_1y:.2f}），建議持續追蹤後續法說會展望與總經數據發布。"

    # 5. 若有設定 GEMINI_API_KEY，嘗試呼叫 AI 進行深度潤飾
    if GEMINI_API_KEY and is_stock:
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            news_txt = "\n".join([f"- {h['title']}" for h in headlines[:5]])
            prompt = f"""請針對「{name} ({ticker})」（最新價 {today:.2f}，單日 {day_pct:+.2f}%，近一年 {pct_1y:+.2f}%，財報：{json.dumps(fin_data, ensure_ascii=False)}，近期新聞：\n{news_txt}）以 JSON 回傳繁體中文分析：
{{
  "bull_factors": ["具體利多1", "具體利多2", "具體利多3"],
  "bear_factors": ["具體利空或風險1", "具體利空或風險2"],
  "earnings_note": "最新一季財報數據亮點與營運展望整理（約80-120字）",
  "announcements": "近期公司公開說明、法說會指引或重大產業動態整合（約80-120字）"
}}"""
            res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12)
            if res.status_code == 200:
                txt = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                s_idx, e_idx = txt.find('{'), txt.rfind('}')
                if s_idx != -1 and e_idx != -1:
                    ai_data = json.loads(txt[s_idx:e_idx+1])
                    return {
                        "bull_factors": ai_data.get("bull_factors") or bulls[:4],
                        "bear_factors": ai_data.get("bear_factors") or bears[:4],
                        "earnings_note": ai_data.get("earnings_note") or earnings_note,
                        "announcements": ai_data.get("announcements") or announcements,
                        "news_list": headlines
                    }
        except Exception as e:
            print(f"Gemini fallback for {ticker}: {e}")

    return {
        "bull_factors": bulls[:4],
        "bear_factors": bears[:4],
        "earnings_note": earnings_note,
        "announcements": announcements,
        "news_list": headlines
    }

dashboard_data = {}

# 3. 遍歷所有資產並建立完整資料結構
for category, tickers in yf_assets.items():
    dashboard_data[category] = []
    for name, ticker in tickers.items():
        try:
            print(f"Fetching {name} ({ticker})...")
            tk = yf.Ticker(ticker)
            hist_1y = tk.history(period="1y").dropna(subset=['Close'])
            if len(hist_1y) < 2:
                continue
                
            # 強制校正美債殖利率，確保數值永遠落在合理的 1% ~ 15% 真實殖利率區間
            scale_factor = 1.0
            raw_last = float(hist_1y['Close'].iloc[-1])
            if category == "美債殖利率":
                while raw_last * scale_factor > 15:
                    scale_factor /= 10.0
                while 0 < raw_last * scale_factor < 0.8:
                    scale_factor *= 10.0

            hist_1y.index = hist_1y.index.strftime('%Y-%m-%d')
            dates_1y = hist_1y.index.tolist()
            prices_1y = [round(float(x) * scale_factor, 3) for x in hist_1y['Close'].tolist()]
            
            today = prices_1y[-1]
            yesterday = prices_1y[-2]
            diff_val = today - yesterday
            pct = (diff_val / yesterday) * 100
            year_change_pct = round(((today - prices_1y[0]) / prices_1y[0]) * 100, 2) if prices_1y[0] != 0 else 0
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
            
            # 抓取當日 5 分鐘 K 線製作迷你走勢圖 (Sparkline)
            sparkline = []
            try:
                intra = tk.history(period="1d", interval="5m").dropna(subset=['Close'])
                if len(intra) > 5:
                    raw_pts = [float(x) * scale_factor for x in intra['Close'].tolist()]
                    step = max(1, len(raw_pts) // 25)
                    sparkline = [round(x, 4) for x in raw_pts[::step]]
                else:
                    sparkline = prices_1y[-15:]
            except Exception:
                sparkline = prices_1y[-15:]

            # 對齊大盤指數（美股個股對比納斯達克、台股個股對比台股加權）
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

            is_stock = category in ["台股權值股", "美股科技股"]
            fin_data = extract_financials(tk, ticker) if is_stock else None
            headlines = fetch_rss_news(name, ticker)
            analysis_data = build_deep_analysis(name, ticker, category, prices_1y, benchmark_info, fin_data, headlines)

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
                "analysis": analysis_data
            })
        except Exception as e:
            print(f"Error processing {name}: {e}")

# 4. 抓取證交所三大法人數據與歷史趨勢
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

for i in range(22):
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
                    if len(chip_history["dates"]) >= 12:
                        break
    except Exception:
        pass

if twse_success and len(chip_history["dates"]) > 0:
    fmt = lambda v: f"+{v} 億" if v > 0 else f"{v} 億"
    chip_configs = [
        ("外資買賣超", chip_history["foreign"], "外資買賣超直接反映國際機構資金對台股權值股與新台幣匯率之配置態度。"),
        ("投信買賣超", chip_history["trust"], "投信買賣超反映國內主動型基金與高股息／市值型 ETF 申贖及季底作帳動向。"),
        ("自營商買賣超", chip_history["dealer"], "自營商買賣超包含自行買賣與權證避險部位，反映內資短線市場交投熱度。")
    ]
    for c_name, c_series, c_desc in chip_configs:
        c_latest = c_series[-1]
        c_sum = round(sum(c_series), 2)
        twse_chips.append({
            "id": "TWSE_CHIP",
            "name": c_name,
            "category": "台股籌碼",
            "is_stock": False,
            "price": fmt(c_latest),
            "change": 1 if c_latest > 0 else (-1 if c_latest < 0 else 0),
            "sparkline": c_series,
            "history_1y": {
                "dates": chip_history["dates"],
                "prices": c_series,
                "benchmark": None
            },
            "financials": None,
            "analysis": {
                "bull_factors": [
                    f"最新單日買賣超金額：{fmt(c_latest)}",
                    f"近 {len(c_series)} 個交易日累計買賣超淨額：{fmt(c_sum)}"
                ],
                "bear_factors": [
                    "需同步搭配外資台指期未平倉空單水位與美元兌新台幣 (USD/TWD) 匯率走勢綜合研判"
                ],
                "earnings_note": "",
                "announcements": f"【證交所三大法人籌碼統計（資料日期：{twse_date_label}）】\n{c_desc}",
                "news_list": []
            }
        })
else:
    for c_name in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
        twse_chips.append({"id": c_name, "name": c_name, "price": "連線失敗", "change": 0})

# 合併「台股市場」與三大法人籌碼
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
print("所有數據與深度分析更新完成！")
