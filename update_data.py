import os, re, sys, io, json, math, time, datetime
import xml.etree.ElementTree as ET
from urllib.parse import quote
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
    if text is None:
        return ""
    s = cc.convert(str(text)) if cc else str(text)
    for w, r in [("那斯達剋", "納斯達克"), ("納斯達剋", "納斯達克"), ("那斯達克", "納斯達克"), ("瑞士法朗", "瑞士法郎"), ("臺", "台")]:
        s = s.replace(w, r)
    return s

def safe_float(val, default=0.0):
    try:
        if val is None or pd.isna(val):
            return default
        s = str(val).replace(",", "").replace("%", "").replace("--", "").replace("+", "").strip()
        if s in ["", "N/A", "None", "null", "-", "X", "."]:
            return default
        f = float(s)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default

def fmt_pct_str(val):
    f = safe_float(val, None)
    return f"{f:.1f}%" if f is not None else "N/A"

def fmt_num_str(val):
    f = safe_float(val, None)
    return round(f, 2) if (f is not None and f != 0) else "N/A"

def clean_json_nans(obj):
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: clean_json_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_json_nans(x) for x in obj]
    return obj

def extract_close_series(df, ticker=None):
    if df is None or df.empty:
        return pd.Series(dtype=float)
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if ticker is not None and ticker in df.columns.get_level_values(0):
                sub = df[ticker]
                if "Close" in sub.columns:
                    s = sub["Close"]
                    return s.iloc[:, 0].dropna() if isinstance(s, pd.DataFrame) else s.dropna()
            if "Close" in df.columns.get_level_values(0):
                sub = df["Close"]
                if isinstance(sub, pd.DataFrame):
                    if ticker is not None and ticker in sub.columns:
                        return sub[ticker].dropna()
                    return sub.iloc[:, 0].dropna()
                return sub.dropna()
        elif "Close" in df.columns:
            s = df["Close"]
            return s.iloc[:, 0].dropna() if isinstance(s, pd.DataFrame) else s.dropna()
    except Exception:
        pass
    return pd.Series(dtype=float)

tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.datetime.now(tw_tz)
DELISTED_BLACKLIST = {"2867.TW", "2809.TW", "2888.TW", "MMC"}

INDICES = {
    "^GSPC": "S&P 500 指數",
    "^DJI": "道瓊工業指數",
    "^NDX": "納斯達克 100 指數",
    "^SOX": "費城半導體指數",
    "^RUT": "羅素 2000 指數",
    "^TWII": "台灣加權指數",
    "^TWOII": "台灣櫃買指數",
    "^N225": "日經 225 指數",
    "^KS11": "韓國 KOSPI 指數",
    "^FTSE": "英國富時 100",
    "^GDAXI": "德國 DAX 指數",
    "^FCHI": "法國 CAC 40"
}
VIX_INDICES = {
    "^VIX": "美國 CBOE VIX 恐慌指數",
    "^VIXTWN": "臺指選擇權波動率指數 (VIXTWN)"
}
US_BONDS = {
    "^IRX": "美國 3 個月期國庫券殖利率",
    "US2Y": "美國 2 年期公債殖利率",
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
US_STOCKS = ["NVDA", "TSM", "SPCX", "AMD", "GOOGL", "META", "TSLA", "AVGO", "AMZN", "AAPL", "MSFT"]
TW_STOCKS = {
    "2330": {"ticker": "2330.TW", "name": "2330 台積電"},
    "2454": {"ticker": "2454.TW", "name": "2454 聯發科"},
    "2308": {"ticker": "2308.TW", "name": "2308 台達電"},
    "2317": {"ticker": "2317.TW", "name": "2317 鴻海"},
    "3711": {"ticker": "3711.TW", "name": "3711 日月光投控"}
}
FUTURES_AND_COMMODITIES = {
    "TXF": {"name": "台指期近月", "group": "us_index_futures"},
    "ES=F": {"name": "小S&P期貨", "group": "us_index_futures"},
    "NQ=F": {"name": "小納斯達克期貨", "group": "us_index_futures"},
    "YM=F": {"name": "小道瓊期貨", "group": "us_index_futures"},
    "GC=F": {"name": "黃金期貨", "group": "metals_futures"},
    "SI=F": {"name": "白銀期貨", "group": "metals_futures"},
    "HG=F": {"name": "銅期貨", "group": "metals_futures"},
    "PA=F": {"name": "鈀金期貨", "group": "metals_futures"},
    "BZ=F": {"name": "布蘭特原油期貨", "group": "energy_futures"},
    "CL=F": {"name": "WTI 原油期貨", "group": "energy_futures"},
    "ZS=F": {"name": "黃豆期貨 (CBOT)", "group": "agri_futures"},
    "ZW=F": {"name": "小麥期貨 (CBOT)", "group": "agri_futures"},
    "ZC=F": {"name": "玉米期貨 (CBOT)", "group": "agri_futures"},
    "BTC-USD": {"name": "比特幣 (BTC)", "group": "crypto_assets"},
    "ETH-USD": {"name": "以太幣 (ETH)", "group": "crypto_assets"}
}

# 1. 官方月營收 OpenAPI (上市 + 上櫃)
def fetch_official_tw_monthly_revenues():
    rev_map = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in ["https://openapi.twse.com.tw/v1/opendata/t187ap05_L", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"]:
        try:
            r = requests.get(url, headers=headers, timeout=10, verify=False)
            if r.status_code == 200:
                for row in r.json():
                    code = str(row.get("公司代號") or row.get("SecuritiesCompanyCode") or "").strip()
                    ym = str(row.get("資料年月") or row.get("YearMonth") or "").strip()
                    cur_rev = safe_float(row.get("營業收入-當月營收") or row.get("MonthlyRevenue"), 0.0)
                    mom = safe_float(row.get("營業收入-上月比較增減(%)") or row.get("MonthOnMonthChange"), None)
                    yoy = safe_float(row.get("營業收入-去年同月增減(%)") or row.get("YearOnYearChange"), None)
                    cum_yoy = safe_float(row.get("累計營業收入-前期比較增減(%)") or row.get("CumulativeYearOnYearChange"), None)
                    if code and cur_rev > 0:
                        rev_yi = round(cur_rev / 1e5, 2)
                        m_str = f"{ym[:3]}年{ym[3:]}月" if len(ym) == 5 else ym
                        rev_map[code] = {
                            "month": m_str, "revenue_yi": f"{rev_yi:,.2f} 億元",
                            "mom": round(mom, 2) if mom is not None else 0.0,
                            "yoy": round(yoy, 2) if yoy is not None else 0.0,
                            "cum_yoy": round(cum_yoy, 2) if cum_yoy is not None else 0.0
                        }
        except Exception:
            pass
    return rev_map

# 2. MOPS 重大訊息
def fetch_official_mops_material_news():
    mops_by_code, mops_general = {}, []
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in ["https://openapi.twse.com.tw/v1/opendata/t187ap04_L", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"]:
        try:
            r = requests.get(url, headers=headers, timeout=8, verify=False)
            if r.status_code == 200:
                for row in r.json():
                    code = str(row.get("公司代號") or "").strip()
                    name = to_trad(row.get("公司名稱") or "")
                    subj = to_trad(row.get("主旨") or "").replace("\n", " ").strip()
                    dt, tm = str(row.get("發言日期") or ""), str(row.get("發言時間") or "")
                    if code and subj:
                        item_obj = {
                            "code": code, "name": name, "subject": subj, "date": dt, "time": tm,
                            "url": "https://mops.twse.com.tw/mops/#/web/t05st01"
                        }
                        mops_by_code.setdefault(code, []).append(item_obj)
                        if len(mops_general) < 25:
                            mops_general.append(item_obj)
        except Exception:
            pass
    return mops_by_code, mops_general

# 3. Google News RSS
def fetch_google_news_rss_for_stock(query_str, max_items=3):
    news_list = []
    try:
        url = f"https://news.google.com/rss/search?q={quote(query_str)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall("./channel/item")[:max_items]:
                title = to_trad(item.findtext("title") or "")
                link = item.findtext("link") or "#"
                pub_date = (item.findtext("pubDate") or "")[:16]
                source = to_trad(item.findtext("source") or "財經新聞")
                if title:
                    news_list.append({"title": title, "url": link, "date": f"{source}・{pub_date}"})
    except Exception:
        pass
    return news_list

# 4. 恐懼與貪婪指數
def classify_fg_label(score):
    s = float(score)
    if s <= 25:
        return "極度恐懼", "EXTREME FEAR"
    if s < 45:
        return "恐懼", "FEAR"
    if s <= 55:
        return "中立", "NEUTRAL"
    if s < 75:
        return "貪婪", "GREED"
    return "極度貪婪", "EXTREME GREED"

def fetch_fear_and_greed_indices():
    fg_data = {
        "us_cnn": {"score": None, "label_zh": "同步中", "label_en": "LOADING", "prev_close": None, "updated": now_tw.strftime("%Y-%m-%d"), "source": "CNN Fear & Greed Index"},
        "crypto_alt": {"score": None, "label_zh": "同步中", "label_en": "LOADING", "prev_close": None, "updated": now_tw.strftime("%Y-%m-%d"), "source": "Alternative.me Crypto F&G"}
    }
    try:
        r_cnn = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cnn.com/markets/fear-and-greed"}, timeout=8)
        if r_cnn.status_code == 200:
            fg_obj = (r_cnn.json() or {}).get("fear_and_greed") or {}
            sc = safe_float(fg_obj.get("score"), None)
            prev_sc = safe_float(fg_obj.get("previous_close"), None)
            if sc is not None and 0 <= sc <= 100:
                l_zh, l_en = classify_fg_label(sc)
                fg_data["us_cnn"] = {
                    "score": round(sc), "label_zh": l_zh, "label_en": l_en,
                    "prev_close": round(prev_sc) if prev_sc is not None else round(sc),
                    "updated": str(fg_obj.get("timestamp", ""))[:10] or now_tw.strftime("%Y-%m-%d"),
                    "source": "CNN Business 官方 API"
                }
    except Exception:
        pass
    try:
        r_alt = requests.get("https://api.alternative.me/fng/?limit=2", headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r_alt.status_code == 200:
            arr = (r_alt.json() or {}).get("data") or []
            if arr:
                cur_sc = safe_float(arr[0].get("value"), None)
                prv_sc = safe_float(arr[1].get("value"), cur_sc) if len(arr) > 1 else cur_sc
                if cur_sc is not None and 0 <= cur_sc <= 100:
                    l_zh, l_en = classify_fg_label(cur_sc)
                    fg_data["crypto_alt"] = {
                        "score": round(cur_sc), "label_zh": l_zh, "label_en": l_en,
                        "prev_close": round(prv_sc) if prv_sc is not None else round(cur_sc),
                        "updated": now_tw.strftime("%Y-%m-%d"), "source": "Alternative.me 官方 API"
                    }
    except Exception:
        pass
    return fg_data

# 5. 全自動台股三大法人 + 上市櫃融資餘額(10日完整) + 官方公式實算每日上市融資維持率 (零寫死日期)
def fetch_twse_close_prices_for_date(ymd, headers):
    px = {}
    try:
        r = requests.get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json", headers=headers, timeout=10, verify=False)
        if r.status_code == 200:
            j = r.json()
            if j.get("stat") == "OK":
                for tb in (j.get("tables") or []):
                    fields = [str(f).strip() for f in (tb.get("fields") or [])]
                    if "證券代號" in fields and "收盤價" in fields:
                        ic, ip = fields.index("證券代號"), fields.index("收盤價")
                        for row in (tb.get("data") or []):
                            if len(row) > max(ic, ip):
                                p = safe_float(row[ip], 0.0)
                                if p > 0:
                                    px[str(row[ic]).strip()] = p
    except Exception:
        pass
    return px

def parse_mi_margn_all_with_ratio(j_data, px_map):
    if not j_data or j_data.get("stat") != "OK":
        return None, None, None, None
    d_str = str(j_data.get("date", "")).strip()
    today_yi, short_wan, margin_k_ntd = None, None, 0.0
    total_mv_ntd = 0.0

    for tb in (j_data.get("tables") or []):
        fields = [str(x).strip() for x in (tb.get("fields") or [])]
        rows = tb.get("data") or []
        if any("項目" in f for f in fields) and any("今日餘額" in f for f in fields):
            idx_t = next((i for i, f in enumerate(fields) if "今日餘額" in f), 5)
            for r in rows:
                if len(r) <= idx_t:
                    continue
                title = str(r[0]).strip()
                if "融資金額" in title:
                    t_q = safe_float(r[idx_t], 0.0)
                    if t_q > 1e6:
                        margin_k_ntd = t_q
                        today_yi = round(t_q / 1e5, 2)
                elif "融券" in title:
                    s_z = safe_float(r[idx_t], 0.0)
                    if s_z > 1000:
                        short_wan = round(s_z / 1e4, 2)
        elif any("代號" in f for f in fields) and any("今日餘額" in f for f in fields) and px_map:
            idx_c = next((i for i, f in enumerate(fields) if "代號" in f), 0)
            idx_mlot = next((i for i, f in enumerate(fields) if "今日餘額" in f), 6)
            for r in rows:
                if len(r) <= max(idx_c, idx_mlot):
                    continue
                code = str(r[idx_c]).strip()
                lots = safe_float(r[idx_mlot], 0.0)
                if lots > 0 and code in px_map:
                    total_mv_ntd += lots * 1000.0 * px_map[code]

    maint_rate = None
    if margin_k_ntd > 1e6 and total_mv_ntd > 0:
        r_val = (total_mv_ntd / (margin_k_ntd * 1000.0)) * 100.0
        if 100.0 <= r_val <= 250.0:
            maint_rate = round(r_val, 2)
    return d_str, today_yi, short_wan, maint_rate

def fetch_twse_official_margin_and_maintenance():
    headers = {"User-Agent": "Mozilla/5.0"}
    records_by_ymd = {}
    if os.path.exists("data/market_data.json"):
        try:
            with open("data/market_data.json", "r", encoding="utf-8") as f:
                old_c = (json.load(f) or {}).get("tw_chips_visual") or {}
                ymds = old_c.get("ymds") or []
                for i, ymd in enumerate(ymds):
                    if isinstance(ymd, str) and len(ymd) == 8:
                        records_by_ymd[ymd] = {
                            "foreign_buy": (old_c.get("foreign_buy") or [None] * len(ymds))[i],
                            "trust_buy": (old_c.get("trust_buy") or [None] * len(ymds))[i],
                            "dealer_buy": (old_c.get("dealer_buy") or [None] * len(ymds))[i],
                            "margin_balance": (old_c.get("margin_balance") or [None] * len(ymds))[i],
                            "otc_margin_balance": (old_c.get("otc_margin_balance") or [None] * len(ymds))[i],
                            "twse_only_margin_rate": (old_c.get("twse_only_margin_rate") or [None] * len(ymds))[i],
                            "short_balance": (old_c.get("short_balance") or [None] * len(ymds))[i]
                        }
        except Exception:
            pass

    collected_days = 0
    for offset in range(0, 18):
        if collected_days >= 10:
            break
        dt = now_tw - datetime.timedelta(days=offset)
        if dt.weekday() >= 5:
            continue
        ymd = dt.strftime("%Y%m%d")
        rec = records_by_ymd.get(ymd) or {
            "foreign_buy": None, "trust_buy": None, "dealer_buy": None,
            "margin_balance": None, "otc_margin_balance": None,
            "twse_only_margin_rate": None, "short_balance": None
        }

        got_day = False
        if offset <= 2 or rec["foreign_buy"] is None:
            try:
                r_inst = requests.get(f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={ymd}&response=json", headers=headers, timeout=8, verify=False)
                if r_inst.status_code == 200:
                    j = r_inst.json()
                    if j.get("stat") == "OK" and str(j.get("date", "")).strip() == ymd and j.get("data"):
                        f_sum, t_sum, d_sum = 0.0, 0.0, 0.0
                        for row in j["data"]:
                            name = str(row[0]).strip()
                            diff_val = safe_float(row[3], 0.0) / 1e8
                            if "外資" in name:
                                f_sum += diff_val
                            elif "投信" in name:
                                t_sum += diff_val
                            elif "自營商" in name:
                                d_sum += diff_val
                        rec["foreign_buy"] = round(f_sum, 2)
                        rec["trust_buy"] = round(t_sum, 2)
                        rec["dealer_buy"] = round(d_sum, 2)
                        got_day = True
                time.sleep(0.2)
            except Exception:
                pass
        else:
            got_day = True

        if got_day and (offset <= 2 or rec["margin_balance"] is None or rec["twse_only_margin_rate"] is None):
            try:
                r_m = requests.get(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ymd}&selectType=ALL&response=json", headers=headers, timeout=10, verify=False)
                if r_m.status_code == 200:
                    jm = r_m.json()
                    if jm.get("stat") == "OK" and str(jm.get("date", "")).strip() == ymd:
                        px_map = fetch_twse_close_prices_for_date(ymd, headers)
                        _, t_yi, s_wan, m_rate = parse_mi_margn_all_with_ratio(jm, px_map)
                        if t_yi:
                            rec["margin_balance"] = t_yi
                        if s_wan:
                            rec["short_balance"] = s_wan
                        if m_rate:
                            rec["twse_only_margin_rate"] = m_rate
                time.sleep(0.25)
            except Exception:
                pass

        # 逐日抓取櫃買中心上櫃融資餘額，補齊全部 10 個交易日
        if got_day and (offset <= 2 or rec["otc_margin_balance"] is None):
            try:
                tpex_d = dt.strftime("%Y/%m/%d")
                r_otc = requests.get(f"https://www.tpex.org.tw/www/zh-tw/margin/balance?date={tpex_d}&response=json", headers=headers, timeout=8, verify=False)
                if r_otc.status_code == 200:
                    j_otc = r_otc.json()
                    otc_bal = None
                    for tb in (j_otc.get("tables") or []):
                        for s_row in (tb.get("summary") or []):
                            for cell in s_row:
                                v = safe_float(cell, 0.0)
                                if v > 1e7:
                                    v = round(v / 1e5, 2)
                                if 800.0 <= v <= 4000.0:
                                    otc_bal = round(v, 2)
                    if otc_bal:
                        rec["otc_margin_balance"] = otc_bal
                time.sleep(0.2)
            except Exception:
                pass

        if got_day:
            records_by_ymd[ymd] = rec
            collected_days += 1

    sorted_ymds = sorted(records_by_ymd.keys())[-10:]
    return {
        "ymds": sorted_ymds,
        "dates": [f"{d[4:6]}/{d[6:8]}" for d in sorted_ymds],
        "foreign_buy": [records_by_ymd[d]["foreign_buy"] for d in sorted_ymds],
        "trust_buy": [records_by_ymd[d]["trust_buy"] for d in sorted_ymds],
        "dealer_buy": [records_by_ymd[d]["dealer_buy"] for d in sorted_ymds],
        "margin_balance": [records_by_ymd[d]["margin_balance"] for d in sorted_ymds],
        "otc_margin_balance": [records_by_ymd[d]["otc_margin_balance"] for d in sorted_ymds],
        "twse_only_margin_rate": [records_by_ymd[d]["twse_only_margin_rate"] for d in sorted_ymds],
        "short_balance": [records_by_ymd[d]["short_balance"] for d in sorted_ymds]
    }

TV_FUND_COLUMNS = [
    "name", "close", "change", "change_abs",
    "price_earnings_ttm", "price_earnings_forward_fy",
    "earnings_per_share_diluted_ttm", "return_on_equity",
    "gross_margin_ttm", "operating_margin_ttm", "total_revenue_yoy_growth_ttm",
    "earnings_per_share_forecast_next_fy", "earnings_per_share_forecast_fq"
]

def parse_tv_fundamentals(d):
    p = safe_float(d[1], 0.0) if len(d) > 1 else 0.0
    fwd_pe = fmt_num_str(d[5]) if len(d) > 5 else "N/A"
    if fwd_pe == "N/A" and p > 0:
        eps_fy = safe_float(d[11], 0.0) if len(d) > 11 else 0.0
        eps_fq = safe_float(d[12], 0.0) if len(d) > 12 else 0.0
        if eps_fy > 0:
            fwd_pe = round(p / eps_fy, 2)
        elif eps_fq > 0:
            fwd_pe = round(p / (eps_fq * 4), 2)
    return {
        "pe": fmt_num_str(d[4]) if len(d) > 4 else "N/A",
        "forward_pe": fwd_pe if fwd_pe != "N/A" else "無預估",
        "eps": fmt_num_str(d[6]) if len(d) > 6 else "N/A",
        "roe": fmt_pct_str(d[7]) if len(d) > 7 else "N/A",
        "gross_margin": fmt_pct_str(d[8]) if len(d) > 8 else "N/A",
        "operating_margin": fmt_pct_str(d[9]) if len(d) > 9 else "N/A",
        "yoy_rev_growth": fmt_pct_str(d[10]) if len(d) > 10 else "N/A"
    }

def fetch_tradingview_taiwan_full_market():
    tv_stocks, tv_fund_map = {}, {}
    payload = {
        "filter": [{"left": "close", "operation": "greater", "right": 0}],
        "options": {"lang": "zh_TW"}, "markets": ["taiwan"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": TV_FUND_COLUMNS, "sort": {"sortBy": "name", "sortOrder": "asc"}, "range": [0, 4000]
    }
    try:
        r = requests.post("https://scanner.tradingview.com/taiwan/scan", json=payload, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}, timeout=12)
        if r.status_code == 200:
            for row in (r.json().get("data") or []):
                d = row.get("d") or []
                t_raw = str(row.get("s", ""))
                code = t_raw.split(":")[-1].strip() if ":" in t_raw else (str(d[0]).strip() if d else "")
                if len(d) >= 4 and code:
                    p, pct, chg = safe_float(d[1], 0.0), safe_float(d[2], 0.0), safe_float(d[3], 0.0)
                    if p > 0:
                        tv_stocks[code] = {"price": round(p, 2), "prev_close": round(p - chg, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
                        tv_fund_map[code] = parse_tv_fundamentals(d)
    except Exception:
        pass
    return tv_stocks, tv_fund_map

def fetch_tradingview_us_fundamentals(us_sym_list):
    us_fund_map = {}
    clean_us = [s.replace("-", ".") for s in set(us_sym_list) if s and not s.startswith("^") and "=" not in s]
    payload = {
        "filter": [{"left": "name", "operation": "in_range", "right": clean_us}],
        "options": {"lang": "zh_TW"}, "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": TV_FUND_COLUMNS, "range": [0, 1000]
    }
    try:
        r = requests.post("https://scanner.tradingview.com/america/scan", json=payload, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}, timeout=12)
        if r.status_code == 200:
            for row in (r.json().get("data") or []):
                d = row.get("d") or []
                t_raw = str(row.get("s", ""))
                sym = (t_raw.split(":")[-1].strip() if ":" in t_raw else str(d[0]).strip()).replace(".", "-")
                if len(d) >= 5 and sym:
                    us_fund_map[sym] = parse_tv_fundamentals(d)
    except Exception:
        pass
    return us_fund_map

def fetch_tradingview_futures_quotes():
    tv_fut_map = {}
    symbol_map = {
        "NYMEX:CL1!": "CL=F",
        "ICEEUR:BRN1!": "BZ=F",
        "CME_MINI:ES1!": "ES=F",
        "CME_MINI:NQ1!": "NQ=F",
        "CBOT_MINI:YM1!": "YM=F",
        "COMEX:GC1!": "GC=F",
        "COMEX:SI1!": "SI=F",
        "COMEX:HG1!": "HG=F",
        "NYMEX:PA1!": "PA=F"
    }
    payload = {
        "symbols": {"tickers": list(symbol_map.keys()), "query": {"types": []}},
        "columns": ["close", "change", "change_abs"]
    }
    try:
        r = requests.post("https://scanner.tradingview.com/futures/scan", json=payload, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}, timeout=10)
        if r.status_code == 200:
            for row in (r.json().get("data") or []):
                tv_sym = str(row.get("s", "")).strip()
                d = row.get("d") or []
                if tv_sym in symbol_map and len(d) >= 3:
                    p, pct, chg = safe_float(d[0], 0.0), safe_float(d[1], 0.0), safe_float(d[2], 0.0)
                    if p > 0:
                        prev_c = round(p - chg, 2)
                        tv_fut_map[symbol_map[tv_sym]] = {
                            "price": round(p, 2), "prev_close": prev_c,
                            "change": round(chg, 2), "change_pct": round(pct, 2),
                            "ext_session": {"price": prev_c, "change": 0.0, "change_pct": 0.0, "label": "前日結算"}
                        }
    except Exception:
        pass
    return tv_fut_map

# 6. 台灣加權 (^TWII) 與 櫃買指數 (^TWOII) 3 通道官方抓取
def fetch_tw_official_all_channels():
    snapshot = {"indices": {}, "stocks": {}, "fund_map": {}}
    headers = {"User-Agent": "Mozilla/5.0"}
    tv_stocks, tv_fund_map = fetch_tradingview_taiwan_full_market()
    snapshot["stocks"].update(tv_stocks)
    snapshot["fund_map"].update(tv_fund_map)

    try:
        r_mis = requests.get("https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw|otc_o00.tw&json=1&delay=0", headers=headers, timeout=8, verify=False)
        if r_mis.status_code == 200:
            for m in (r_mis.json().get("msgArray") or []):
                code = str(m.get("c", "")).strip()
                cur_p, prev_p = safe_float(m.get("z"), 0.0), safe_float(m.get("y"), 0.0)
                if cur_p > 0 and prev_p > 0:
                    chg_p = round(cur_p - prev_p, 2)
                    pct_p = round((chg_p / prev_p) * 100, 2)
                    if code == "t00":
                        snapshot["indices"]["^TWII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": chg_p, "change_pct": pct_p}
                    elif code == "o00":
                        snapshot["indices"]["^TWOII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": chg_p, "change_pct": pct_p}
    except Exception:
        pass

    if "^TWII" not in snapshot["indices"]:
        try:
            r_idx = requests.get("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json", headers=headers, timeout=8, verify=False)
            if r_idx.status_code == 200:
                for tb in (r_idx.json().get("tables") or []):
                    for row in (tb.get("data") or []):
                        if row and ("發行量加權股價指數" in str(row[0]) or "加權股價指數" in str(row[0])):
                            cur_p, chg_p = safe_float(row[1], 0.0), safe_float(row[3], 0.0)
                            if "-" in str(row[2]) or "green" in str(row[2]).lower():
                                chg_p = -abs(chg_p)
                            prev_p = cur_p - chg_p
                            if cur_p > 10000 and prev_p > 0:
                                snapshot["indices"]["^TWII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": round(chg_p, 2), "change_pct": round((chg_p / prev_p) * 100, 2)}
        except Exception:
            pass

    if "^TWOII" not in snapshot["indices"]:
        try:
            r_tpex = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_index", headers=headers, timeout=8, verify=False)
            if r_tpex.status_code == 200:
                arr = r_tpex.json()
                if isinstance(arr, list) and arr:
                    last = arr[-1]
                    cur_p = safe_float(last.get("Close") or last.get("Index") or last.get("收盤指數"), 0.0)
                    chg_p = safe_float(last.get("Change") or last.get("漲跌"), 0.0)
                    prev_p = cur_p - chg_p
                    if cur_p > 50 and prev_p > 0:
                        snapshot["indices"]["^TWOII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": round(chg_p, 2), "change_pct": round((chg_p / prev_p) * 100, 2)}
        except Exception:
            pass

    if "^TWOII" not in snapshot["indices"]:
        try:
            r_inx = requests.get("https://www.tpex.org.tw/www/zh-tw/indexInfo/inx?response=json", headers=headers, timeout=8, verify=False)
            if r_inx.status_code == 200:
                rows = ((r_inx.json().get("tables") or [{}])[0].get("data")) or []
                if rows:
                    last = rows[-1]
                    cur_p = safe_float(last[1], 0.0) if len(last) > 1 else 0.0
                    chg_p = safe_float(last[2], 0.0) if len(last) > 2 else 0.0
                    prev_p = cur_p - chg_p
                    if cur_p > 50 and prev_p > 0:
                        snapshot["indices"]["^TWOII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": round(chg_p, 2), "change_pct": round((chg_p / prev_p) * 100, 2)}
        except Exception:
            pass

    return snapshot

def download_all_yf_histories_and_ext(symbols_list, us_eq_list):
    yf_map = {}
    skip_set = DELISTED_BLACKLIST | {"^VIXTWN", "TXF"}
    yf_download_syms = [("2YY=F" if s == "US2Y" else s) for s in dict.fromkeys(symbols_list) if s not in skip_set]

    for i in range(0, len(yf_download_syms), 35):
        chunk = yf_download_syms[i:i + 35]
        try:
            df = yf.download(chunk, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
            if df is None or df.empty:
                continue
            for y_sym in chunk:
                try:
                    closes = extract_close_series(df, y_sym if len(chunk) > 1 else None)
                    if closes.empty:
                        continue
                    dec = 4 if (y_sym.endswith("=X") and y_sym not in ["JPY=X", "TWD=X"]) else 2
                    pts = [{"date": idx.strftime("%Y-%m-%d"), "close": round(safe_float(v), dec)} for idx, v in closes.items() if safe_float(v) > 0]
                    if len(pts) >= 2:
                        lc, pc = pts[-1]["close"], pts[-2]["close"]
                        target_key = "US2Y" if y_sym == "2YY=F" else y_sym
                        yf_map[target_key] = {
                            "price": lc, "prev_close": pc,
                            "change": round(lc - pc, dec),
                            "change_pct": round(((lc - pc) / pc) * 100, 2) if pc > 0 else 0.0,
                            "history": pts, "ext_session": None
                        }
                except Exception:
                    continue
        except Exception:
            pass

    fut_and_us = [s for s in dict.fromkeys(list(FUTURES_AND_COMMODITIES.keys()) + us_eq_list) if s not in skip_set and s not in {"ZS=F", "ZW=F", "ZC=F"}]
    for i in range(0, len(fut_and_us), 35):
        chunk = fut_and_us[i:i + 35]
        try:
            df_ext = yf.download(chunk, period="5d", interval="5m", prepost=True, group_by="ticker", threads=True, progress=False)
            if df_ext is None or df_ext.empty:
                continue
            for sym in chunk:
                try:
                    if sym not in yf_map:
                        continue
                    closes = extract_close_series(df_ext, sym if len(chunk) > 1 else None)
                    if closes.empty:
                        continue
                    latest_tick_p = round(safe_float(closes.iloc[-1]), 2)
                    if latest_tick_p <= 0:
                        continue
                    reg_p, prev_c = yf_map[sym]["price"], yf_map[sym]["prev_close"]
                    if sym in ["BTC-USD", "ETH-USD"]:
                        chg = round(latest_tick_p - prev_c, 2)
                        yf_map[sym]["price"] = latest_tick_p
                        yf_map[sym]["change"] = chg
                        yf_map[sym]["change_pct"] = round((chg / prev_c) * 100, 2) if prev_c > 0 else 0.0
                        yf_map[sym]["ext_session"] = None
                    elif sym in FUTURES_AND_COMMODITIES:
                        today_us = (now_tw - datetime.timedelta(hours=13)).strftime("%Y-%m-%d")
                        last_hist_date = yf_map[sym]["history"][-1]["date"] if yf_map[sym]["history"] else ""
                        settle_p = prev_c if (last_hist_date == today_us and prev_c > 0) else reg_p
                        chg = round(latest_tick_p - settle_p, 2)
                        pct = round((chg / settle_p) * 100, 2) if settle_p > 0 else 0.0
                        yf_map[sym]["price"] = latest_tick_p
                        yf_map[sym]["prev_close"] = settle_p
                        yf_map[sym]["change"] = chg
                        yf_map[sym]["change_pct"] = pct
                        yf_map[sym]["ext_session"] = {"price": settle_p, "change": 0.0, "change_pct": 0.0, "label": "前日結算"}
                    else:
                        e_chg = round(latest_tick_p - reg_p, 2)
                        e_pct = round((e_chg / reg_p) * 100, 2) if reg_p > 0 else 0.0
                        lbl = "盤前" if 15 <= now_tw.hour <= 22 else "盤後"
                        yf_map[sym]["ext_session"] = {"price": latest_tick_p, "change": e_chg, "change_pct": e_pct, "label": lbl}
                except Exception:
                    continue
        except Exception:
            pass

    # 自動計算農產品「未到期近月合約 (大字)」與「次月芝商所合約 (小字)」(零寫死日期、無電子盤)
    agri_schedules = {
        "ZS=F": ("ZS", [(1, "F"), (3, "H"), (5, "K"), (7, "N"), (8, "Q"), (9, "U"), (11, "X")]),
        "ZW=F": ("ZW", [(3, "H"), (5, "K"), (7, "N"), (9, "U"), (12, "Z")]),
        "ZC=F": ("ZC", [(3, "H"), (5, "K"), (7, "N"), (9, "U"), (12, "Z")])
    }
    for base_sym, (root, months) in agri_schedules.items():
        if base_sym not in yf_map:
            yf_map[base_sym] = {"price": 0.0, "prev_close": 0.0, "change": 0.0, "change_pct": 0.0, "history": [], "ext_session": None}
        seq = [
            (y, dm, code) for y in (now_tw.year, now_tw.year + 1) for (dm, code) in months
            if (y > now_tw.year) or (dm > now_tw.month) or (dm == now_tw.month and now_tw.day < 10)
        ]
        if len(seq) < 2:
            continue
        front_y, _, front_code = seq[0]
        next_y, _, next_code = seq[1]
        front_ticker = f"{root}{front_code}{str(front_y)[-2:]}.CBT"
        next_ticker = f"{root}{next_code}{str(next_y)[-2:]}.CBT"
        next_label = f"芝商所 {root}{next_code}{str(next_y)[-1:]}"

        try:
            df_front = yf.download(front_ticker, period="5d", interval="1d", progress=False)
            f_vals = extract_close_series(df_front)
            if len(f_vals) >= 2:
                f_last, f_prev = round(safe_float(f_vals.iloc[-1]), 2), round(safe_float(f_vals.iloc[-2]), 2)
                f_chg = round(f_last - f_prev, 2)
                yf_map[base_sym]["price"] = f_last
                yf_map[base_sym]["prev_close"] = f_prev
                yf_map[base_sym]["change"] = f_chg
                yf_map[base_sym]["change_pct"] = round((f_chg / f_prev) * 100, 2) if f_prev > 0 else 0.0
        except Exception:
            pass

        try:
            df_next = yf.download(next_ticker, period="5d", interval="1d", progress=False)
            n_vals = extract_close_series(df_next)
            if len(n_vals) >= 2:
                n_last, n_prev = round(safe_float(n_vals.iloc[-1]), 2), round(safe_float(n_vals.iloc[-2]), 2)
                n_chg = round(n_last - n_prev, 2)
                n_pct = round((n_chg / n_prev) * 100, 2) if n_prev > 0 else 0.0
                yf_map[base_sym]["ext_session"] = {"price": n_last, "change": n_chg, "change_pct": n_pct, "label": next_label}
        except Exception:
            pass

    return yf_map

def fetch_official_us2y_and_taifex_vixtwn_and_txf(existing_yf_map):
    extra = {}
    if "US2Y" not in existing_yf_map or safe_float(existing_yf_map.get("US2Y", {}).get("price"), 0.0) <= 0:
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

    headers_mis = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json;charset=UTF-8", "Referer": "https://mis.taifex.com.tw/futures/"}
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
                        extra["^VIXTWN"] = {"price": round(last_p, 2), "prev_close": round(ref_p, 2), "change": round(diff, 2), "change_pct": round(pct, 2), "history": [{"date": now_tw.strftime("%Y-%m-%d"), "close": round(last_p, 2)}], "ext_session": None}
                        break
        except Exception:
            pass

    day_txf, night_txf = None, None
    try:
        r_day = requests.post("https://mis.taifex.com.tw/futures/api/getQuoteDetail", json={"SymbolID": ["TXF-S", "TXFL6-S", "TXFA7-S"]}, headers=headers_mis, timeout=6, verify=False)
        if r_day.status_code == 200:
            for q in (((r_day.json().get("RtData") or {}).get("QuoteList")) or []):
                lp = safe_float(q.get("CLastPrice") or q.get("ChtPrice"), 0.0)
                rp = safe_float(q.get("CRefPrice") or q.get("COpenPrice"), lp)
                df_v = safe_float(q.get("CDiff"), lp - rp)
                pct_v = safe_float(q.get("CDiffRate"), (df_v / rp * 100) if rp > 0 else 0.0)
                if lp > 15000:
                    day_txf = {"price": round(lp, 2), "prev_close": round(rp, 2), "change": round(df_v, 2), "change_pct": round(pct_v, 2)}
                    break
    except Exception:
        pass
    try:
        r_night = requests.post("https://mis.taifex.com.tw/futures/api/getQuoteDetail", json={"SymbolID": ["TXF-M", "TXFL6-M", "TXFA7-M"]}, headers=headers_mis, timeout=6, verify=False)
        if r_night.status_code == 200:
            for q in (((r_night.json().get("RtData") or {}).get("QuoteList")) or []):
                lp = safe_float(q.get("CLastPrice") or q.get("ChtPrice"), 0.0)
                rp = safe_float(q.get("CRefPrice") or q.get("COpenPrice"), lp)
                df_v = safe_float(q.get("CDiff"), lp - rp)
                pct_v = safe_float(q.get("CDiffRate"), (df_v / rp * 100) if rp > 0 else 0.0)
                if lp > 15000:
                    night_txf = {"price": round(lp, 2), "change": round(df_v, 2), "change_pct": round(pct_v, 2), "label": "夜盤"}
                    break
    except Exception:
        pass

    if day_txf:
        extra["TXF"] = {
            "price": day_txf["price"], "prev_close": day_txf["prev_close"],
            "change": day_txf["change"], "change_pct": day_txf["change_pct"],
            "history": [{"date": now_tw.strftime("%Y-%m-%d"), "close": day_txf["price"]}],
            "ext_session": night_txf
        }
    return extra

def parse_sectors_and_symbols_from_js(js_path="supply_chain_db.js"):
    items_map, sector_stocks_map = {}, {}
    if not os.path.exists(js_path):
        return items_map, sector_stocks_map
    try:
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        sec_blocks = re.split(r'\{\s*id\s*:\s*"', content)[1:]
        triple_pat = re.compile(r'\[\s*"([A-Za-z0-9\.\-\^=]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]')
        for blk in sec_blocks:
            sec_id = blk.split('"')[0].strip()
            sector_stocks_map.setdefault(sec_id, [])
            for m in triple_pat.finditer(blk):
                sym, name, role = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                if sym in DELISTED_BLACKLIST:
                    continue
                items_map[sym] = {"symbol": sym, "name": to_trad(name), "role": to_trad(role)}
                if sym not in sector_stocks_map[sec_id]:
                    sector_stocks_map[sec_id].append(sym)
    except Exception:
        pass
    return items_map, sector_stocks_map

def build_stock_specific_sentiment_and_news(symbol, display_name, f_obj, mops_by_code, fetch_rss=False):
    tw_code = symbol.split(".")[0] if (symbol.endswith(".TW") or symbol.endswith(".TWO")) else None
    fund_bulls, fund_bears = [], []
    m_rev = f_obj.get("monthly_rev")

    if tw_code:
        if tw_code in mops_by_code:
            for mp in mops_by_code[tw_code][:3]:
                fund_bulls.append({"title": f"[MOPS重訊] {mp['subject']}", "url": mp["url"], "date": f"MOPS・{mp['date']} {mp['time']}"})
        if m_rev:
            yoy_v, mom_v = safe_float(m_rev.get("yoy"), 0.0), safe_float(m_rev.get("mom"), 0.0)
            rev_entry = {"title": f"[MOPS月營收 ({m_rev['month']})] 單月營收 {m_rev['revenue_yi']} (MoM {mom_v:+.2f}% / YoY {yoy_v:+.2f}%)", "url": "https://mops.twse.com.tw/mops/#/web/t05st10_ifrs", "date": "證交所/櫃買中心 OpenAPI"}
            (fund_bulls if yoy_v >= 0 else fund_bears).append(rev_entry)

    fin_url = "https://mops.twse.com.tw/mops/#/web/t163sb04" if tw_code else f"https://finance.yahoo.com/quote/{symbol}/financials/"
    fin_src = "MOPS 財務報表 / TradingView" if tw_code else f"SEC Filings / Yahoo Finance ({symbol})"
    fund_bulls.append({"title": f"[最新財報實績] EPS {f_obj.get('eps')}、ROE {f_obj.get('roe')}、毛利率 {f_obj.get('gross_margin')}、營益率 {f_obj.get('operating_margin')}、季營收年增 {f_obj.get('yoy_rev_growth')}", "url": fin_url, "date": fin_src})
    fund_bears.append({"title": f"[估值水位檢視] 本益比 PE {f_obj.get('pe')} 倍、預估本益比 {f_obj.get('forward_pe')}", "url": fin_url, "date": fin_src})

    ev_bulls, ev_bears = [], []
    if fetch_rss:
        for n_item in fetch_google_news_rss_for_stock(display_name if tw_code else f"{symbol} stock", max_items=4):
            if any(k in n_item["title"] for k in ["跌", "砍", "賣超", "下滑", "虧損", "降評", "利空", "重挫", "fall", "drop", "cut"]):
                ev_bears.append(n_item)
            else:
                ev_bulls.append(n_item)

    news_search_url = f"https://news.google.com/search?q={quote(display_name)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    if not ev_bulls:
        ev_bulls.append({"title": f"🔗 檢視「{display_name} ({symbol})」Google 新聞最新報導", "url": news_search_url, "date": "Google News"})
    if not ev_bears:
        ev_bears.append({"title": f"🔗 檢視「{display_name} ({symbol})」最新風險與法人籌碼報導", "url": news_search_url, "date": "Google News"})

    return {
        "bullish": [fund_bulls[0], ev_bulls[0]],
        "bearish": [fund_bears[0], ev_bears[0]],
        "categories": {
            "fundamentals_mops": {"label": "📑 MOPS重訊・最新月營收・財報指標" if tw_code else "📑 SEC最新財報・季營收・獲利指標", "bullish": fund_bulls, "bearish": fund_bears},
            "events": {"label": "📰 產業與個股新聞時事 (附來源連結)", "bullish": ev_bulls, "bearish": ev_bears}
        }
    }

def build_asset_object(symbol, display_name, asset_type, future_group, yf_map, tw_official, us_fund_map, rev_map, mops_by_code, fetch_rss=False):
    dec = 4 if (asset_type == "fx_rate" and symbol not in ["JPY=X", "TWD=X"]) else 2
    tw_code = symbol.split(".")[0] if (symbol.endswith(".TW") or symbol.endswith(".TWO")) else None
    y_data = yf_map.get(symbol) or {}
    hist = y_data.get("history") or []
    tv_f = (tw_official.get("fund_map", {}).get(tw_code) if tw_code else us_fund_map.get(symbol)) or {}

    p_val = safe_float(y_data.get("price"), 0.0)
    prev_val = safe_float(y_data.get("prev_close"), p_val)
    chg_val = safe_float(y_data.get("change"), 0.0)
    pct_val = safe_float(y_data.get("change_pct"), 0.0)
    ext_obj = None if symbol in ["BTC-USD", "ETH-USD"] else y_data.get("ext_session")

    if tw_official:
        if symbol in tw_official.get("indices", {}):
            off_idx = tw_official["indices"][symbol]
            if off_idx["price"] > 0:
                p_val, prev_val, chg_val, pct_val = off_idx["price"], off_idx["prev_close"], off_idx["change"], off_idx["change_pct"]
                today_str = now_tw.strftime("%Y-%m-%d")
                if not hist:
                    hist = [{"date": today_str, "close": p_val}]
                elif hist[-1]["date"] != today_str:
                    hist.append({"date": today_str, "close": p_val})
                else:
                    hist[-1]["close"] = p_val
        elif tw_code and tw_code in tw_official.get("stocks", {}):
            offs = tw_official["stocks"][tw_code]
            if offs["price"] > 0:
                p_val, prev_val, chg_val, pct_val = offs["price"], offs["prev_close"], offs["change"], offs["change_pct"]
                today_str = now_tw.strftime("%Y-%m-%d")
                if not hist:
                    hist = [{"date": today_str, "close": p_val}]
                elif hist[-1]["date"] != today_str:
                    hist.append({"date": today_str, "close": p_val})
                else:
                    hist[-1]["close"] = p_val

    f_dict = {
        "pe": tv_f.get("pe", "N/A"), "forward_pe": tv_f.get("forward_pe", "無預估"),
        "eps": tv_f.get("eps", "N/A"), "gross_margin": tv_f.get("gross_margin", "N/A"),
        "operating_margin": tv_f.get("operating_margin", "N/A"), "roe": tv_f.get("roe", "N/A"),
        "yoy_rev_growth": tv_f.get("yoy_rev_growth", "N/A"),
        "monthly_rev": rev_map.get(tw_code) if tw_code else None
    }

    ns_obj = build_stock_specific_sentiment_and_news(symbol, to_trad(display_name), f_dict, mops_by_code, fetch_rss=fetch_rss) if asset_type in ["us_stock", "tw_stock"] else None

    return {
        "symbol": symbol, "name": to_trad(display_name), "asset_type": asset_type, "future_group": future_group,
        "price": round(p_val, dec), "prev_close": round(prev_val, dec), "change": round(chg_val, dec), "change_pct": round(pct_val, 2),
        "ext_session": ext_obj, "intraday": [], "history": hist,
        "fundamentals": f_dict, "news_sentiment": ns_obj
    }

def main():
    t0 = time.time()
    os.makedirs("data", exist_ok=True)
    payload = {
        "last_updated": now_tw.strftime("%Y-%m-%d %H:%M:%S CST"),
        "indices": [], "vix_indices": [], "fear_greed": fetch_fear_and_greed_indices(),
        "us_bonds": [], "fx_rates": [], "fx_bonds": [],
        "us_stocks": [], "tw_stocks": [], "futures_commodities": [],
        "supply_chain_sectors": [], "tw_chips_visual": {}, "mops_general": []
    }

    try:
        sc_items_map, _ = parse_sectors_and_symbols_from_js("supply_chain_db.js")
        all_us_eq = list(set(US_STOCKS + [s for s in sc_items_map.keys() if not (s.endswith(".TW") or s.endswith(".TWO"))]))

        rev_map = fetch_official_tw_monthly_revenues()
        mops_by_code, mops_general = fetch_official_mops_material_news()
        payload["mops_general"] = mops_general

        tw_official = fetch_tw_official_all_channels()
        us_fund_map = fetch_tradingview_us_fundamentals(all_us_eq)
        payload["tw_chips_visual"] = fetch_twse_official_margin_and_maintenance()

        all_required_syms = (
            list(INDICES.keys()) + list(VIX_INDICES.keys()) + list(US_BONDS.keys()) + list(FX_RATES.keys()) +
            list(US_STOCKS) + [m["ticker"] for m in TW_STOCKS.values()] +
            list(FUTURES_AND_COMMODITIES.keys()) + list(sc_items_map.keys())
        )

        yf_map = download_all_yf_histories_and_ext(all_required_syms, all_us_eq)
        yf_map.update(fetch_official_us2y_and_taifex_vixtwn_and_txf(yf_map))

        # 使用 TradingView 官方交易所期貨報價同步原油、金屬與美指期貨
        for f_sym, f_q in fetch_tradingview_futures_quotes().items():
            if f_sym in yf_map:
                yf_map[f_sym].update(f_q)
            else:
                yf_map[f_sym] = {**f_q, "history": [{"date": now_tw.strftime("%Y-%m-%d"), "close": f_q["price"]}]}

        core_rss_set = set(US_STOCKS + [m["ticker"] for m in TW_STOCKS.values()])
        built_cache = {}
        def get_asset(sym, name, a_type, f_group=None):
            if sym not in built_cache:
                built_cache[sym] = build_asset_object(sym, name, a_type, f_group, yf_map, tw_official, us_fund_map, rev_map, mops_by_code, fetch_rss=(sym in core_rss_set))
            cp = dict(built_cache[sym])
            cp["name"] = to_trad(name)
            if f_group:
                cp["future_group"] = f_group
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
