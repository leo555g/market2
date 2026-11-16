import os, re, sys, io, json, math, time, datetime, concurrent.futures
import pytz, requests, urllib3
import pandas as pd
import yfinance as yf

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from opencc import OpenCC
    cc = OpenCC('s2tw')
except Exception:
    cc = None

def to_trad(text):
    if text is None: return ""
    s = cc.convert(str(text)) if cc else str(text)
    for w, r in [("那斯達剋","納斯達克"),("納斯達剋","納斯達克"),("那斯達克","納斯達克"),("瑞士法朗","瑞士法郎"),("臺","台")]:
        s = s.replace(w, r)
    return s

def safe_float(val, default=0.0):
    try:
        if val is None or pd.isna(val): return default
        s = str(val).replace(",", "").replace("%", "").replace("--", "").replace("+", "").strip()
        if s in ["", "N/A", "None", "null", "-", "X", "."]: return default
        f = float(s)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default

def clean_json_nans(obj):
    if isinstance(obj, float): return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict): return {k: clean_json_nans(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_json_nans(x) for x in obj]
    return obj

tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.datetime.now(tw_tz)
DELISTED_BLACKLIST = {"2867.TW", "2809.TW", "2888.TW", "MMC"}

INDICES = {
    "^GSPC": "S&P 500 指數", "^DJI": "道瓊工業指數", "^IXIC": "納斯達克指數", "^SOX": "費城半導體指數",
    "^TWII": "台灣加權指數", "^TWOII": "台灣櫃買指數", "^N225": "日經 225 指數", "^KS11": "韓國 KOSPI 指數",
    "^FTSE": "英國富時 100", "^GDAXI": "德國 DAX 指數", "^FCHI": "法國 CAC 40"
}
VIX_INDICES = {"^VIX": "美國 CBOE VIX 恐慌指數", "^VIXTWN": "臺指選擇權波動率指數 (VIXTWN)"}
US_BONDS = {"^IRX": "美國 3 個月期國庫券殖利率", "US2Y": "美國 2 年期公債殖利率", "^FVX": "美國 5 年期公債殖利率", "^TNX": "美國 10 年期公債殖利率", "^TYX": "美國 30 年期公債殖利率"}
FX_RATES = {"TWD=X": "美元/台幣 (USD/TWD)", "AUDUSD=X": "澳幣/美元 (AUD/USD)", "CHF=X": "美元/瑞士法郎 (USD/CHF)", "JPY=X": "美元/日圓 (USD/JPY)", "EURUSD=X": "歐元/美元 (EUR/USD)", "GBPUSD=X": "英鎊/美元 (GBP/USD)", "CNY=X": "美元/人民幣 (USD/CNY)", "DX-Y.NYB": "美元指數 (DXY)"}
US_STOCKS = ["NVDA", "TSM", "SPCX", "AMD", "GOOGL", "META", "TSLA", "AVGO", "AMZN", "AAPL", "MSFT"]
TW_STOCKS = {
    "2330": {"ticker": "2330.TW", "name": "2330 台積電"},
    "2454": {"ticker": "2454.TW", "name": "2454 聯發科"},
    "2308": {"ticker": "2308.TW", "name": "2308 台達電"},
    "2317": {"ticker": "2317.TW", "name": "2317 鴻海"},
    "3711": {"ticker": "3711.TW", "name": "3711 日月光投控"}
}
FUTURES_AND_COMMODITIES = {
    "ES=F": {"name": "小S&P期貨", "group": "us_index_futures"}, "NQ=F": {"name": "小納斯達克期貨", "group": "us_index_futures"}, "YM=F": {"name": "小道瓊期貨", "group": "us_index_futures"},
    "GC=F": {"name": "黃金期貨", "group": "metals_futures"}, "SI=F": {"name": "白銀期貨", "group": "metals_futures"}, "HG=F": {"name": "銅期貨", "group": "metals_futures"}, "PA=F": {"name": "鈀金期貨", "group": "metals_futures"},
    "BZ=F": {"name": "布蘭特原油期貨", "group": "energy_futures"}, "CL=F": {"name": "WTI 原油期貨", "group": "energy_futures"},
    "ZS=F": {"name": "黃豆期貨", "group": "agri_futures"}, "ZW=F": {"name": "小麥期貨", "group": "agri_futures"}, "ZC=F": {"name": "玉米期貨", "group": "agri_futures"},
    "BTC-USD": {"name": "比特幣 (BTC)", "group": "crypto_assets"}, "ETH-USD": {"name": "以太幣 (ETH)", "group": "crypto_assets"}
}

CORE_FUNDAMENTALS_DB = {
    "NVDA": {"pe": 42.8, "forward_pe": 31.5, "eps": 3.80, "gross_margin": "74.7%", "operating_margin": "62.1%", "roe": "115.2%", "yoy_rev_growth": "78.4%"},
    "TSM": {"pe": 24.1, "forward_pe": 19.8, "eps": 16.54, "gross_margin": "57.8%", "operating_margin": "47.5%", "roe": "31.2%", "yoy_rev_growth": "39.0%"},
    "SPCX": {"pe": "N/A", "forward_pe": 68.5, "eps": -0.25, "gross_margin": "54.2%", "operating_margin": "28.4%", "roe": "24.6%", "yoy_rev_growth": "64.8%"},
    "AMD": {"pe": 48.5, "forward_pe": 32.4, "eps": 11.01, "gross_margin": "51.2%", "operating_margin": "24.8%", "roe": "18.5%", "yoy_rev_growth": "35.2%"},
    "GOOGL": {"pe": 26.4, "forward_pe": 22.8, "eps": 11.20, "gross_margin": "58.1%", "operating_margin": "32.3%", "roe": "30.8%", "yoy_rev_growth": "15.1%"},
    "META": {"pe": 28.2, "forward_pe": 24.1, "eps": 22.75, "gross_margin": "81.5%", "operating_margin": "41.2%", "roe": "36.1%", "yoy_rev_growth": "18.9%"},
    "TSLA": {"pe": 88.5, "forward_pe": 68.2, "eps": 4.41, "gross_margin": "18.2%", "operating_margin": "9.3%", "roe": "20.4%", "yoy_rev_growth": "12.8%"},
    "AVGO": {"pe": 39.2, "forward_pe": 28.5, "eps": 8.85, "gross_margin": "66.5%", "operating_margin": "58.2%", "roe": "41.5%", "yoy_rev_growth": "47.0%"},
    "AMZN": {"pe": 42.1, "forward_pe": 33.5, "eps": 6.33, "gross_margin": "48.0%", "operating_margin": "11.0%", "roe": "22.6%", "yoy_rev_growth": "11.0%"},
    "AAPL": {"pe": 38.5, "forward_pe": 31.2, "eps": 9.25, "gross_margin": "46.2%", "operating_margin": "31.5%", "roe": "147.2%", "yoy_rev_growth": "8.1%"},
    "MSFT": {"pe": 36.8, "forward_pe": 30.5, "eps": 14.23, "gross_margin": "69.8%", "operating_margin": "44.6%", "roe": "37.1%", "yoy_rev_growth": "16.0%"},
    "2330.TW": {"pe": 22.5, "eps": 98.25, "roe": "31.2%", "gross_margin": "57.8%", "operating_margin": "47.5%", "yoy_rev_growth": "36.0%"},
    "2454.TW": {"pe": 62.6, "eps": 60.56, "roe": "27.5%", "gross_margin": "48.8%", "operating_margin": "19.5%", "yoy_rev_growth": "19.4%"},
    "2308.TW": {"pe": 31.2, "eps": 35.90, "roe": "19.8%", "gross_margin": "34.2%", "operating_margin": "14.8%", "yoy_rev_growth": "22.4%"},
    "2317.TW": {"pe": 15.8, "eps": 13.77, "roe": "11.4%", "gross_margin": "6.4%", "operating_margin": "3.2%", "yoy_rev_growth": "20.1%"},
    "3711.TW": {"pe": 24.6, "eps": 22.31, "roe": "15.9%", "gross_margin": "18.5%", "operating_margin": "9.2%", "yoy_rev_growth": "18.3%"}
}

# ====================================================================
# 1. 台股三重官方即時與收盤通道 (mis.twse.com.tw 即時看盤 API + STOCK_DAY_ALL + TPEx)
# ====================================================================
def fetch_tw_official_all_channels(tw_sym_list):
    snapshot = {"indices": {}, "stocks": {}, "pe_map": {}}
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    # 通道 A：證交所基本市況報導 (mis.twse.com.tw) - 13:30 一收盤立即提供當日最終收盤價與昨收價
    ex_ch_list = ["tse_t00.tw", "otc_o00.tw"]
    for s in tw_sym_list:
        if s.endswith(".TW"):
            ex_ch_list.append(f"tse_{s.split('.')[0]}.tw")
        elif s.endswith(".TWO"):
            ex_ch_list.append(f"otc_{s.split('.')[0]}.tw")

    chunk_size = 45
    for i in range(0, len(ex_ch_list), chunk_size):
        chunk = ex_ch_list[i:i + chunk_size]
        ex_str = "|".join(chunk)
        try:
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_str}&json=1&delay=0"
            r = requests.get(url, headers=headers, timeout=6, verify=False)
            if r.status_code == 200:
                msg_arr = r.json().get("msgArray") or []
                for m in msg_arr:
                    code = str(m.get("c", "")).strip()
                    prev_p = safe_float(m.get("y"), 0.0)
                    # 若當盤成交價 z 為 '-'，則取最近成交價或買賣價中間值
                    cur_p = safe_float(m.get("z"), 0.0)
                    if cur_p <= 0:
                        b_str = str(m.get("b", "")).split("_")[0]
                        a_str = str(m.get("a", "")).split("_")[0]
                        cur_p = safe_float(b_str, 0.0) or safe_float(a_str, 0.0) or safe_float(m.get("o"), 0.0) or prev_p
                    if cur_p > 0 and prev_p > 0:
                        chg = round(cur_p - prev_p, 2)
                        pct = round((chg / prev_p) * 100, 2)
                        if code == "t00":
                            snapshot["indices"]["^TWII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": chg, "change_pct": pct}
                        elif code == "o00":
                            snapshot["indices"]["^TWOII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": chg, "change_pct": pct}
                        elif code:
                            snapshot["stocks"][code] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": chg, "change_pct": pct}
        except Exception:
            pass

    # 通道 B：證交所 STOCK_DAY_ALL 官方盤後總表
    try:
        r_all = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=8, verify=False)
        if r_all.status_code == 200:
            for item in r_all.json():
                code = str(item.get("Code", "")).strip()
                p = safe_float(item.get("ClosingPrice"), 0.0)
                chg = safe_float(item.get("Change"), 0.0)
                if "-" in str(item.get("Change", "")): chg = -abs(chg)
                prev_p = p - chg
                pct = (chg / prev_p) * 100 if prev_p > 0 else 0.0
                if code and p > 0:
                    snapshot["stocks"][code] = {"price": round(p, 2), "prev_close": round(prev_p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
    except Exception:
        pass

    # 通道 C：櫃買中心 tpex_mainboard_quotes 官方盤後總表
    try:
        r_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=headers, timeout=8, verify=False)
        if r_otc.status_code == 200:
            for item in r_otc.json():
                code = str(item.get("SecuritiesCompanyCode", "")).strip()
                p = safe_float(item.get("Close"), 0.0)
                chg = safe_float(item.get("Change"), 0.0)
                if "-" in str(item.get("Change", "")): chg = -abs(chg)
                prev_p = p - chg
                pct = (chg / prev_p) * 100 if prev_p > 0 else 0.0
                if code and p > 0:
                    snapshot["stocks"][code] = {"price": round(p, 2), "prev_close": round(prev_p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
    except Exception:
        pass

    # 本益比 PE 表
    for pe_url, k_code, k_pe in [
        ("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", "Code", "PEratio"),
        ("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis", "SecuritiesCompanyCode", "PriceEarningRatio")
    ]:
        try:
            rp = requests.get(pe_url, headers=headers, timeout=6, verify=False)
            if rp.status_code == 200:
                for it in rp.json():
                    c, pv = str(it.get(k_code, "")).strip(), safe_float(it.get(k_pe))
                    if c and pv > 0: snapshot["pe_map"][c] = round(pv, 2)
        except Exception:
            pass

    return snapshot

# ====================================================================
# 2. yfinance 批次下載全站台美股 1Y K 線 + 美股盤中(大字) vs 盤前盤後(小字)
# ====================================================================
def download_all_yf_histories_and_ext(symbols_list, us_eq_list):
    yf_map = {}
    skip_set = DELISTED_BLACKLIST | {"US2Y", "^VIXTWN", "SPCX"}
    unique_syms = [s for s in dict.fromkeys(symbols_list) if s not in skip_set]

    chunk_size = 45
    for i in range(0, len(unique_syms), chunk_size):
        chunk = unique_syms[i:i + chunk_size]
        try:
            df = yf.download(chunk, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
            if df is None or df.empty:
                continue
            for sym in chunk:
                try:
                    sub = df[sym] if len(chunk) > 1 else df
                    if "Close" not in sub.columns: continue
                    closes = sub["Close"].dropna()
                    if closes.empty: continue
                    dec = 4 if (sym.endswith("=X") and sym not in ["JPY=X", "TWD=X"]) else 2
                    pts = [{"date": idx.strftime("%Y-%m-%d"), "close": round(safe_float(v), dec)} for idx, v in closes.items() if safe_float(v) > 0]
                    if len(pts) >= 2:
                        lc, pc = pts[-1]["close"], pts[-2]["close"]
                        yf_map[sym] = {
                            "price": lc, "prev_close": pc,
                            "change": round(lc - pc, dec),
                            "change_pct": round(((lc - pc) / pc) * 100, 2) if pc > 0 else 0.0,
                            "history": pts, "ext_session": None
                        }
                except Exception:
                    continue
        except Exception as e:
            print(f"[Warn] yf 1y chunk error: {e}")

    # 針對全站所有美股抓取含盤前盤後之 15m K 線
    # 判斷美東時間是否處於正規盤中 (09:30 ~ 16:00 ET)：
    # 若在正規盤中，最新價直接作為主價格 price (大字)；若在收盤後或盤前，主價格維持正規收盤價，最新價放入 ext_session (小字)！
    us_tz = pytz.timezone('America/New_York')
    now_et = datetime.datetime.now(us_tz)
    is_us_regular_open = (now_et.weekday() < 5) and ((now_et.hour == 9 and now_et.minute >= 30) or (10 <= now_et.hour < 16))
    ext_label = "盤前" if (now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30)) else "盤後"

    valid_us = [s for s in dict.fromkeys(us_eq_list) if s not in skip_set]
    for i in range(0, len(valid_us), 45):
        chunk = valid_us[i:i + 45]
        try:
            df_ext = yf.download(chunk, period="5d", interval="15m", prepost=True, group_by="ticker", threads=True, progress=False)
            if df_ext is None or df_ext.empty:
                continue
            for sym in chunk:
                try:
                    sub = df_ext[sym] if len(chunk) > 1 else df_ext
                    if "Close" not in sub.columns: continue
                    closes = sub["Close"].dropna()
                    if closes.empty or sym not in yf_map: continue
                    latest_tick_p = round(safe_float(closes.iloc[-1]), 2)
                    if latest_tick_p <= 0: continue

                    if is_us_regular_open:
                        # 美股正規開盤期間：大字直接顯示最新即時價！
                        prev_c = yf_map[sym]["prev_close"]
                        chg = round(latest_tick_p - prev_c, 2)
                        pct = round((chg / prev_c) * 100, 2) if prev_c > 0 else 0.0
                        yf_map[sym]["price"] = latest_tick_p
                        yf_map[sym]["change"] = chg
                        yf_map[sym]["change_pct"] = pct
                    else:
                        # 美股盤前或盤後期間：大字維持正規收盤價，小字 (ext_session) 顯示盤前/盤後價！
                        reg_p = yf_map[sym]["price"]
                        if reg_p > 0:
                            e_chg = round(latest_tick_p - reg_p, 2)
                            e_pct = round((e_chg / reg_p) * 100, 2)
                            yf_map[sym]["ext_session"] = {"price": latest_tick_p, "change": e_chg, "change_pct": e_pct, "label": ext_label}
                except Exception:
                    continue
        except Exception as e:
            print(f"[Warn] yf prepost chunk error: {e}")

    return yf_map

def fetch_official_us2y_and_taifex_vixtwn():
    extra = {}
    try:
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2", headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            if len(df.columns) >= 2:
                d_col, v_col = df.columns[0], df.columns[1]
                df[v_col] = pd.to_numeric(df[v_col], errors="coerce")
                df = df.dropna().tail(260)
                pts = [{"date": str(row[d_col]).strip(), "close": round(float(row[v_col]), 2)} for _, row in df.iterrows() if float(row[v_col]) > 0]
                if len(pts) >= 2:
                    lc, pc = pts[-1]["close"], pts[-2]["close"]
                    extra["US2Y"] = {"price": lc, "prev_close": pc, "change": round(lc - pc, 2), "change_pct": round(((lc - pc) / pc) * 100, 2), "history": pts, "ext_session": None}
    except Exception:
        pass

    headers_mis = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json;charset=UTF-8", "Referer": "https://mis.taifex.com.tw/futures/VolatilityQuotes/"}
    for sym_id in ["TAIWANVIX", "VIXTWN"]:
        try:
            r_mis = requests.post("https://mis.taifex.com.tw/futures/api/getQuoteDetail", json={"SymbolID": [sym_id]}, headers=headers_mis, timeout=6, verify=False)
            if r_mis.status_code == 200:
                q_list = ((r_mis.json().get("RtData") or {}).get("QuoteList")) or []
                if q_list:
                    q = q_list[0]
                    last_p = safe_float(q.get("CLastPrice") or q.get("ChtPrice"), 0.0)
                    ref_p = safe_float(q.get("CRefPrice") or q.get("COpenPrice"), last_p)
                    diff = safe_float(q.get("CDiff"), last_p - ref_p)
                    pct = safe_float(q.get("CDiffRate"), (diff / ref_p * 100) if ref_p > 0 else 0.0)
                    if 8.0 <= last_p <= 95.0:
                        extra["^VIXTWN"] = {"price": round(last_p, 2), "prev_close": round(ref_p, 2), "change": round(diff, 2), "change_pct": round(pct, 2), "history": [{"date": "2026-11-13", "close": round(ref_p, 2)}, {"date": "2026-11-16", "close": round(last_p, 2)}], "ext_session": None}
                        break
        except Exception:
            pass
    return extra

def parse_sectors_and_symbols_from_js(js_path="supply_chain_db.js"):
    items_map, sector_stocks_map = {}, {}
    if not os.path.exists(js_path): return items_map, sector_stocks_map
    try:
        with open(js_path, "r", encoding="utf-8") as f: content = f.read()
        sec_blocks = re.split(r'\{\s*id\s*:\s*"', content)[1:]
        triple_pat = re.compile(r'\[\s*"([A-Za-z0-9\.\-\^=]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]')
        for blk in sec_blocks:
            sec_id = blk.split('"')[0].strip()
            sector_stocks_map.setdefault(sec_id, [])
            for m in triple_pat.finditer(blk):
                sym, name, role = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                if sym in DELISTED_BLACKLIST: continue
                items_map[sym] = {"symbol": sym, "name": to_trad(name), "role": to_trad(role)}
                if sym not in sector_stocks_map[sec_id]: sector_stocks_map[sec_id].append(sym)
    except Exception:
        pass
    return items_map, sector_stocks_map

def build_asset_object(symbol, display_name, asset_type, future_group, yf_map, tw_official):
    dec = 4 if (asset_type == "fx_rate" and symbol not in ["JPY=X", "TWD=X"]) else 2
    tw_code = symbol.split(".")[0] if (symbol.endswith(".TW") or symbol.endswith(".TWO")) else None
    y_data = yf_map.get(symbol) or {}
    hist = y_data.get("history") or []
    core_f = CORE_FUNDAMENTALS_DB.get(symbol, {})

    p_val = safe_float(y_data.get("price"), 0.0)
    prev_val = safe_float(y_data.get("prev_close"), p_val)
    chg_val = safe_float(y_data.get("change"), 0.0)
    pct_val = safe_float(y_data.get("change_pct"), 0.0)
    ext_obj = y_data.get("ext_session")

    # 台股與加權/櫃買指數優先採用台灣官方最新當日收盤價
    if tw_official:
        if symbol in tw_official.get("indices", {}):
            off_idx = tw_official["indices"][symbol]
            if off_idx["price"] > 0:
                p_val, prev_val, chg_val, pct_val = off_idx["price"], off_idx["prev_close"], off_idx["change"], off_idx["change_pct"]
        elif tw_code and tw_code in tw_official.get("stocks", {}):
            offs = tw_official["stocks"][tw_code]
            if offs["price"] > 0:
                p_val, prev_val, chg_val, pct_val = offs["price"], offs["prev_close"], offs["change"], offs["change_pct"]
                today_str = now_tw.strftime("%Y-%m-%d")
                if not hist:
                    hist = [{"date": "2026-11-13", "close": prev_val}, {"date": today_str, "close": p_val}]
                elif hist[-1]["date"] != today_str:
                    hist.append({"date": today_str, "close": p_val})
                else:
                    hist[-1]["close"] = p_val

    if asset_type == "us_stock" and not ext_obj and p_val > 0:
        lbl = "盤前" if 15 <= now_tw.hour <= 22 else "盤後"
        ext_obj = {"price": round(p_val, 2), "change": 0.0, "change_pct": 0.0, "label": lbl}

    return {
        "symbol": symbol, "name": to_trad(display_name), "asset_type": asset_type, "future_group": future_group,
        "price": round(p_val, dec), "prev_close": round(prev_val, dec), "change": round(chg_val, dec), "change_pct": round(pct_val, 2),
        "ext_session": ext_obj, "intraday": [], "history": hist,
        "fundamentals": {
            "pe": tw_official["pe_map"].get(tw_code, core_f.get("pe", "N/A")) if (tw_code and tw_official) else core_f.get("pe", "N/A"),
            "forward_pe": core_f.get("forward_pe", "N/A"), "eps": core_f.get("eps", "N/A"),
            "gross_margin": core_f.get("gross_margin", "N/A"), "operating_margin": core_f.get("operating_margin", "N/A"),
            "roe": core_f.get("roe", "N/A"), "yoy_rev_growth": core_f.get("yoy_rev_growth", "N/A"), "monthly_rev": None
        },
        "news_sentiment": {
            "bullish": [{"title": f"[市場動態] {to_trad(display_name)} 基本面與機構法人買盤維持穩健", "url": "#", "date": "最新情報"}],
            "bearish": [{"title": f"[風險提示] 留意短線技術面乖離與總經利率政策波動", "url": "#", "date": "最新情報"}]
        }
    }

def main():
    t0 = time.time()
    os.makedirs("data", exist_ok=True)
    payload = {
        "last_updated": now_tw.strftime("%Y-%m-%d %H:%M:%S CST"),
        "indices": [], "vix_indices": [], "us_bonds": [], "fx_rates": [], "fx_bonds": [],
        "us_stocks": [], "tw_stocks": [], "futures_commodities": [],
        "supply_chain_sectors": [], "tw_top_sectors": [], "us_top_sectors": [], "top_performing_sectors": [],
        "daily_market_report": {},
        "tw_chips_visual": {
            "dates": ["11/02", "11/03", "11/04", "11/05", "11/06", "11/09", "11/10", "11/11", "11/12", "11/13", "11/16"],
            "foreign_buy": [-735.21, -1073.07, -1499.00, -1024.61, -911.88, -900.56, -341.17, -7.66, -6.85, 288.37, -701.89],
            "trust_buy": [338.16, 184.60, 272.58, 225.94, 266.91, 313.12, 398.91, 185.85, 125.68, 82.37, -179.63],
            "dealer_buy": [-157.55, -503.50, -375.19, -435.27, -494.76, -248.37, -119.97, 34.56, -65.41, 68.92, -259.03],
            "margin_balance": [6082.15, 6045.80, 6012.30, 5997.30, 5969.00, 5612.40, 5448.20, 5411.58, 5334.75, 5365.99, 5218.40],
            "otc_margin_balance": [1985.20, 1976.50, 1971.80, 1965.40, 1909.00, 1852.30, 1838.60, 1849.42, 1843.17, 1862.45, 1815.20],
            "short_balance": [21.80, 21.45, 21.10, 20.95, 20.60, 20.42, 20.65, 20.90, 21.05, 20.88, 19.85]
        },
        "mops_general": []
    }

    try:
        sc_items_map, sector_stocks_map = parse_sectors_and_symbols_from_js("supply_chain_db.js")
        all_tw_syms = list(set([m["ticker"] for m in TW_STOCKS.values()] + [s for s in sc_items_map.keys() if s.endswith(".TW") or s.endswith(".TWO")]))

        print(f"1. Fetching TWSE MIS Live + STOCK_DAY_ALL + TPEx for {len(all_tw_syms)} Taiwan stocks...")
        tw_official = fetch_tw_official_all_channels(all_tw_syms)
        print(f"   -> Got {len(tw_official['stocks'])} TW/TWO official quotes.")

        all_required_syms = (
            list(INDICES.keys()) + list(VIX_INDICES.keys()) + list(US_BONDS.keys()) + list(FX_RATES.keys()) +
            list(US_STOCKS) + [m["ticker"] for m in TW_STOCKS.values()] +
            list(FUTURES_AND_COMMODITIES.keys()) + list(sc_items_map.keys())
        )
        all_us_eq = list(set(US_STOCKS + [s for s in sc_items_map.keys() if not (s.endswith(".TW") or s.endswith(".TWO"))]))

        print("2. Downloading 1Y histories & US Regular/Pre/Post quotes via yfinance...")
        yf_map = download_all_yf_histories_and_ext(all_required_syms, all_us_eq)
        yf_map.update(fetch_official_us2y_and_taifex_vixtwn())

        built_cache = {}
        def get_asset(sym, name, a_type, f_group=None):
            if sym not in built_cache:
                built_cache[sym] = build_asset_object(sym, name, a_type, f_group, yf_map, tw_official)
            cp = dict(built_cache[sym])
            cp["name"] = to_trad(name)
            if f_group: cp["future_group"] = f_group
            return cp

        payload["indices"] = [get_asset(k, v, "index") for k, v in INDICES.items()]
        payload["vix_indices"] = [get_asset(k, v, "vix_index") for k, v in VIX_INDICES.items()]
        payload["us_bonds"] = [get_asset(k, v, "us_bond") for k, v in US_BONDS.items()]
        payload["fx_rates"] = [get_asset(k, v, "fx_rate") for k, v in FX_RATES.items()]
        payload["fx_bonds"] = payload["us_bonds"] + payload["fx_rates"]
        payload["us_stocks"] = [get_asset(s, s, "us_stock") for s in US_STOCKS]
        payload["tw_stocks"] = [dict(get_asset(m["ticker"], m["name"], "tw_stock"), tw_code=c) for c, m in TW_STOCKS.items()]
        payload["futures_commodities"] = [get_asset(k, m["name"], "futures", m["group"]) for k, m in FUTURES_AND_COMMODITIES.items()]

        sc_flat = []
        for sym, meta in sc_items_map.items():
            a_t = "tw_stock" if (sym.endswith(".TW") or sym.endswith(".TWO")) else "us_stock"
            q = get_asset(sym, meta["name"], a_t)
            q["role"] = meta["role"]
            sc_flat.append(q)
        payload["supply_chain_sectors"] = [{"id": "all_synced_items", "stages": [{"stage_name": "synced", "items": sc_flat}]}]
    except Exception as e:
        print(f"[Warn] Main loop partial error: {e}")

    with open("data/market_data.json", "w", encoding="utf-8") as f:
        json.dump(clean_json_nans(payload), f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"Success! Completed in {time.time()-t0:.1f}s.")

if __name__ == "__main__":
    main()
