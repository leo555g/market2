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

for category, tickers in yf_assets.items():
    dashboard_data[category] = []
    for name, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) >= 2:
                today = hist['Close'].iloc[-1]
                yesterday = hist['Close'].iloc[-2]
                
                # 修正殖利率被放大10倍的問題
                if category == "美債殖利率":
                    today = today / 10
                    yesterday = yesterday / 10
                    
                pct = ((today - yesterday) / yesterday) * 100
                
                if category == "美債殖利率" or category == "外匯市場":
                    price_str = f"{today:.3f}"
                    if category == "美債殖利率": price_str += "%"
                else:
                    price_str = f"{today:.2f}"
                    
                dashboard_data[category].append({"name": name, "price": price_str, "change": round(pct, 2)})
        except Exception:
            pass

# 改用證交所 OpenAPI，此端點不會封鎖 GitHub Actions
try:
    url = "https://openapi.twse.com.tw/v1/fund/BFI82U"
    res = requests.get(url, timeout=10)
    
    if res.status_code == 200:
        data_list = res.json()
        f_val = 0
        t_val = 0
        d_val = 0
        
        for item in data_list:
            # OpenAPI 欄位解析，相容大小寫
            name = item.get("type", item.get("Type", ""))
            diff_str = item.get("difference", item.get("Difference", "0"))
            diff = int(str(diff_str).replace(",", ""))
            
            if "外資" in name:
                f_val += diff
            elif "投信" in name:
                t_val += diff
            elif "自營商" in name:
                d_val += diff
                
        f_val = round(f_val / 100_000_000, 1)
        t_val = round(t_val / 100_000_000, 1)
        d_val = round(d_val / 100_000_000, 1)
        
        fmt = lambda v: f"+ {v} 億" if v > 0 else f"- {abs(v)} 億"
        
        dashboard_data["台股籌碼"] = [
            {"name": "外資買賣超", "price": fmt(f_val), "change": 1 if f_val > 0 else -1},
            {"name": "投信買賣超", "price": fmt(t_val), "change": 1 if t_val > 0 else -1},
            {"name": "自營商買賣超", "price": fmt(d_val), "change": 1 if d_val > 0 else -1}
        ]
    else:
        dashboard_data["台股籌碼"] = []
except Exception:
    dashboard_data["台股籌碼"] = []

with open('data.js', 'w', encoding='utf-8') as f:
    f.write(f"const data = {json.dumps(dashboard_data, ensure_ascii=False)};")
