import yfinance as yf
import json
import requests
from datetime import datetime, timedelta
import urllib3

# 忽略 SSL 憑證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

yf_assets = {
    "全球指數": {"標普 500": "^GSPC", "道瓊工業": "^DJI", "納斯達克": "^IXIC", "費城半導體": "^SOX", "台股指數": "^TWII", "日經 225": "^N225", "韓國 KOSPI": "^KS11"},
    "外匯市場": {"USD/TWD": "USDTWD=X", "美元指數 (DXY)": "DX-Y.NYB", "人民幣 (USD/CNY)": "USDCNY=X", "歐元 (EUR/USD)": "EURUSD=X", "日圓 (USD/JPY)": "USDJPY=X", "英鎊 (GBP/USD)": "GBPUSD=X"},
    "美債殖利率": {"10年期": "^TNX", "30年期": "^TYX"},
    "原物料": {"黃金": "GC=F", "白銀": "SI=F", "銅": "HG=F", "布蘭特原油": "BZ=F", "WTI原油": "CL=F"},
    "核心科技股": {"輝達 (NVDA)": "NVDA", "台積電 (TSM)": "TSM", "AMD": "AMD"}
}

dashboard_data = {}

# 1. 抓取全球金融報價
for category, tickers in yf_assets.items():
    dashboard_data[category] = []
    for name, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            hist = hist.dropna(subset=['Close'])
            if len(hist) >= 2:
                today = float(hist['Close'].iloc[-1])
                yesterday = float(hist['Close'].iloc[-2])
                
                # 防呆機制：如果報價異常大於 20 (代表舊版放大10倍格式) 才除以 10，否則保持原樣
                if category == "美債殖利率" and today > 20:
                    today /= 10
                    yesterday /= 10
                    
                pct = ((today - yesterday) / yesterday) * 100
                
                if category == "美債殖利率":
                    price_str = f"{today:.2f}%"
                elif category == "外匯市場":
                    price_str = f"{today:.3f}"
                else:
                    price_str = f"{today:.2f}"
                    
                dashboard_data[category].append({"name": name, "price": price_str, "change": round(pct, 2)})
        except Exception as e:
            print(f"Error {name}: {e}")

# 2. 抓取台股籌碼 (三道防線：證交所 OpenAPI -> 證交所官網 -> FinMind 英文標籤)
twse_success = False
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 防線 A：證交所 OpenAPI
try:
    res = requests.get("https://openapi.twse.com.tw/v1/fund/BFI82U", headers=headers, timeout=10, verify=False)
    if res.status_code == 200:
        data_list = res.json()
        if isinstance(data_list, list) and len(data_list) > 0:
            f_val, t_val, d_val = 0, 0, 0
            for item in data_list:
                name = str(item.get("單位名稱", item.get("type", item.get("Type", ""))))
                diff_str = str(item.get("買賣差額", item.get("difference", item.get("Difference", "0")))).replace(",", "")
                if diff_str and diff_str != "-":
                    diff = int(float(diff_str))
                    if "外資" in name: f_val += diff
                    elif "投信" in name: t_val += diff
                    elif "自營商" in name: d_val += diff
            if f_val != 0 or t_val != 0:
                f_val = round(f_val / 100_000_000, 1)
                t_val = round(t_val / 100_000_000, 1)
                d_val = round(d_val / 100_000_000, 1)
                fmt = lambda v: f"+ {v} 億" if v > 0 else f"- {abs(v)} 億"
                dashboard_data["台股籌碼"] = [
                    {"name": "外資買賣超", "price": fmt(f_val), "change": 1 if f_val > 0 else -1},
                    {"name": "投信買賣超", "price": fmt(t_val), "change": 1 if t_val > 0 else -1},
                    {"name": "自營商買賣超", "price": fmt(d_val), "change": 1 if d_val > 0 else -1}
                ]
                twse_success = True
except Exception as e:
    print(f"OpenAPI 失敗: {e}")

# 防線 B：FinMind API (修正為正確的英文標籤比對)
if not twse_success:
    try:
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockTotalInstitutionalInvestors&start_date={start_date}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            json_data = res.json()
            df_data = json_data.get("data", [])
            if len(df_data) > 0:
                last_date = df_data[-1]["date"]
                f_val, t_val, d_val = 0, 0, 0
                for row in df_data:
                    if row.get("date") == last_date:
                        name = str(row.get("name", ""))
                        net = float(row.get("buy", 0)) - float(row.get("sell", 0))
                        if "Foreign" in name or "外資" in name: f_val += net
                        elif "Investment_Trust" in name or "投信" in name: t_val += net
                        elif "Dealer" in name or "自營商" in name: d_val += net
                if f_val != 0 or t_val != 0:
                    f_val = round(f_val / 100_000_000, 1)
                    t_val = round(t_val / 100_000_000, 1)
                    d_val = round(d_val / 100_000_000, 1)
                    fmt = lambda v: f"+ {v} 億" if v > 0 else f"- {abs(v)} 億"
                    dashboard_data["台股籌碼"] = [
                        {"name": "外資買賣超", "price": fmt(f_val), "change": 1 if f_val > 0 else -1},
                        {"name": "投信買賣超", "price": fmt(t_val), "change": 1 if t_val > 0 else -1},
                        {"name": "自營商買賣超", "price": fmt(d_val), "change": 1 if d_val > 0 else -1}
                    ]
                    twse_success = True
    except Exception as e:
        print(f"FinMind 失敗: {e}")

if not twse_success:
    dashboard_data["台股籌碼"] = [
        {"name": "外資買賣超", "price": "更新中", "change": 0},
        {"name": "投信買賣超", "price": "更新中", "change": 0},
        {"name": "自營商買賣超", "price": "更新中", "change": 0}
    ]

# 紀錄最後更新時間 (台灣時間 UTC+8)
tw_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

output_content = f"const lastUpdate = '{tw_time}';\nconst data = {json.dumps(dashboard_data, ensure_ascii=False)};"
with open('data.js', 'w', encoding='utf-8') as f:
    f.write(output_content)
