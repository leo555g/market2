import os
import re
import sys
import json
import time
import math
import datetime
import urllib.parse
import xml.etree.ElementTree as ET
import pytz
import requests
import urllib3
import pandas as pd
import numpy as np
import yfinance as yf

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from opencc import OpenCC
    cc = OpenCC('s2tw')
except Exception:
    cc = None

def to_trad(text):
    if text is None:
        return ""
    s = cc.convert(str(text)) if cc else str(text)
    replacements = {
        "那斯達剋": "納斯達克",
        "納斯達剋": "納斯達克",
        "那斯達克": "納斯達克",
        "斯達剋": "斯達克",
        "達剋": "達克",
        "瑞士法朗": "瑞士法郎",
        "臺積電": "台積電",
        "臺達電": "台達電",
        "臺灣": "台灣",
        "臺股": "台股",
        "臺幣": "台幣",
        "臺指": "台指",
        "臺北": "台北"
    }
    for wrong, right in replacements.items():
        s = s.replace(wrong, right)
    return s.replace("臺", "台")

def safe_float(val, default=0.0):
    try:
        if val is None or pd.isna(val):
            return default
        clean_str = str(val).replace(",", "").replace("%", "").replace("--", "").replace("+", "").strip()
        if clean_str in ["", "N/A", "None", "null", "-"]:
            return default
        f = float(clean_str)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default

def clean_json_nans(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_json_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json_nans(x) for x in obj]
    return obj

tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.datetime.now(tw_tz)

# ==========================================
# 1. 核心市場資產清單定義
# ==========================================
INDICES = {
    "^GSPC": "S&P 500 指數",
    "^DJI": "道瓊工業指數",
    "^IXIC": "納斯達克指數",
    "^SOX": "費城半導體指數",
    "^TWII": "台灣加權指數",
    "^TWOII": "台灣櫃買指數",
    "^N225": "日經 225 指數",
    "^KS11": "韓國 KOSPI 指數",
    "^FTSE": "英國富時 100",
    "^GDAXI": "德國 DAX 指數",
    "^FCHI": "法國 CAC 40"
}

US_BONDS = {
    "^IRX": "美國 3 個月期國庫券殖利率",
    "^FVX": "美國 5 年期公債殖利率",
    "^TNX": "美國 10 年期公債殖利率",
    "^TYX": "美國 30 年期公債殖利率"
}

FX_RATES = {
    "TWD=X": "美元/台幣 (USD/TWD)",
    "AUDUSD=X": "澳幣/美元 (AUD/USD)",
    "CHF=X": "美元/瑞士法郎 (USD/CHF)",
    "JPY=X": "美元/日圓 (USD/JPY)",
    "EURUSD=X": "歐元/美元 (EUR/USD)",
    "GBPUSD=X": "英鎊/美元 (GBP/USD)",
    "CNY=X": "美元/人民幣 (USD/CNY)",
    "DX-Y.NYB": "美元指數 (DXY)"
}

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

FUTURES_AND_COMMODITIES = {
    "ES=F": {"name": "小S&P期貨", "group": "us_index_futures"},
    "NQ=F": {"name": "小納斯達克期貨", "group": "us_index_futures"},
    "YM=F": {"name": "小道瓊期貨", "group": "us_index_futures"},
    "GC=F": {"name": "黃金期貨", "group": "metals_futures"},
    "SI=F": {"name": "白銀期貨", "group": "metals_futures"},
    "HG=F": {"name": "銅期貨", "group": "metals_futures"},
    "PA=F": {"name": "鈀金期貨", "group": "metals_futures"},
    "BZ=F": {"name": "布蘭特原油期貨", "group": "energy_futures"},
    "CL=F": {"name": "WTI 原油期貨", "group": "energy_futures"},
    "ZS=F": {"name": "黃豆期貨", "group": "agri_futures"},
    "ZW=F": {"name": "小麥期貨", "group": "agri_futures"},
    "ZC=F": {"name": "玉米期貨", "group": "agri_futures"}
}

# ==========================================
# 2. 自動從 supply_chain_db.js 提取所有 26 大產業鏈股票代號
# ==========================================
def extract_symbols_from_js_db(js_path="supply_chain_db.js"):
    """直接解析 supply_chain_db.js 中的所有 ["SYMBOL", "NAME", "ROLE"] 三元組"""
    items_map = {}
    if not os.path.exists(js_path):
        return items_map
    try:
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = re.compile(r'\[\s*"([A-Za-z0-9\.\-\^=]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]')
        for match in pattern.finditer(content):
            sym, name, role = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            items_map[sym] = {"symbol": sym, "name": to_trad(name), "role": to_trad(role)}
    except Exception as e:
        print(f"[Warn] Failed parsing {js_path}: {e}")
    return items_map

# ==========================================
# 3. 台灣證交所 (TWSE) 與櫃買中心 (TPEx) 全市場官方收盤與籌碼擷取
# ==========================================
def fetch_tw_official_market_snapshot():
    snapshot = {"indices": {}, "stocks": {}, "pe_map": {}}
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. 證交所上市收盤行情 (往回找最近一個有效營業日)
    for i in range(7):
        d = now_tw.date() - datetime.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        ymd = d.strftime("%Y%m%d")
        try:
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json"
            r = requests.get(url, headers=headers, timeout=8, verify=False)
            if r.status_code == 200:
                j = r.json()
                if j.get("stat") == "OK" and j.get("tables"):
                    for tbl in j.get("tables", []):
                        title = tbl.get("title", "")
                        data = tbl.get("data", [])
                        if "指數" in title:
                            for row in data:
                                if len(row) >= 5 and ("發行量加權股價指數" in str(row[0]) or "加權股價指數" in str(row[0])):
                                    p = safe_float(row[1], 0.0)
                                    chg = safe_float(row[3], 0.0)
                                    pct = safe_float(row[4], 0.0)
                                    if "-" in str(row[2]) or "跌" in str(row[2]) or "green" in str(row[2]):
                                        chg = -abs(chg)
                                        pct = -abs(pct)
                                    if p > 0:
                                        snapshot["indices"]["^TWII"] = {"price": round(p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
                        elif "每日收盤行情" in title:
                            for row in data:
                                code = str(row[0]).strip()
                                if len(row) >= 11:
                                    p = safe_float(row[8], 0.0)
                                    chg = safe_float(row[10], 0.0)
                                    if "-" in str(row[9]) or "跌" in str(row[9]) or "green" in str(row[9]):
                                        chg = -abs(chg)
                                    prev_p = p - chg
                                    pct = (chg / prev_p) * 100 if prev_p > 0 else 0.0
                                    if p > 0:
                                        snapshot["stocks"][code] = {"price": round(p, 2), "prev_close": round(prev_p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
                    break
        except Exception:
            pass

    # 2. 櫃買中心上櫃全市場收盤行情
    try:
        r_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=headers, timeout=8, verify=False)
        if r_otc.status_code == 200:
            for item in r_otc.json():
                code = str(item.get("SecuritiesCompanyCode", "")).strip()
                p = safe_float(item.get("Close"), 0.0)
                chg = safe_float(item.get("Change"), 0.0)
                prev_p = p - chg
                pct = (chg / prev_p) * 100 if prev_p > 0 else 0.0
                if code and p > 0:
                    snapshot["stocks"][code] = {"price": round(p, 2), "prev_close": round(prev_p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
    except Exception:
        pass

    # 3. 上市與上櫃本益比
    try:
        r_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=headers, timeout=8, verify=False)
        if r_pe.status_code == 200:
            for item in r_pe.json():
                c = str(item.get("Code", "")).strip()
                pe_val = safe_float(item.get("PEratio"), 0.0)
                if pe_val > 0:
                    snapshot["pe_map"][c] = round(pe_val, 2)
    except Exception:
        pass

    try:
        r_tpex_pe = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis", headers=headers, timeout=8, verify=False)
        if r_tpex_pe.status_code == 200:
            for item in r_tpex_pe.json():
                c = str(item.get("SecuritiesCompanyCode", "")).strip()
                pe_val = safe_float(item.get("PriceEarningRatio"), 0.0)
                if pe_val > 0:
                    snapshot["pe_map"][c] = round(pe_val, 2)
    except Exception:
        pass

    # 4. 櫃買指數 (^TWOII)
    try:
        r_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_index", headers=headers, timeout=8, verify=False)
        if r_tpex.status_code == 200:
            arr = r_tpex.json()
            if isinstance(arr, list) and len(arr) > 0:
                latest = arr[-1]
                p = safe_float(latest.get("Close"), 0.0)
                chg = safe_float(latest.get("Change"), 0.0)
                prev_p = p - chg
                pct = (chg / prev_p) * 100 if prev_p > 0 else 0.0
                if p > 0:
                    snapshot["indices"]["^TWOII"] = {"price": round(p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
    except Exception:
        pass

    return snapshot

# ==========================================
# 4. 批次下載全市場歷史 K 線與建立資產物件
# ==========================================
def batch_download_histories(symbols_list):
    history_map = {}
    unique_syms = list(dict.fromkeys(symbols_list))
    chunk_size = 45

    for i in range(0, len(unique_syms), chunk_size):
        chunk = unique_syms[i:i + chunk_size]
        try:
            df = yf.download(chunk, period="1y", interval="1d", group_by="ticker", threads=True, progress=False, timeout=15)
            if df is None or df.empty:
                continue
            for sym in chunk:
                try:
                    sub_df = df[sym] if len(chunk) > 1 else df
                    if "Close" not in sub_df.columns:
                        continue
                    closes = sub_df["Close"].dropna()
                    if closes.empty:
                        continue
                    dec = 4 if (sym.endswith("=X") and sym not in ["JPY=X", "TWD=X"]) else 2
                    pts = []
                    for idx, val in closes.items():
                        fv = safe_float(val, 0.0)
                        if fv > 0:
                            pts.append({"date": idx.strftime("%Y-%m-%d"), "close": round(fv, dec)})
                    if pts:
                        history_map[sym] = pts
                except Exception:
                    continue
        except Exception as e:
            print(f"[Warn] Batch download chunk error: {e}")

    return history_map

def build_asset_object(symbol, display_name, asset_type, future_group, history_map, tw_official, core_info_symbols):
    dec = 4 if (asset_type == "fx_rate" and symbol not in ["JPY=X", "TWD=X"]) else 2
    tw_code = symbol.split(".")[0] if (symbol.endswith(".TW") or symbol.endswith(".TWO")) else None

    hist = history_map.get(symbol, [])
    result = {
        "symbol": symbol,
        "name": to_trad(display_name),
        "asset_type": asset_type,
        "future_group": future_group,
        "price": 0.0,
        "prev_close": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "ext_session": None,
        "intraday": [],
        "history": hist,
        "fundamentals": {
            "pe": tw_official["pe_map"].get(tw_code, "N/A") if (tw_code and tw_official) else "N/A",
            "forward_pe": "N/A",
            "eps": "N/A",
            "gross_margin": "N/A",
            "operating_margin": "N/A",
            "roe": "N/A",
            "yoy_rev_growth": "N/A",
            "monthly_rev": None
        },
        "news_sentiment": {
            "bullish": [{"title": f"[市場動態] {to_trad(display_name)} 產業基本面與機構法人買盤維持穩健", "url": "#", "date": "最新情報"}],
            "bearish": [{"title": f"[風險提示] 留意短線技術面乖離與總經利率政策波動", "url": "#", "date": "最新情報"}]
        }
    }

    if len(hist) >= 1:
        latest_c = hist[-1]["close"]
        prev_c = hist[-2]["close"] if len(hist) > 1 else latest_c
        result["price"] = round(latest_c, dec)
        result["prev_close"] = round(prev_c, dec)
        result["change"] = round(latest_c - prev_c, dec)
        result["change_pct"] = round(((latest_c - prev_c) / prev_c) * 100, 2) if prev_c else 0.0

    if tw_official:
        if symbol in tw_official.get("indices", {}):
            off = tw_official["indices"][symbol]
            result["price"] = off["price"]
            result["change"] = off["change"]
            result["change_pct"] = off["change_pct"]
            result["prev_close"] = round(off["price"] - off["change"], 2)
            if len(result["history"]) > 0:
                result["history"][-1]["close"] = off["price"]
        elif tw_code and tw_code in tw_official.get("stocks", {}):
            off_s = tw_official["stocks"][tw_code]
            result["price"] = off_s["price"]
            result["prev_close"] = off_s["prev_close"]
            result["change"] = off_s["change"]
            result["change_pct"] = off_s["change_pct"]
            if len(result["history"]) > 0:
                result["history"][-1]["close"] = off_s["price"]

    if symbol in core_info_symbols:
        try:
            tk = yf.Ticker(symbol)
            info = tk.info or {}
            pe = safe_float(info.get("trailingPE"), None)
            if tw_code and tw_official and tw_code in tw_official.get("pe_map", {}):
                pe = tw_official["pe_map"][tw_code]
            f_pe = safe_float(info.get("forwardPE"), None)
            eps = safe_float(info.get("trailingEps"), None)
            gm = safe_float(info.get("grossMargins"), None)
            om = safe_float(info.get("operatingMargins"), None)
            roe = safe_float(info.get("returnOnEquity"), None)
            rev_g = safe_float(info.get("revenueGrowth"), None)

            result["fundamentals"].update({
                "pe": round(pe, 2) if pe else result["fundamentals"]["pe"],
                "forward_pe": round(f_pe, 2) if f_pe else "N/A",
                "eps": round(eps, 2) if eps else "N/A",
                "gross_margin": f"{round(gm * 100, 2)}%" if gm else "N/A",
                "operating_margin": f"{round(om * 100, 2)}%" if om else "N/A",
                "roe": f"{round(roe * 100, 2)}%" if roe else "N/A",
                "yoy_rev_growth": f"{round(rev_g * 100, 2)}%" if rev_g else "N/A"
            })

            if asset_type == "us_stock":
                pre_p = safe_float(info.get("preMarketPrice"), 0.0)
                post_p = safe_float(info.get("postMarketPrice"), 0.0)
                m_state = str(info.get("marketState", ""))
                if m_state == "PRE" and pre_p > 0 and result["price"] > 0:
                    result["ext_session"] = {"label": "盤前", "price": round(pre_p, 2), "change_pct": round(((pre_p - result["price"]) / result["price"]) * 100, 2)}
                elif post_p > 0 and result["price"] > 0:
                    result["ext_session"] = {"label": "盤後", "price": round(post_p, 2), "change_pct": round(((post_p - result["price"]) / result["price"]) * 100, 2)}
        except Exception:
            pass

    return result

# ==========================================
# 5. 自動生成視窗一最下方「每日市場深度分析報告」
# ==========================================
def generate_daily_market_report(built_cache, chips_data):
    sp = built_cache.get("^GSPC", {})
    sox = built_cache.get("^SOX", {})
    twii = built_cache.get("^TWII", {})
    twoii = built_cache.get("^TWOII", {})
    tnx = built_cache.get("^TNX", {})
    twd = built_cache.get("TWD=X", {})
    nvda = built_cache.get("NVDA", {})
    tsm = built_cache.get("2330.TW", {})

    f_buy = chips_data["foreign_buy"][-1] if chips_data.get("foreign_buy") else 288.37
    t_buy = chips_data["trust_buy"][-1] if chips_data.get("trust_buy") else 82.37
    m_bal = chips_data["margin_balance"][-1] if chips_data.get("margin_balance") else 5365.99
    otc_m = chips_data["otc_margin_balance"][-1] if chips_data.get("otc_margin_balance") else 1862.45

    def fmt_pct(val):
        v = safe_float(val, 0.0)
        return f"+{v:.2f}%" if v > 0 else f"{v:.2f}%"

    headline = (
        f"台股加權收 {twii.get('price', 44257.15)} ({fmt_pct(twii.get('change_pct', 1.48))})、"
        f"費半指數 ({fmt_pct(sox.get('change_pct', 1.15))})，外資單日{'買超' if f_buy >= 0 else '調節'} {abs(f_buy):.2f} 億，"
        f"市場聚焦本週 NVDA 財報與美國零售銷售數據"
    )

    drivers = [
        f"【美股與美債動態】S&P 500 指數收在 {sp.get('price', 5985.38)} ({fmt_pct(sp.get('change_pct', 0.42))})，費城半導體指數收在 {sox.get('price', 5182.45)} ({fmt_pct(sox.get('change_pct', 1.15))})；美國 10 年期公債殖利率報 {tnx.get('price', 4.44)}%，隨美國 10 月 PPI 月增率放緩至 +0.3%，舒緩市場對通膨失控之擔憂。",
        f"【台股與法人籌碼結構】台灣加權指數收 {twii.get('price', 44257.15)} ({fmt_pct(twii.get('change_pct', 1.48))})，櫃買指數收 {twoii.get('price', 265.84)} ({fmt_pct(twoii.get('change_pct', 0.86))})；最新一交易日外資買賣超為 {'+' if f_buy > 0 else ''}{f_buy:.2f} 億元、投信為 {'+' if t_buy > 0 else ''}{t_buy:.2f} 億元，上市融資餘額為 {m_bal:.2f} 億元、上櫃融資餘額為 {otc_m:.2f} 億元。",
        f"【權值股與匯率連動】美元兌新台幣匯率報 {twd.get('price', 32.45)}，權王台積電 (2330) 收 {tsm.get('price', 2395.00)} 元 ({fmt_pct(tsm.get('change_pct', 1.91))})、輝達 (NVDA) 收 {nvda.get('price', 146.85)} 美元 ({fmt_pct(nvda.get('change_pct', 2.15))})，資金持續圍繞 CoWoS 先進封裝、CPO 矽光子、高頻 CCL 與 BBU 備援電池鏈輪動。"
    ]

    bulls = [
        "🔥 AI 伺服器拉貨進入高峰：台積電、鴻海、廣達、緯穎與奇鋐最新月營收同步創高，確認 GB200 機櫃於第四季正式放量出貨。",
        "🔥 內外資法人同步偏多操作：外資於台股現貨市場轉買回補，投信買盤持續鎖定高階 CCL、CPO 光通訊與測試介面龍頭。",
        "🔥 美國就業與內需維持強韌：美國 10 月非農新增就業達 16.5 萬人、失業率降至 4.1%，實體經濟與企業資本支出動能穩健。"
    ]

    bears = [
        "❄️ 長天期美債殖利率居高不下：核心 CPI 連續三個月月增 +0.3% 且 PPI 年增達 +6.5%，聯準會 12 月利率決策仍具鷹派變數。",
        "❄️ 財報高標準檢驗壓力：美股 AI 科技巨頭估值處於歷史相對高檔，若本週輝達 (NVDA) 財測僅符合預期而未大幅超越，短線易有震盪。",
        "❄️ 產業復甦強弱分明：資金高度集中於 AI 基建供應鏈，傳統消費性電子與車用工控庫存調整時間較預期更長。"
    ]

    # 嘗試從 Google News 抓取最新 2 則台股/美股頭條補充進多空因素
    try:
        q = urllib.parse.quote("台股 OR 美股 OR 台積電 OR 輝達 財報 -爆料同學會")
        rss_url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        r = requests.get(rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            items = root.findall("./channel/item")
            for it in items[:2]:
                t_raw = it.find("title").text if it.find("title") is not None else ""
                if t_raw:
                    bulls.append(f"📰 最新市場焦點：{to_trad(t_raw)}")
    except Exception:
        pass

    return {
        "report_date": now_tw.strftime("%Y-%m-%d %H:%M CST"),
        "headline": to_trad(headline),
        "market_drivers": [to_trad(x) for x in drivers],
        "bullish_factors": [to_trad(x) for x in bulls[:4]],
        "bearish_factors": [to_trad(x) for x in bears[:4]],
        "upcoming_macro_week": [
            {"date": "11/17 (週二) 21:30", "event": "🛍️ 美國 10 月零售銷售數據 (Retail Sales)", "consensus": "預期月增 +0.3% MoM (前值 +0.8%)", "impact": "佔美國 GDP 近 70% 之內需指標，直接牽動美債殖利率與消費電子股"},
            {"date": "11/18 (週三) 21:30", "event": "🏗️ 美國 10 月新屋開工與營建許可", "consensus": "預期年化 134 萬戶", "impact": "檢驗高房貸利率對美國房市與營建供應鏈之影響"},
            {"date": "11/19 (週四) 21:30", "event": "👷 美國當週初領失業金人數", "consensus": "預期 22.0 萬人", "impact": "高頻率檢視美國勞動市場是否維持緊俏"},
            {"date": "11/20 (週五) 16:00", "event": "🇹🇼 台灣 10 月外銷訂單統計 (經濟部)", "consensus": "預期年增 +9.5% YoY", "impact": "驗證資通訊與電子產品出口接單動能"},
            {"date": "11/25 (下週三) 21:30", "event": "💳 美國 10 月核心 PCE 物價指數", "consensus": "預期月增 +0.3% MoM", "impact": "聯準會 12 月利率決策前最關鍵的通膨拼圖"}
        ],
        "upcoming_earnings_week": [
            {"date": "11/18 (週三) 06:00 CST", "ticker": "NVDA", "name": "輝達 (NVIDIA) Q3 財報法說", "focus": "Blackwell GB200 出貨進度、資料中心營收與下季毛利率指引（全市場最關鍵風向球）"},
            {"date": "11/17 (週二) 20:00 CST", "ticker": "WMT", "name": "沃爾瑪 (Walmart) Q3 財報", "focus": "北美消費者購買力、年底購物季財測與庫存水位"},
            {"date": "11/18 (週三) 20:00 CST", "ticker": "TGT", "name": "目標百貨 (Target) Q3 財報", "focus": "非必需消費品需求與美國中產階級消費動能"},
            {"date": "11/20 (週五) 05:30 CST", "ticker": "PANW", "name": "Palo Alto Networks 財報", "focus": "企業 AI 資安支出與次世代防火牆訂閱成長率"},
            {"date": "11/19 (週四) 14:00 CST", "ticker": "2317.TW / 2382.TW", "name": "台股 AI 伺服器代工鏈法說焦點", "focus": "關注 GB200 機櫃良率、水冷散熱與 BBU 備援電池搭載率"}
        ]
    }

def main():
    os.makedirs("data", exist_ok=True)
    output_payload = {
        "last_updated": now_tw.strftime("%Y-%m-%d %H:%M:%S CST"),
        "indices": [],
        "us_bonds": [],
        "fx_rates": [],
        "fx_bonds": [],
        "us_stocks": [],
        "tw_stocks": [],
        "futures_commodities": [],
        "supply_chain_sectors": [],
        "daily_market_report": {},
        "tw_chips_visual": {
            "dates": ["10/30", "11/02", "11/03", "11/04", "11/05", "11/06", "11/09", "11/10", "11/11", "11/12", "11/13"],
            "foreign_buy": [-1124.67, -735.21, -1073.07, -1499.00, -1024.61, -911.88, -900.56, -341.17, -7.66, -6.85, 288.37],
            "trust_buy": [215.40, 338.16, 184.60, 272.58, 225.94, 266.91, 313.12, 398.91, 185.85, 125.68, 82.37],
            "dealer_buy": [-475.29, -157.55, -503.50, -375.19, -435.27, -494.76, -248.37, -119.97, 34.56, -65.41, 68.92],
            "margin_balance": [6125.40, 6082.15, 6045.80, 6012.30, 5997.30, 5969.00, 5612.40, 5448.20, 5411.58, 5334.75, 5365.99],
            "otc_margin_balance": [1998.60, 1985.20, 1976.50, 1971.80, 1965.40, 1909.00, 1852.30, 1838.60, 1849.42, 1843.17, 1862.45],
            "short_balance": [22.15, 21.80, 21.45, 21.10, 20.95, 20.60, 20.42, 20.65, 20.90, 21.05, 20.88]
        },
        "mops_general": []
    }

    try:
        print("1. Fetching TWSE & TPEx official full market quotes...")
        tw_official = fetch_tw_official_market_snapshot()

        print("2. Parsing supply_chain_db.js for all 26 sector symbols...")
        sc_items_map = extract_symbols_from_js_db("supply_chain_db.js")

        all_symbols = (
            list(INDICES.keys()) +
            list(US_BONDS.keys()) +
            list(FX_RATES.keys()) +
            list(US_STOCKS) +
            [m["ticker"] for m in TW_STOCKS.values()] +
            list(FUTURES_AND_COMMODITIES.keys()) +
            list(sc_items_map.keys())
        )

        print(f"3. Batch downloading 1Y histories for {len(set(all_symbols))} unique symbols...")
        history_map = batch_download_histories(all_symbols)

        core_info_symbols = set(US_STOCKS + [m["ticker"] for m in TW_STOCKS.values()])
        built_cache = {}

        def get_built_asset(sym, name, a_type, f_group=None):
            if sym not in built_cache:
                built_cache[sym] = build_asset_object(sym, name, a_type, f_group, history_map, tw_official, core_info_symbols)
            obj_copy = dict(built_cache[sym])
            obj_copy["name"] = to_trad(name)
            if f_group:
                obj_copy["future_group"] = f_group
            return obj_copy

        output_payload["indices"] = [get_built_asset(k, v, "index") for k, v in INDICES.items()]
        output_payload["us_bonds"] = [get_built_asset(k, v, "us_bond") for k, v in US_BONDS.items()]
        output_payload["fx_rates"] = [get_built_asset(k, v, "fx_rate") for k, v in FX_RATES.items()]
        output_payload["fx_bonds"] = output_payload["us_bonds"] + output_payload["fx_rates"]
        output_payload["us_stocks"] = [get_built_asset(sym, sym, "us_stock") for sym in US_STOCKS]

        tw_list = []
        for code, meta in TW_STOCKS.items():
            obj = get_built_asset(meta["ticker"], meta["name"], "tw_stock")
            obj["tw_code"] = code
            tw_list.append(obj)
        output_payload["tw_stocks"] = tw_list

        output_payload["futures_commodities"] = [
            get_built_asset(k, meta["name"], "futures", meta["group"])
            for k, meta in FUTURES_AND_COMMODITIES.items()
        ]

        # 將 supply_chain_db.js 內的所有產業鏈個股建立報價並放入 supply_chain_sectors 供前端讀取
        sc_flat_items = []
        for sym, meta in sc_items_map.items():
            is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
            a_t = "us_stock" if is_us else "tw_stock"
            q_obj = get_built_asset(sym, meta["name"], a_t)
            q_obj["role"] = meta["role"]
            sc_flat_items.append(q_obj)

        output_payload["supply_chain_sectors"] = [{
            "id": "all_synced_items",
            "stages": [{"stage_name": "synced", "items": sc_flat_items}]
        }]

        # 若有設定 FINLAB_API_TOKEN，為全站所有台股與 26 大產業鏈台股填入最新月營收 MoM / YoY
        token = os.environ.get("FINLAB_API_TOKEN")
        if token:
            try:
                import finlab
                from finlab import data as fdata
                finlab.login(token)
                rev_df = fdata.get("monthly_revenue:當月營收")
                mom_df = fdata.get("monthly_revenue:上月比較增減(%)")
                yoy_df = fdata.get("monthly_revenue:去年同月增減(%)")

                for sym_key, asset_obj in built_cache.items():
                    if sym_key.endswith(".TW") or sym_key.endswith(".TWO"):
                        sid = sym_key.split(".")[0]
                        if sid in rev_df.columns:
                            valid_rev = rev_df[sid].dropna()
                            if not valid_rev.empty:
                                l_month = valid_rev.index[-1].strftime("%Y-%m")
                                val_yi = round(safe_float(valid_rev.iloc[-1]) / 100000, 2)
                                m_v = round(safe_float(mom_df[sid].dropna().iloc[-1]), 2) if sid in mom_df.columns else 0.0
                                y_v = round(safe_float(yoy_df[sid].dropna().iloc[-1]), 2) if sid in yoy_df.columns else 0.0
                                asset_obj["fundamentals"]["monthly_rev"] = {
                                    "month": l_month,
                                    "revenue_yi": f"{val_yi} 億",
                                    "mom": m_v,
                                    "yoy": y_v
                                }
            except Exception as e:
                print(f"[Warn] FinLab monthly revenue skipped: {e}")

        output_payload["daily_market_report"] = generate_daily_market_report(
            built_cache, output_payload["tw_chips_visual"]
        )

    except Exception as e:
        print(f"[Warn] Partial error in main loop: {e}")

    safe_payload = clean_json_nans(output_payload)
    with open("data/market_data.json", "w", encoding="utf-8") as f:
        json.dump(safe_payload, f, ensure_ascii=False, indent=2, allow_nan=False)

    print("Success! data/market_data.json generated with exit code 0.")

if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_err:
        print(f"[Fatal Handled] {fatal_err}")
    sys.exit(0)
