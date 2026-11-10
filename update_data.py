import yfinance as yf
import json
import requests
from datetime import datetime, timedelta
import urllib3

# 忽略 SSL 憑證警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

yf_assets = {
    "全球指數": {
        "標普 500": "^GSPC", 
        "道瓊工業": "^DJI", 
        "納斯達克": "^IXIC", 
        "費城半導體": "^SOX", 
        "台股指數": "^TWII", 
        "日經 225": "^N225", 
        "韓國 KOSPI": "^KS11",
        "英國富時 100": "^FTSE",
        "德國 DAX": "^GDAXI",
        "法國 CAC 40": "^FCHI"
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
    },
    "核心科技股": {
        "輝達 (NVDA)": "NVDA", 
        "台積電 (TSM)": "TSM", 
        "AMD": "AMD"
    }
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
                
                # 強制校正美債殖利率，確保數值永遠落在合理的 1% ~ 15% 真實殖利率區間
                if category == "美債殖利率":
                    while today > 15:
                        today /= 10.0
                        yesterday /= 10.0
                    while today < 0.8 and today > 0:
                        today *= 10.0
                        yesterday *= 10.0
                        
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

# 2. 直連證交所三大法人網頁 (https://www.twse.com.tw/zh/trading/foreign/bfi82u.html)
twse_success = False
session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/zh/trading/foreign/bfi82u.html',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
}

# 自動往回尋找最近一個有開盤的交易日（最多找7天）
tw_now = datetime.utcnow() + timedelta(hours=8)

for i in range(7):
    target_date = (tw_now - timedelta(days=i)).strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate={target_date}"
    
    try:
        res = session.get(url, headers=headers, timeout=15, verify=False)
        if res.status_code == 200:
            twse_data = res.json()
            if twse_data.get('stat') == 'OK' and twse_data.get('data'):
                f_val, t_val, d_val = 0, 0, 0
                
                for row in twse_data['data']:
                    name = str(row[0]).strip()
                    diff_str = str(row[3]).replace(',', '').replace(' ', '').strip()
                    if not diff_str or diff_str == '-':
                        continue
                    diff = int(float(diff_str))
                    
                    if '外資' in name:
                        f_val += diff
                    elif '投信' in name:
                        t_val += diff
                    elif '自營商' in name:
                        d_val += diff
                        
                if f_val != 0 or t_val != 0 or d_val != 0:
                    f_yi = round(f_val / 100_000_000, 2)
                    t_yi = round(t_val / 100_000_000, 2)
                    d_yi = round(d_val / 100_000_000, 2)
                    
                    fmt = lambda v: f"+{v} 億" if v > 0 else f"{v} 億"
                    
                    dashboard_data[f"台股籌碼 ({target_date[:4]}/{target_date[4:6]}/{target_date[6:]})"] = [
                        {"name": "外資買賣超", "price": fmt(f_yi), "change": 1 if f_yi > 0 else (-1 if f_yi < 0 else 0)},
                        {"name": "投信買賣超", "price": fmt(t_yi), "change": 1 if t_yi > 0 else (-1 if t_yi < 0 else 0)},
                        {"name": "自營商買賣超", "price": fmt(d_yi), "change": 1 if d_yi > 0 else (-1 if d_yi < 0 else 0)}
                    ]
                    twse_success = True
                    print(f"成功抓取 {target_date} 證交所三大法人數據！")
                    break
    except Exception as e:
        print(f"嘗試抓取 {target_date} 失敗: {e}")

if not twse_success:
    dashboard_data["台股籌碼"] = [
        {"name": "外資買賣超", "price": "連線失敗", "change": 0},
        {"name": "投信買賣超", "price": "連線失敗", "change": 0},
        {"name": "自營商買賣超", "price": "連線失敗", "change": 0}
    ]

# 紀錄最後更新時間 (台灣時間 UTC+8)
tw_time_str = tw_now.strftime("%Y-%m-%d %H:%M")

output_content = f"const lastUpdate = '{tw_time_str}';\nconst data = {json.dumps(dashboard_data, ensure_ascii=False)};"
with open('data.js', 'w', encoding='utf-8') as f:
    f.write(output_content)
