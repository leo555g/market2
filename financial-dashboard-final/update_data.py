import yfinance as yf
import json
import requests

yf_assets = {
    "全球指數": {"標普 500": "^GSPC", "道瓊工業": "^DJI", "納斯達克": "^IXIC", "費城半導體": "^SOX", "台股指數": "^TWII", "日經 225": "^N225", "韓國 KOSPI": "^KS11"},
    "外匯市場": {"USD/TWD": "USDTWD=X", "美元指數 (DXY)": "DX-Y.NYB", "人民幣 (USD/CNY)": "USDCNY=X", "歐元 (EUR/USD)": "EURUSD=X", "日圓 (USD/JPY)": "USDJPY=X", "英鎊 (GBP/USD)": "GBPUSD=X"},
    "美債殖利率": {"10年期": "^TNX", "30年期": "^TYX"},
    "原物料": {"黃金": "GC=F", "白銀": "SI=F", "銅": "HG=F", "布蘭特原油": "BZ=F", "WTI原油": "CL=F"},
    "核心科技股": {"輝達 (NVDA)": "NVDA", "台積電 (TSM)": "TSM", "AMD": "AMD"}
}

dashboard_data = {}

print("開始爬取國際金融報價...")
for category, tickers in yf_assets.items():
    dashboard_data[category] = []
    for name, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) >= 2:
                today = hist['Close'].iloc[-1]
                yesterday = hist['Close'].iloc[-2]
                
                # 修正：Yahoo Finance 殖利率報價放大10倍問題
                if category == "美債殖利率":
                    today = today / 10
                    yesterday = yesterday / 10
                    
                pct = ((today - yesterday) / yesterday) * 100
                
                # 修正：外匯與殖利率增加小數點位數
                if category == "美債殖利率" or category == "外匯市場":
                    price_str = f"{today:.3f}"
                    if category == "美債殖利率": price_str += "%"
                else:
                    price_str = f"{today:.2f}"
                    
                dashboard_data[category].append({"name": name, "price": price_str, "change": round(pct, 2)})
        except Exception as e:
            pass

print("開始爬取 TWSE 證交所三大法人數據...")
try:
    url = "https://www.twse.com.tw/fund/BFI82U?response=json"
    res = requests.get(url)
    twse_data = res.json()
    
    if twse_data.get('stat') == 'OK':
        foreign_net = 0
        trust_net = 0
        dealer_net = 0
        
        for row in twse_data['data']:
            name = row[0]
            net_value = int(row[3].replace(',', ''))
            
            if '外資' in name:
                foreign_net += net_value
            elif name == '投信':
                trust_net += net_value
            elif '自營商' in name:
                dealer_net += net_value
                
        f_val = round(foreign_net / 100_000_000, 1)
        t_val = round(trust_net / 100_000_000, 1)
        d_val = round(dealer_net / 100_000_000, 1)
        
        fmt = lambda v: f"+ {v} 億" if v > 0 else f"- {abs(v)} 億"
        
        dashboard_data["台股籌碼"] = [
            {"name": "外資買賣超", "price": fmt(f_val), "change": 1 if f_val > 0 else -1},
            {"name": "投信買賣超", "price": fmt(t_val), "change": 1 if t_val > 0 else -1},
            {"name": "自營商買賣超", "price": fmt(d_val), "change": 1 if d_val > 0 else -1}
        ]
    else:
        dashboard_data["台股籌碼"] = []
except Exception as e:
    print(f"證交所資料爬取失敗: {e}")
    dashboard_data["台股籌碼"] = []

with open('data.js', 'w', encoding='utf-8') as f:
    f.write(f"const data = {json.dumps(dashboard_data, ensure_ascii=False)};")
print("更新完成")