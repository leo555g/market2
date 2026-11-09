import os
import yfinance as yf
import json
import finlab
from finlab import data

finlab_token = os.environ.get('FINLAB_API_TOKEN')
if finlab_token:
    finlab.login(finlab_token)

yf_assets = {
    "全球指數": {"標普 500": "^GSPC", "道瓊工業": "^DJI", "納斯達克": "^IXIC", "費城半導體": "^SOX", "台股指數": "^TWII", "日經 225": "^N225", "韓國 KOSPI": "^KS11"},
    "外匯市場": {"USD/TWD": "USDTWD=X", "美元指數 (DXY)": "DX-Y.NYB", "人民幣 (USD/CNY)": "USDCNY=X", "歐元 (EUR/USD)": "EURUSD=X", "日圓 (USD/JPY)": "USDJPY=X", "英鎊 (GBP/USD)": "GBPUSD=X"},
    "美債殖利率": {"10年期": "^TNX", "30年期": "^TYX", "2年期": "ZT=F"},
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
                pct = ((today - yesterday) / yesterday) * 100
                price_str = f"{today:.2f}{'%' if '^' in ticker and category == '美債殖利率' else ''}"
                dashboard_data[category].append({"name": name, "price": price_str, "change": round(pct, 2)})
        except:
            pass

try:
    if finlab_token:
        inst_data = data.get('institutional_investors')
        if inst_data is not None and not inst_data.empty:
            latest = inst_data.loc[inst_data.index[-1]]
            f_val = round(latest.get('外資買賣超(元)', 0) / 100_000_000, 1)
            t_val = round(latest.get('投信買賣超(元)', 0) / 100_000_000, 1)
            d_val = round(latest.get('自營商買賣超(元)', 0) / 100_000_000, 1)
            fmt = lambda v: f"+ {v} 億" if v > 0 else f"- {abs(v)} 億"
            dashboard_data["台股籌碼"] = [
                {"name": "外資買賣超", "price": fmt(f_val), "change": 1 if f_val > 0 else -1},
                {"name": "投信買賣超", "price": fmt(t_val), "change": 1 if t_val > 0 else -1},
                {"name": "自營商買賣超", "price": fmt(d_val), "change": 1 if d_val > 0 else -1}
            ]
except:
    dashboard_data["台股籌碼"] = []

with open('data.js', 'w', encoding='utf-8') as f:
    f.write(f"const data = {json.dumps(dashboard_data, ensure_ascii=False)};")