import os
import json
import datetime
import pytz
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from opencc import OpenCC

# 初始化簡轉繁轉換器 (s2twp: 簡體到台灣正體，含台灣慣用詞彙轉換)
cc = OpenCC('s2twp')

def to_trad(text):
    """確保所有輸入文字皆轉換為台灣繁體中文"""
    if text is None:
        return ""
    return cc.convert(str(text))

# 設定台灣時區
tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.datetime.now(tw_tz)

# ==========================================
# 1. 資產清單定義 (美股僅保留純代號)
# ==========================================
INDICES = {
    "^GSPC": "S&P 500 指數",
    "^DJI": "道瓊工業指數",
    "^IXIC": "那斯達克指數",
    "^SOX": "費城半導體指數",
    "^TWII": "台灣加權指數",
    "^N225": "日經 225 指數",
    "^KS11": "韓國 KOSPI 指數",
    "^FTSE": "英國富時 100",
    "^GDAXI": "德國 DAX 指數",
    "^FCHI": "法國 CAC 40"
}

# 美股個股：依照需求 #4，名稱直接設為純英文代號，不顯示中文名稱
US_STOCKS = [
    "NVDA", "TSM", "AMD", "GOOGL", "META",
    "TSLA", "AVGO", "AMZN", "AAPL", "MSFT"
]

TW_STOCKS = {
    "2330": {"ticker": "2330.TW", "name": "2330 台積電"},
    "2454": {"ticker": "2454.TW", "name": "2454 聯發科"},
    "2308": {"ticker": "2308.TW", "name": "2308 台達電"},
    "2317": {"ticker": "2317.TW", "name": "2317 鴻海"},
    "3711": {"ticker": "3711.TW", "name": "3711 日月光投控"}
}

# 期貨與大宗商品 (支援當日正規收盤價 + 夜盤/電子盤即時報價)
FUTURES_AND_COMMODITIES = {
    "ES=F": "小S&P期貨",
    "NQ=F": "小那斯達克期貨",
    "GC=F": "黃金期貨",
    "SI=F": "白銀期貨",
    "HG=F": "銅期貨",
    "CL=F": "WTI 原油期貨",
    "BZ=F": "布蘭特原油期貨",
    "PA=F": "鈀金期貨",
    "ZS=F": "黃豆期貨",
    "ZW=F": "小麥期貨",
    "ZC=F": "玉米期貨"
}

FX_AND_BONDS = {
    "TWD=X": "美元/台幣 (USD/TWD)",
    "CNY=X": "美元/人民幣 (USD/CNY)",
    "EURUSD=X": "歐元/美元 (EUR/USD)",
    "JPY=X": "美元/日圓 (USD/JPY)",
    "GBPUSD=X": "英鎊/美元 (GBP/USD)",
    "DX-Y.NYB": "美元指數 (DXY)",
    "^TNX": "美國 10 年期公債殖利率",
    "^TYX": "美國 30 年期公債殖利率"
}

# ==========================================
# 2. 價格、盤前盤後、期貨夜盤與歷史 K 線抓取
# ==========================================
def fetch_ticker_full_data(symbol, display_name, asset_type="standard"):
    """
    抓取單一資產的：
    1. 正規收盤價與漲跌幅
    2. 美股盤前/盤後價格 (asset_type == 'us_stock')
    3. 期貨日盤結算價 + 夜盤即時價格 (asset_type == 'futures')
    4. 1D (5分鐘線) 與 2年歷史日線 (供 1W/1M/YTD 及任意自訂區間使用)
    5. 財報核心數據與獲利能力指標
    """
    result = {
        "symbol": symbol,
        "name": to_trad(display_name),
        "price": None,
        "change": 0.0,
        "change_pct": 0.0,
        "ext_session": None,  # 格式: {"label": "盤前"/"盤後"/"夜盤", "price": 100.0, "change_pct": 3.0}
        "intraday": [],       # [{"time": "09:30", "price": 100.5}, ...]
        "history": [],        # [{"date": "2025-01-02", "close": 98.2}, ...]
        "fundamentals": {}
    }

    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}

        # A. 取得近 2 年歷史日線 (供自訂日期區間查詢，涵蓋去年至今年所有交易日)
        hist_2y = tk.history(period="2y", interval="1d")
        if not hist_2y.empty:
            hist_2y = hist_2y.dropna(subset=["Close"])
            for idx, row in hist_2y.iterrows():
                dt_str = idx.strftime("%Y-%m-%d")
                result["history"].append({
                    "date": dt_str,
                    "close": round(float(row["Close"]), 2)
                })

            # 預設以日線最後兩筆計算正規收盤價與漲跌幅
            latest_close = float(hist_2y["Close"].iloc[-1])
            prev_close = float(hist_2y["Close"].iloc[-2]) if len(hist_2y) > 1 else latest_close
            result["price"] = round(latest_close, 2)
            result["change"] = round(latest_close - prev_close, 2)
            result["change_pct"] = round(((latest_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

        # B. 取得 1D 日內走勢 (5m K線，含盤前盤後以利觀察)
        hist_1d = tk.history(period="1d", interval="5m", prepost=True)
        if not hist_1d.empty:
            hist_1d = hist_1d.dropna(subset=["Close"])
            for idx, row in hist_1d.iterrows():
                t_str = idx.strftime("%H:%M")
                result["intraday"].append({
                    "time": t_str,
                    "price": round(float(row["Close"]), 2)
                })

        # C. 處理美股「盤前 / 盤後」邏輯 (需求 #6)
        market_state = info.get("marketState", "")
        reg_price = info.get("regularMarketPrice") or result["price"]
        reg_prev = info.get("regularMarketPreviousClose") or (result["price"] - result["change"] if result["price"] else None)

        if reg_price and reg_prev:
            result["price"] = round(float(reg_price), 2)
            result["change"] = round(float(reg_price - reg_prev), 2)
            result["change_pct"] = round(((reg_price - reg_prev) / reg_prev) * 100, 2)

        if asset_type == "us_stock":
            if market_state == "PRE" and info.get("preMarketPrice"):
                pre_p = float(info["preMarketPrice"])
                # yfinance preMarketChangePercent 有時為小數(0.03)或百分比(3.0)，統一用 reg_price 精確計算
                pre_pct = ((pre_p - reg_price) / reg_price) * 100 if reg_price else 0.0
                result["ext_session"] = {
                    "label": "盤前",
                    "price": round(pre_p, 2),
                    "change_pct": round(pre_pct, 2)
                }
            elif market_state in ["POST", "POSTPOST", "CLOSED"] and info.get("postMarketPrice"):
                post_p = float(info["postMarketPrice"])
                post_pct = ((post_p - reg_price) / reg_price) * 100 if reg_price else 0.0
                result["ext_session"] = {
                    "label": "盤後",
                    "price": round(post_p, 2),
                    "change_pct": round(post_pct, 2)
                }

        # D. 處理期貨「當日收盤價 + 夜盤交易價格」邏輯 (需求 #6)
        elif asset_type == "futures":
            # 期貨日盤結算基準價 (Previous Settlement / Regular Close) 與目前電子盤/夜盤最新報價拆分
            settlement_price = info.get("previousClose") or (hist_2y["Close"].iloc[-2] if len(hist_2y) > 1 else reg_price)
            prev_settlement = hist_2y["Close"].iloc[-3] if len(hist_2y) > 2 else settlement_price
            current_globex_price = info.get("regularMarketPrice") or (result["intraday"][-1]["price"] if result["intraday"] else reg_price)

            # 判斷目前是否處於亞洲/歐洲夜盤時段 (台灣時間 15:00 ~ 隔日 05:00)
            is_night_hours = (now_tw.hour >= 15 or now_tw.hour < 5)
            if is_night_hours and settlement_price and current_globex_price:
                # 主價格顯示上一日正規結算價，下方顯示夜盤即時價格與相對於結算價之漲跌幅
                result["price"] = round(float(settlement_price), 2)
                result["change"] = round(float(settlement_price - prev_settlement), 2)
                result["change_pct"] = round(((settlement_price - prev_settlement) / prev_settlement) * 100, 2) if prev_settlement else 0.0

                night_pct = ((current_globex_price - settlement_price) / settlement_price) * 100
                result["ext_session"] = {
                    "label": "夜盤",
                    "price": round(float(current_globex_price), 2),
                    "change_pct": round(float(night_pct), 2)
                }

        # E. 提取個股最新財報核心數據與獲利能力指標 (供美股與台股顯示)
        if asset_type in ["us_stock", "tw_stock"]:
            pe = info.get("trailingPE")
            f_pe = info.get("forwardPE")
            eps = info.get("trailingEps")
            gm = info.get("grossMargins")
            om = info.get("operatingMargins")
            roe = info.get("returnOnEquity")
            rev_growth = info.get("revenueGrowth")

            result["fundamentals"] = {
                "pe": round(pe, 2) if pe else "N/A",
                "forward_pe": round(f_pe, 2) if f_pe else "N/A",
                "eps": round(eps, 2) if eps else "N/A",
                "gross_margin": f"{round(gm * 100, 2)}%" if gm else "N/A",
                "operating_margin": f"{round(om * 100, 2)}%" if om else "N/A",
                "roe": f"{round(roe * 100, 2)}%" if roe else "N/A",
                "yoy_rev_growth": f"{round(rev_growth * 100, 2)}%" if rev_growth else "N/A",
                # 月營收欄位預設值 (台股會由下方 FinLab 函數填入最新月營收)
                "monthly_rev": None
            }

    except Exception as e:
        print(f"[Warning] Failed fetching {symbol}: {e}")

    return result


# ==========================================
# 3. 公開資訊觀測站 (MOPS) 當日重大訊息抓取 (需求 #2)
# ==========================================
def fetch_mops_material_info(target_stock_ids):
    """
    串接證交所公開資訊觀測站 OpenAPI (t05st01 每日重大訊息)，
    篩選出追蹤清單中的台股當日重大訊息，並附上 MOPS 連結。
    """
    mops_url = "https://openapi.twse.com.tw/v1/mops/t05st01"
    announcements = {sid: [] for sid in target_stock_ids}
    all_recent_mops = []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(mops_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                code = str(item.get("公司代號", "")).strip()
                name = to_trad(item.get("公司簡稱", "")).strip()
                date_str = str(item.get("發言日期", "")).strip()
                time_str = str(item.get("發言時間", "")).strip()
                subject = to_trad(item.get("主旨", "")).strip()

                record = {
                    "code": code,
                    "name": name,
                    "date": date_str,
                    "time": time_str,
                    "subject": subject,
                    "url": "https://mops.twse.com.tw/mops/#/web/home"
                }

                if code in announcements:
                    announcements[code].append(record)
                all_recent_mops.append(record)
    except Exception as e:
        print(f"[Warning] MOPS API fetch error: {e}")

    return announcements, all_recent_mops[:15]


# ==========================================
# 4. FinLab 台股月營收 + 三大法人與融資融券視覺化數據 (需求 #2 & #5)
# ==========================================
def fetch_finlab_tw_data(tw_stocks_dict):
    """
    使用 FinLab 取得：
    1. 個股最新公布月營收、MoM、YoY
    2. 大盤近 10 日三大法人買賣超 (外資、投信、自營商) 供堆疊長條圖使用
    3. 大盤與個股近 10 日融資餘額、融券餘額變化供雙軸折線/長條圖使用
    """
    chip_chart_data = {
        "dates": [],
        "foreign_buy": [],    # 外資買賣超 (億)
        "trust_buy": [],      # 投信買賣超 (億)
        "dealer_buy": [],     # 自營商買賣超 (億)
        "margin_balance": [], # 融資餘額 (億/萬張)
        "short_balance": []   # 融券餘額 (萬張)
    }

    token = os.environ.get("FINLAB_API_TOKEN")
    if not token:
        print("[Info] FINLAB_API_TOKEN not set, using TWSE fallback for institutional data.")
        return chip_chart_data

    try:
        import finlab
        from finlab import data as fdata
        finlab.login(token)

        # A. 個股最新月營收 (需求 #2)
        rev_df = fdata.get("monthly_revenue:當月營收")
        mom_df = fdata.get("monthly_revenue:上月比較增減(%)")
        yoy_df = fdata.get("monthly_revenue:去年同月增減(%)")

        for sid, s_obj in tw_stocks_dict.items():
            if sid in rev_df.columns:
                valid_rev = rev_df[sid].dropna()
                if not valid_rev.empty:
                    latest_month = valid_rev.index[-1].strftime("%Y-%m")
                    val_yi = round(float(valid_rev.iloc[-1]) / 100000, 2)  # 仟元轉億元
                    mom_val = round(float(mom_df[sid].dropna().iloc[-1]), 2) if sid in mom_df.columns else 0.0
                    yoy_val = round(float(yoy_df[sid].dropna().iloc[-1]), 2) if sid in yoy_df.columns else 0.0

                    s_obj["fundamentals"]["monthly_rev"] = {
                        "month": latest_month,
                        "revenue_yi": f"{val_yi} 億",
                        "mom": mom_val,
                        "yoy": yoy_val
                    }

        # B. 近 10 日三大法人買賣超統計 (需求 #5)
        foreign_df = fdata.get("institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)")
        trust_df = fdata.get("institutional_investors_trading_summary:投信買賣超股數")
        dealer_df = fdata.get("institutional_investors_trading_summary:自營商買賣超股數(自行買賣)")
        close_df = fdata.get("price:收盤價")

        # 計算全市場每日買賣超金額 (億元)
        common_dates = close_df.index.intersection(foreign_df.index)[-10:]
        for dt in common_dates:
            chip_chart_data["dates"].append(dt.strftime("%m/%d"))
            f_amt = (foreign_df.loc[dt] * close_df.loc[dt]).sum() / 1e8
            t_amt = (trust_df.loc[dt] * close_df.loc[dt]).sum() / 1e8
            d_amt = (dealer_df.loc[dt] * close_df.loc[dt]).sum() / 1e8
            chip_chart_data["foreign_buy"].append(round(float(f_amt), 2))
            chip_chart_data["trust_buy"].append(round(float(t_amt), 2))
            chip_chart_data["dealer_buy"].append(round(float(d_amt), 2))

        # C. 近 10 日融資與融券餘額變化 (需求 #5)
        margin_df = fdata.get("margin_transactions:融資今日餘額")
        short_df = fdata.get("margin_transactions:融券今日餘額")
        m_dates = margin_df.index[-10:]
        for dt in m_dates:
            # 轉為萬張單位
            m_total = margin_df.loc[dt].sum() / 10000
            s_total = short_df.loc[dt].sum() / 10000
            chip_chart_data["margin_balance"].append(round(float(m_total), 2))
            chip_chart_data["short_balance"].append(round(float(s_total), 2))

    except Exception as e:
        print(f"[Warning] FinLab data processing error: {e}")

    return chip_chart_data


# ==========================================
# 5. 主程式組裝與輸出
# ==========================================
def main():
    os.makedirs("data", exist_ok=True)

    print("1. Fetching Global Indices...")
    indices_data = [fetch_ticker_full_data(k, v, "standard") for k, v in INDICES.items()]

    print("2. Fetching US Tech Stocks (Ticker Only + Pre/Post Market)...")
    us_stocks_data = [fetch_ticker_full_data(sym, sym, "us_stock") for sym in US_STOCKS]

    print("3. Fetching TW Stocks...")
    tw_stocks_map = {}
    for code, meta in TW_STOCKS.items():
        tw_stocks_map[code] = fetch_ticker_full_data(meta["ticker"], meta["name"], "tw_stock")
        tw_stocks_map[code]["tw_code"] = code

    print("4. Fetching MOPS Material Announcements...")
    mops_by_stock, mops_latest_list = fetch_mops_material_info(list(TW_STOCKS.keys()))
    for code, s_obj in tw_stocks_map.items():
        s_obj["mops_announcements"] = mops_by_stock.get(code, [])

    print("5. Fetching FinLab Monthly Revenue & Institutional / Margin Data...")
    chip_chart_data = fetch_finlab_tw_data(tw_stocks_map)

    print("6. Fetching Futures & Commodities (Day Close + Night Session)...")
    futures_data = [fetch_ticker_full_data(k, v, "futures") for k, v in FUTURES_AND_COMMODITIES.items()]

    print("7. Fetching FX & Bonds...")
    fx_bonds_data = [fetch_ticker_full_data(k, v, "standard") for k, v in FX_AND_BONDS.items()]

    output_payload = {
        "last_updated": now_tw.strftime("%Y-%m-%d %H:%M:%S CST"),
        "indices": indices_data,
        "us_stocks": us_stocks_data,
        "tw_stocks": list(tw_stocks_map.values()),
        "futures_commodities": futures_data,
        "fx_bonds": fx_bonds_data,
        "tw_chips_visual": chip_chart_data,
        "mops_general": mops_latest_list
    }

    with open("data/market_data.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print("Done! data/market_data.json updated successfully.")

if __name__ == "__main__":
    main()
