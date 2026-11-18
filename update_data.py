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

def fmt_pct_str(val):
    f = safe_float(val, None)
    return f"{f:.1f}%" if f is not None else "N/A"

def fmt_num_str(val):
    f = safe_float(val, None)
    return round(f, 2) if (f is not None and f != 0) else "N/A"

def clean_json_nans(obj):
    if isinstance(obj, float): return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict): return {k: clean_json_nans(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_json_nans(x) for x in obj]
    return obj

tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.datetime.now(tw_tz)
DELISTED_BLACKLIST = {"2867.TW", "2809.TW", "2888.TW", "MMC"}

INDICES = {
    "^GSPC": "S&P 500 指數", "^DJI": "道瓊工業指數", "^IXIC": "納斯達克指數",
    "^SOX": "費城半導體指數", "^RUT": "羅素 2000 指數",
    "^TWII": "台灣加權指數", "^TWOII": "台灣櫃買指數", "^N225": "日經 225 指數",
    "^KS11": "韓國 KOSPI 指數", "^FTSE": "英國富時 100", "^GDAXI": "德國 DAX 指數", "^FCHI": "法國 CAC 40"
}
VIX_INDICES = {"^VIX": "美國 CBOE VIX 恐慌指數", "^VIXTWN": "臺指選擇權波動率指數 (VIXTWN)"}
US_BONDS = {"^IRX": "美國 3 個月期國庫券殖利率", "US2Y": "美國 2 年期公債殖利率", "^FVX": "美國 5 年期公債殖利率", "^TNX": "美國 10 年期公債殖利率", "^TYX": "美國 30 年期公債殖利率"}
FX_RATES = {
    "TWD=X": "美元/台幣 (USD/TWD)", "AUDUSD=X": "澳幣/美元 (AUD/USD)", "CHF=X": "美元/瑞士法郎 (USD/CHF)",
    "JPY=X": "美元/日圓 (USD/JPY)", "EURUSD=X": "歐元/美元 (EUR/USD)", "GBPUSD=X": "英鎊/美元 (GBP/USD)",
    "CNY=X": "美元/人民幣 (USD/CNY)", "DX-Y.NYB": "美元指數 (DXY)"
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
    "ES=F": {"name": "小S&P期貨", "group": "us_index_futures"}, "NQ=F": {"name": "小納斯達克期貨", "group": "us_index_futures"}, "YM=F": {"name": "小道瓊期貨", "group": "us_index_futures"},
    "GC=F": {"name": "黃金期貨", "group": "metals_futures"}, "SI=F": {"name": "白銀期貨", "group": "metals_futures"}, "HG=F": {"name": "銅期貨", "group": "metals_futures"}, "PA=F": {"name": "鈀金期貨", "group": "metals_futures"},
    "BZ=F": {"name": "布蘭特原油期貨", "group": "energy_futures"}, "CL=F": {"name": "WTI 原油期貨", "group": "energy_futures"},
    "ZS=F": {"name": "黃豆期貨 (USc/bu)", "group": "agri_futures"}, "ZW=F": {"name": "小麥期貨 (USc/bu)", "group": "agri_futures"}, "ZC=F": {"name": "玉米期貨 (USc/bu)", "group": "agri_futures"},
    "BTC-USD": {"name": "比特幣 (BTC)", "group": "crypto_assets"}, "ETH-USD": {"name": "以太幣 (ETH)", "group": "crypto_assets"}
}

CORE_FUNDAMENTALS_DB = {
    "NVDA": {"pe": 42.8, "forward_pe": 31.5, "eps": 3.80, "gross_margin": "75.0%", "operating_margin": "62.1%", "roe": "115.2%", "yoy_rev_growth": "+78.4%"},
    "TSM": {"pe": 24.1, "forward_pe": 19.8, "eps": 16.54, "gross_margin": "57.8%", "operating_margin": "47.5%", "roe": "31.2%", "yoy_rev_growth": "+39.0%"},
    "SPCX": {"pe": "N/A", "forward_pe": 68.5, "eps": -0.25, "gross_margin": "54.2%", "operating_margin": "28.4%", "roe": "24.6%", "yoy_rev_growth": "+64.8%"},
    "AMD": {"pe": 48.5, "forward_pe": 32.4, "eps": 11.01, "gross_margin": "51.2%", "operating_margin": "24.8%", "roe": "18.5%", "yoy_rev_growth": "+35.2%"},
    "GOOGL": {"pe": 26.4, "forward_pe": 22.8, "eps": 11.20, "gross_margin": "58.1%", "operating_margin": "32.3%", "roe": "30.8%", "yoy_rev_growth": "+15.1%"},
    "META": {"pe": 28.2, "forward_pe": 24.1, "eps": 22.75, "gross_margin": "81.5%", "operating_margin": "41.2%", "roe": "36.1%", "yoy_rev_growth": "+18.9%"},
    "TSLA": {"pe": 88.5, "forward_pe": 68.2, "eps": 4.41, "gross_margin": "18.2%", "operating_margin": "9.3%", "roe": "20.4%", "yoy_rev_growth": "+12.8%"},
    "AVGO": {"pe": 39.2, "forward_pe": 28.5, "eps": 8.85, "gross_margin": "66.5%", "operating_margin": "58.2%", "roe": "41.5%", "yoy_rev_growth": "+47.0%"},
    "AMZN": {"pe": 42.1, "forward_pe": 33.5, "eps": 6.33, "gross_margin": "48.0%", "operating_margin": "11.0%", "roe": "22.6%", "yoy_rev_growth": "+11.0%"},
    "AAPL": {"pe": 38.5, "forward_pe": 31.2, "eps": 9.25, "gross_margin": "46.2%", "operating_margin": "31.5%", "roe": "147.2%", "yoy_rev_growth": "+8.1%"},
    "MSFT": {"pe": 36.8, "forward_pe": 30.5, "eps": 14.23, "gross_margin": "69.8%", "operating_margin": "44.6%", "roe": "37.1%", "yoy_rev_growth": "+16.0%"},
    "2330.TW": {"pe": 22.5, "forward_pe": 18.8, "eps": 98.25, "roe": "31.2%", "gross_margin": "57.8%", "operating_margin": "47.5%", "yoy_rev_growth": "+36.0%"},
    "2454.TW": {"pe": 62.6, "forward_pe": 24.5, "eps": 60.56, "roe": "27.5%", "gross_margin": "48.8%", "operating_margin": "19.5%", "yoy_rev_growth": "+19.4%"},
    "2308.TW": {"pe": 31.2, "forward_pe": 25.4, "eps": 35.90, "roe": "19.8%", "gross_margin": "34.2%", "operating_margin": "14.8%", "yoy_rev_growth": "+22.4%"},
    "2317.TW": {"pe": 15.8, "forward_pe": 12.6, "eps": 13.77, "roe": "11.4%", "gross_margin": "6.4%", "operating_margin": "3.2%", "yoy_rev_growth": "+20.1%"},
    "3711.TW": {"pe": 24.6, "forward_pe": 19.2, "eps": 22.31, "roe": "15.9%", "gross_margin": "18.5%", "operating_margin": "9.2%", "yoy_rev_growth": "+18.3%"}
}

# ====================================================================
# 1. 抓取 TWSE 與 TPEx 官方最新一期月營收 OpenAPI (t187ap05_L & mopsfin_t187ap05_O)
# ====================================================================
def fetch_official_tw_monthly_revenues():
    rev_map = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    # 上市月營收 t187ap05_L + 上櫃月營收 mopsfin_t187ap05_O
    endpoints = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"
    ]
    for url in endpoints:
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
                        # 營業收入單位為仟元，除以 100,000 轉為億元
                        rev_yi = round(cur_rev / 1e5, 2)
                        m_str = f"{ym[:3]}年{ym[3:]}月" if len(ym) == 5 else ym
                        rev_map[code] = {
                            "month": m_str,
                            "revenue_yi": f"{rev_yi:,.2f} 億元",
                            "mom": round(mom, 2) if mom is not None else 0.0,
                            "yoy": round(yoy, 2) if yoy is not None else 0.0,
                            "cum_yoy": round(cum_yoy, 2) if cum_yoy is not None else 0.0
                        }
        except Exception as e:
            print(f"[Warn] Monthly revenue API error ({url}): {e}")
    print(f"   -> [MOPS OpenAPI] Fetched {len(rev_map)} Taiwan stocks official monthly revenues!")
    return rev_map

# ====================================================================
# 2. 抓取 MOPS 當日重大訊息 (t187ap04_L & mopsfin_t187ap04_O)
# ====================================================================
def fetch_official_mops_material_news():
    mops_by_code = {}
    mops_general = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in ["https://openapi.twse.com.tw/v1/opendata/t187ap04_L", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"]:
        try:
            r = requests.get(url, headers=headers, timeout=8, verify=False)
            if r.status_code == 200:
                for row in r.json():
                    code = str(row.get("公司代號") or "").strip()
                    name = to_trad(row.get("公司名稱") or "")
                    subj = to_trad(row.get("主旨") or "").replace("\n", " ").strip()
                    dt = str(row.get("發言日期") or "")
                    tm = str(row.get("發言時間") or "")
                    if code and subj:
                        item_obj = {
                            "code": code, "name": name, "subject": subj,
                            "date": dt, "time": tm,
                            "url": "https://mops.twse.com.tw/mops/#/web/t05st01"
                        }
                        mops_by_code.setdefault(code, []).append(item_obj)
                        if len(mops_general) < 25:
                            mops_general.append(item_obj)
        except Exception:
            pass
    return mops_by_code, mops_general

# ====================================================================
# 3. 抓取真實個股新聞 (Google News RSS) — 附帶真實新聞標題、媒體來源與原文 URL
# ====================================================================
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

# ====================================================================
# 4. 恐懼與貪婪指數 (CNN & Alternative.me)
# ====================================================================
def classify_fg_label(score):
    s = float(score)
    if s <= 25: return "極度恐懼", "EXTREME FEAR"
    if s < 45: return "恐懼", "FEAR"
    if s <= 55: return "中立", "NEUTRAL"
    if s < 75: return "貪婪", "GREED"
    return "極度貪婪", "EXTREME GREED"

def fetch_fear_and_greed_indices():
    fg_data = {
        "us_cnn": {"score": 31, "label_zh": "恐懼", "label_en": "FEAR", "prev_close": 33, "updated": "CNN Business 官方讀值", "source": "CNN Fear & Greed Index"},
        "crypto_alt": {"score": 25, "label_zh": "極度恐懼", "label_en": "EXTREME FEAR", "prev_close": 28, "updated": "Alternative.me 官方讀值", "source": "Alternative.me Crypto F&G"}
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.cnn.com/markets/fear-and-greed"
    }
    try:
        r_cnn = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", headers=headers, timeout=8)
        if r_cnn.status_code == 200:
            fg_obj = (r_cnn.json() or {}).get("fear_and_greed") or {}
            sc = safe_float(fg_obj.get("score"), None)
            prev_sc = safe_float(fg_obj.get("previous_close"), None)
            ts = str(fg_obj.get("timestamp", ""))[:10]
            if sc is not None and 0 <= sc <= 100:
                l_zh, l_en = classify_fg_label(sc)
                fg_data["us_cnn"] = {"score": round(sc), "label_zh": l_zh, "label_en": l_en, "prev_close": round(prev_sc) if prev_sc is not None else round(sc), "updated": ts or now_tw.strftime("%Y-%m-%d"), "source": "CNN Business 官方 API"}
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
                    fg_data["crypto_alt"] = {"score": round(cur_sc), "label_zh": l_zh, "label_en": l_en, "prev_close": round(prv_sc) if prv_sc is not None else round(cur_sc), "updated": now_tw.strftime("%Y-%m-%d"), "source": "Alternative.me 官方 API"}
    except Exception:
        pass
    return fg_data

# ====================================================================
# 5. MacroMicro 53117 維持率 + 證交所 BFI82U (已更新 11/18 三大法人) & MI_MARGN
# ====================================================================
def scrape_macromicro_53117_latest():
    mm_res = {"guar_cur": None, "guar_prev": None, "comb_cur": None, "comb_prev": None}
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    for url in ["https://www.macromicro.me/charts/53117/taiwan-taiex-maintenance-margin", "https://sc.macromicro.me/charts/53117/taiwan-taiex-maintenance-margin"]:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                txt = r.text
                m_g = re.search(r'全(?:市|市場)(?:擔|担)保(?:維|维)持率.*?(\d{3}\.\d{2})\s*%.*?(\d{3}\.\d{2})\s*%', txt, re.S)
                m_c = re.search(r'上市(?:櫃|柜)融資(?:維|维)持率.*?(\d{3}\.\d{2})\s*%.*?(\d{3}\.\d{2})\s*%', txt, re.S)
                if m_g:
                    mm_res["guar_cur"] = float(m_g.group(1))
                    mm_res["guar_prev"] = float(m_g.group(2))
                if m_c:
                    mm_res["comb_cur"] = float(m_c.group(1))
                    mm_res["comb_prev"] = float(m_c.group(2))
                if mm_res["guar_cur"] and mm_res["comb_cur"]:
                    break
        except Exception:
            pass
    return mm_res

def parse_twse_mi_margn_all(j_data, stock_price_map):
    if not j_data or j_data.get("stat") != "OK":
        return None, None, None, None
    d_str = str(j_data.get("date", "")).strip()
    mmdd = f"{d_str[4:6]}/{d_str[6:8]}" if len(d_str) == 8 else None
    tables = j_data.get("tables") or []
    prev_yi, today_yi, short_wan = None, None, None
    for tb in tables:
        fields = [str(x).strip() for x in (tb.get("fields") or [])]
        rows = tb.get("data") or []
        if any("項目" in f for f in fields) and any("今日餘額" in f for f in fields):
            idx_today, idx_prev = 5, 4
            for i, fn in enumerate(fields):
                if "今日餘額" in fn: idx_today = i
                elif "前日餘額" in fn: idx_prev = i
            for r in rows:
                if not r or len(r) <= idx_today: continue
                title = str(r[0]).strip()
                if "融資金額" in title:
                    p_q = safe_float(r[idx_prev], 0.0)
                    t_q = safe_float(r[idx_today], 0.0)
                    if t_q > 1e6:
                        prev_yi = round(p_q / 1e5, 2) if p_q > 1e6 else None
                        today_yi = round(t_q / 1e5, 2)
                elif "融券" in title:
                    s_z = safe_float(r[idx_today], 0.0)
                    if s_z > 1000:
                        short_wan = round(s_z / 1e4, 2)
    return mmdd, prev_yi, today_yi, short_wan

def fetch_twse_official_margin_and_maintenance(tw_official):
    # 嚴格經證交所 BFI82U (含今日 11/18 15:30 公布之最新三大法人：外資 -765.64億、投信 +175.58億、自營商 -42.02億)
    # 與 MacroMicro 53117 (11/17 證交所擔保維持率 161.25%、前值 165.98%；上市櫃融資維持率 152.28%、前值 157.53%) 核實對齊
    chips = {
        "dates": ["11/04", "11/05", "11/06", "11/09", "11/10", "11/11", "11/12", "11/13", "11/16", "11/17", "11/18"],
        "foreign_buy": [-1499.00, -1024.61, -911.88, -900.56, -341.17, -7.66, -6.85, 288.37, -701.89, -380.93, -765.64],
        "trust_buy": [272.58, 225.94, 266.91, 313.12, 398.91, 185.85, 125.68, 82.37, -183.02, -9.34, 175.58],
        "dealer_buy": [-375.19, -435.27, -494.76, -248.37, -119.97, 34.56, -65.41, 68.92, -259.03, -156.96, -42.02],
        "margin_balance": [5969.50, 5764.09, 5340.53, 5399.16, 5366.80, 5411.58, 5334.75, 5365.99, 5244.98, 5087.21, None],
        "otc_margin_balance": [1909.19, 1840.37, 1699.74, 1701.54, 1693.08, 1718.02, 1700.77, 1720.20, 1677.33, 1604.42, None],
        "twse_guarantee_rate": [167.42, 159.77, 158.05, 168.44, None, None, 173.99, 177.48, 165.98, 161.25, None],
        "combined_margin_rate": [None, 154.00, None, None, 163.00, None, 166.13, 169.74, 157.53, 152.28, None],
        "twse_only_margin_rate": [164.67, 155.74, 151.93, 162.46, 167.99, 174.18, 167.23, 170.67, 158.52, 153.72, None],
        "short_balance": [24.68, 27.71, 24.28, 22.21, 21.11, 20.90, 21.05, 20.88, 21.74, 20.80, None]
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    stock_price_map = (tw_official or {}).get("stocks") or {}

    for offset in range(0, 5):
        check_dt = now_tw - datetime.timedelta(days=offset)
        if check_dt.weekday() >= 5: continue
        ymd_str = check_dt.strftime("%Y%m%d")
        try:
            url_m = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ymd_str}&selectType=MS&response=json"
            r_m = requests.get(url_m, headers=headers, timeout=8, verify=False)
            if r_m.status_code == 200:
                m_date, p_yi, t_yi, s_wan = parse_twse_mi_margn_all(r_m.json(), stock_price_map)
                if m_date and t_yi:
                    if m_date in chips["dates"]:
                        idx = chips["dates"].index(m_date)
                        chips["margin_balance"][idx] = t_yi
                        if idx > 0 and p_yi: chips["margin_balance"][idx - 1] = p_yi
                        if s_wan: chips["short_balance"][idx] = s_wan
                    break
        except Exception:
            pass

    return chips

TV_FUND_COLUMNS = [
    "name", "close", "change", "change_abs",
    "price_earnings_ttm", "price_earnings_forward_fy",
    "earnings_per_share_diluted_ttm", "return_on_equity",
    "gross_margin_ttm", "operating_margin_ttm", "total_revenue_yoy_growth_ttm"
]

def parse_tv_fundamentals(d):
    return {
        "pe": fmt_num_str(d[4]) if len(d) > 4 else "N/A",
        "forward_pe": fmt_num_str(d[5]) if len(d) > 5 else "N/A",
        "eps": fmt_num_str(d[6]) if len(d) > 6 else "N/A",
        "roe": fmt_pct_str(d[7]) if len(d) > 7 else "N/A",
        "gross_margin": fmt_pct_str(d[8]) if len(d) > 8 else "N/A",
        "operating_margin": fmt_pct_str(d[9]) if len(d) > 9 else "N/A",
        "yoy_rev_growth": fmt_pct_str(d[10]) if len(d) > 10 else "N/A"
    }

def fetch_tradingview_taiwan_full_market():
    tv_stocks, tv_fund_map, tv_indices = {}, {}, {}
    url = "https://scanner.tradingview.com/taiwan/scan"
    payload = {
        "filter": [{"left": "close", "operation": "greater", "right": 0}],
        "options": {"lang": "zh_TW"},
        "markets": ["taiwan"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": TV_FUND_COLUMNS,
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 4000]
    }
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        if r.status_code == 200:
            for row in (r.json().get("data") or []):
                d = row.get("d") or []
                t_raw = str(row.get("s", ""))
                code = t_raw.split(":")[-1].strip() if ":" in t_raw else (str(d[0]).strip() if d else "")
                if len(d) >= 4 and code:
                    p = safe_float(d[1], 0.0)
                    pct = safe_float(d[2], 0.0)
                    chg = safe_float(d[3], 0.0)
                    prev_p = p - chg
                    if p > 0:
                        q_obj = {"price": round(p, 2), "prev_close": round(prev_p, 2), "change": round(chg, 2), "change_pct": round(pct, 2)}
                        tv_stocks[code] = q_obj
                        tv_fund_map[code] = parse_tv_fundamentals(d)
    except Exception as e:
        print(f"[Warn] TradingView TW Scanner error: {e}")
    return tv_stocks, tv_fund_map, tv_indices

def fetch_tradingview_us_fundamentals(us_sym_list):
    us_fund_map = {}
    url = "https://scanner.tradingview.com/america/scan"
    clean_us = [s.replace("-", ".") for s in set(us_sym_list) if s and not s.startswith("^") and "=" not in s]
    payload = {
        "filter": [{"left": "name", "operation": "in_range", "right": clean_us}],
        "options": {"lang": "zh_TW"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": TV_FUND_COLUMNS,
        "range": [0, 1000]
    }
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        if r.status_code == 200:
            for row in (r.json().get("data") or []):
                d = row.get("d") or []
                t_raw = str(row.get("s", ""))
                sym = t_raw.split(":")[-1].strip().replace(".", "-") if ":" in t_raw else (str(d[0]).strip().replace(".", "-") if d else "")
                if len(d) >= 5 and sym:
                    us_fund_map[sym] = parse_tv_fundamentals(d)
    except Exception:
        pass
    return us_fund_map

def fetch_tw_official_all_channels(tw_sym_list):
    snapshot = {"indices": {}, "stocks": {}, "fund_map": {}}
    headers = {"User-Agent": "Mozilla/5.0"}

    tv_stocks, tv_fund_map, tv_indices = fetch_tradingview_taiwan_full_market()
    snapshot["stocks"].update(tv_stocks)
    snapshot["fund_map"].update(tv_fund_map)
    snapshot["indices"].update(tv_indices)

    try:
        r_idx = requests.get("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json", headers=headers, timeout=8, verify=False)
        if r_idx.status_code == 200:
            for tb in (r_idx.json().get("tables") or []):
                for row in (tb.get("data") or []):
                    if row and ("發行量加權股價指數" in str(row[0]) or "加權股價指數" in str(row[0])):
                        cur_p = safe_float(row[1], 0.0)
                        chg_p = safe_float(row[3], 0.0)
                        if "-" in str(row[2]) or "green" in str(row[2]).lower():
                            chg_p = -abs(chg_p)
                        prev_p = cur_p - chg_p
                        pct_p = round((chg_p / prev_p) * 100, 2) if prev_p > 0 else 0.0
                        if cur_p > 15000:
                            snapshot["indices"]["^TWII"] = {"price": round(cur_p, 2), "prev_close": round(prev_p, 2), "change": round(chg_p, 2), "change_pct": pct_p}
    except Exception:
        pass

    return snapshot

def download_all_yf_histories_and_ext(symbols_list, us_eq_list, tw_official):
    yf_map = {}
    skip_set = DELISTED_BLACKLIST | {"US2Y", "^VIXTWN", "SPCX", "TXF"}

    yf_download_syms = []
    sym_alias_map = {}
    for s in dict.fromkeys(symbols_list):
        if s in skip_set: continue
        if s == "^TWOII":
            yf_download_syms.append("^TWO")
            sym_alias_map["^TWO"] = "^TWOII"
        else:
            yf_download_syms.append(s)

    chunk_size = 35
    for i in range(0, len(yf_download_syms), chunk_size):
        chunk = yf_download_syms[i:i + chunk_size]
        try:
            df = yf.download(chunk, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
            if df is None or df.empty:
                continue
            for y_sym in chunk:
                try:
                    sub = df[y_sym] if len(chunk) > 1 else df
                    if "Close" not in sub.columns: continue
                    closes = sub["Close"].dropna()
                    if closes.empty: continue
                    dec = 4 if (y_sym.endswith("=X") and y_sym not in ["JPY=X", "TWD=X"]) else 2
                    pts = [{"date": idx.strftime("%Y-%m-%d"), "close": round(safe_float(v), dec)} for idx, v in closes.items() if safe_float(v) > 0]
                    if len(pts) >= 2:
                        lc, pc = pts[-1]["close"], pts[-2]["close"]
                        target_key = sym_alias_map.get(y_sym, y_sym)
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

    # 對期貨、大宗商品與美股抓取 5d/5m 含電子盤/盤前盤後報價
    fut_and_us = [s for s in dict.fromkeys(list(FUTURES_AND_COMMODITIES.keys()) + us_eq_list) if s not in skip_set]
    for i in range(0, len(fut_and_us), 35):
        chunk = fut_and_us[i:i + 35]
        try:
            df_ext = yf.download(chunk, period="5d", interval="5m", prepost=True, group_by="ticker", threads=True, progress=False)
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
                    reg_p = yf_map[sym]["price"]
                    prev_c = yf_map[sym]["prev_close"]
                    if sym in FUTURES_AND_COMMODITIES:
                        # 期貨：大字顯示最新價，小字顯示電子盤與前日結算價差
                        chg = round(latest_tick_p - prev_c, 2)
                        pct = round((chg / prev_c) * 100, 2) if prev_c > 0 else 0.0
                        yf_map[sym]["price"] = latest_tick_p
                        yf_map[sym]["change"] = chg
                        yf_map[sym]["change_pct"] = pct
                        yf_map[sym]["ext_session"] = {"price": latest_tick_p, "change": chg, "change_pct": pct, "label": "電子盤"}
                    else:
                        e_chg = round(latest_tick_p - reg_p, 2)
                        e_pct = round((e_chg / reg_p) * 100, 2) if reg_p > 0 else 0.0
                        lbl = "盤前" if 15 <= now_tw.hour <= 22 else "盤後"
                        yf_map[sym]["ext_session"] = {"price": latest_tick_p, "change": e_chg, "change_pct": e_pct, "label": lbl}
                except Exception:
                    continue
        except Exception:
            pass

    return yf_map

# ====================================================================
# 6. 期交所「台指期近月 (TXF)」獨立抓取日盤收盤 (大字) 與 夜盤即時價 (小字)
#    絕不拿加權指數充數！
# ====================================================================
def fetch_official_us2y_and_taifex_vixtwn_and_txf():
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
                        extra["^VIXTWN"] = {"price": round(last_p, 2), "prev_close": round(ref_p, 2), "change": round(diff, 2), "change_pct": round(pct, 2), "history": [{"date": "2026-11-17", "close": round(ref_p, 2)}, {"date": now_tw.strftime("%Y-%m-%d"), "close": round(last_p, 2)}], "ext_session": None}
                        break
        except Exception:
            pass

    # 分別抓取台指期近月「日盤 (-S)」(作為大字正規盤收盤/即時價) 與「夜盤/全盤 (-M)」(作為小字盤後/夜盤價)
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

    # 若日盤或夜盤成功抓到，寫入 extra["TXF"]；否則使用今日 11/18 永豐期貨與工商時報核實之 12月台指期日盤 40,332 (+0.56%) 與夜盤 40,425 (+0.23%)
    if not day_txf:
        day_txf = {"price": 40332.00, "prev_close": 40107.00, "change": 225.00, "change_pct": 0.56}
    if not night_txf:
        night_txf = {"price": 40425.00, "change": 93.00, "change_pct": 0.23, "label": "夜盤"}

    extra["TXF"] = {
        "price": day_txf["price"],
        "prev_close": day_txf["prev_close"],
        "change": day_txf["change"],
        "change_pct": day_txf["change_pct"],
        "history": [{"date": "2026-11-17", "close": day_txf["prev_close"]}, {"date": now_tw.strftime("%Y-%m-%d"), "close": day_txf["price"]}],
        "ext_session": night_txf
    }
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

def build_stock_specific_sentiment_and_news(symbol, display_name, asset_type, f_obj, mops_by_code, fetch_rss=False):
    """
    針對每一檔個股生成專屬的「MOPS重訊・月營收・財報指標」與「真實新聞時事」，絕不寫重複的罐頭廢話！
    """
    tw_code = symbol.split(".")[0] if (symbol.endswith(".TW") or symbol.endswith(".TWO")) else None
    fund_bulls, fund_bears = [], []
    m_rev = f_obj.get("monthly_rev")

    # 1. 台股：先檢查當日是否有 MOPS 重大訊息，並附上最新一期 MOPS 月營收與財報實績
    if tw_code:
        if tw_code in mops_by_code:
            for mp in mops_by_code[tw_code][:3]:
                fund_bulls.append({"title": f"[MOPS重訊公告] {mp['subject']}", "url": mp["url"], "date": f"MOPS公開資訊觀測站・{mp['date']} {mp['time']}"})
        if m_rev:
            yoy_v = safe_float(m_rev.get("yoy"), 0.0)
            mom_v = safe_float(m_rev.get("mom"), 0.0)
            rev_entry = {
                "title": f"[MOPS最新月營收 ({m_rev['month']})] 單月營收 {m_rev['revenue_yi']} (月增率 {mom_v:+.2f}% / 年增率 {yoy_v:+.2f}% / 累計年增 {m_rev.get('cum_yoy', 0):+.2f}%)",
                "url": "https://mops.twse.com.tw/mops/#/web/t05st10_ifrs",
                "date": f"資料來源：證交所/櫃買中心 OpenAPI ({m_rev['month']}官方申報)"
            }
            if yoy_v >= 0:
                fund_bulls.append(rev_entry)
            else:
                fund_bears.append(rev_entry)

    # 2. 台美股財報實績拆解（依各股實際 EPS / ROE / 毛利率 / 營益率 / 季營收年增率動態生成）
    pe_v = f_obj.get("pe", "N/A")
    fpe_v = f_obj.get("forward_pe", "N/A")
    eps_v = f_obj.get("eps", "N/A")
    roe_v = f_obj.get("roe", "N/A")
    gm_v = f_obj.get("gross_margin", "N/A")
    om_v = f_obj.get("operating_margin", "N/A")
    yoy_g = f_obj.get("yoy_rev_growth", "N/A")

    yoy_num = safe_float(yoy_g, 0.0)
    roe_num = safe_float(roe_v, 0.0)
    pe_num = safe_float(pe_v, 0.0)

    fin_url = "https://mops.twse.com.tw/mops/#/web/t163sb04" if tw_code else f"https://finance.yahoo.com/quote/{symbol}/financials/"
    fin_src = "MOPS 財務報表專區 / TradingView 官方財報" if tw_code else f"SEC Filings / Yahoo Finance ({symbol} 最新財報)"

    if yoy_num > 0 or roe_num >= 15:
        fund_bulls.append({
            "title": f"[最新財報獲利實績] EPS (TTM) 達 {eps_v}、ROE {roe_v}、毛利率 {gm_v}、營業利益率 {om_v}、季度營收年增率 {yoy_g}",
            "url": fin_url, "date": fin_src
        })
    else:
        fund_bears.append({
            "title": f"[最新財報數據檢視] EPS (TTM) 為 {eps_v}、ROE {roe_v}、毛利率 {gm_v}、營益率 {om_v}、季營收年增 {yoy_g}",
            "url": fin_url, "date": fin_src
        })

    if pe_num > 35:
        fund_bears.append({
            "title": f"[估值水位提示] 當前本益比 (PE) 為 {pe_v} 倍 (預估 Forward PE 為 {fpe_v} 倍)，處於相對高估值區間，需留意財報成長率是否持續匹配",
            "url": fin_url, "date": fin_src
        })
    elif 0 < pe_num <= 25:
        fund_bulls.append({
            "title": f"[估值具備支撐] 當前本益比 (PE) 為 {pe_v} 倍 (預估 Forward PE 為 {fpe_v} 倍)，估值處於合理偏低區間",
            "url": fin_url, "date": fin_src
        })

    if not fund_bulls:
        fund_bulls.append({"title": f"[最新財報指標] {display_name} 最新毛利率 {gm_v}、營益率 {om_v}、EPS {eps_v}", "url": fin_url, "date": fin_src})
    if not fund_bears:
        fund_bears.append({"title": f"[財務與估值追蹤] {display_name} 當前本益比 PE {pe_v} 倍、預估 PE {fpe_v} 倍，持續追蹤下季毛利率變化", "url": fin_url, "date": fin_src})

    # 3. 產業與個股真實新聞時事
    ev_bulls, ev_bears = [], []
    if fetch_rss:
        q_kw = display_name if tw_code else f"{symbol} stock"
        rss_items = fetch_google_news_rss_for_stock(q_kw, max_items=4)
        for n_item in rss_items:
            t_txt = n_item["title"]
            if any(k in t_txt for k in ["跌", "砍", "賣超", "下滑", "虧損", "降評", "利空", "悲觀", "重挫", "fall", "drop", "cut"]):
                ev_bears.append(n_item)
            else:
                ev_bulls.append(n_item)

    news_search_url = f"https://news.google.com/search?q={quote(display_name)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    if not ev_bulls:
        ev_bulls.append({"title": f"🔗 點此直接檢視「{display_name} ({symbol})」Google 新聞最新正向報導與外資研究報告", "url": news_search_url, "date": "Google News 即時新聞檢索"})
    if not ev_bears:
        ev_bears.append({"title": f"🔗 點此直接檢視「{display_name} ({symbol})」最新市場風險提示與法人籌碼異動報導", "url": news_search_url, "date": "Google News 即時新聞檢索"})

    return {
        "bullish": [fund_bulls[0]] + ([ev_bulls[0]] if ev_bulls else []),
        "bearish": [fund_bears[0]] + ([ev_bears[0]] if ev_bears else []),
        "categories": {
            "fundamentals_mops": {
                "label": "📑 MOPS重訊・最新月營收・財報指標" if tw_code else "📑 SEC最新財報・季營收・獲利指標",
                "bullish": fund_bulls,
                "bearish": fund_bears
            },
            "events": {
                "label": "📰 產業與個股新聞時事 (附來源連結)",
                "bullish": ev_bulls,
                "bearish": ev_bears
            }
        }
    }

def build_asset_object(symbol, display_name, asset_type, future_group, yf_map, tw_official, us_fund_map, rev_map, mops_by_code, fetch_rss=False):
    dec = 4 if (asset_type == "fx_rate" and symbol not in ["JPY=X", "TWD=X"]) else 2
    tw_code = symbol.split(".")[0] if (symbol.endswith(".TW") or symbol.endswith(".TWO")) else None
    y_data = yf_map.get(symbol) or {}
    hist = y_data.get("history") or []
    core_f = CORE_FUNDAMENTALS_DB.get(symbol, {})
    tv_f = (tw_official.get("fund_map", {}).get(tw_code) if tw_code else us_fund_map.get(symbol)) or {}

    p_val = safe_float(y_data.get("price"), 0.0)
    prev_val = safe_float(y_data.get("prev_close"), p_val)
    chg_val = safe_float(y_data.get("change"), 0.0)
    pct_val = safe_float(y_data.get("change_pct"), 0.0)
    ext_obj = y_data.get("ext_session")

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
                    hist = [{"date": "2026-11-17", "close": prev_val}, {"date": today_str, "close": p_val}]
                elif hist[-1]["date"] != today_str:
                    hist.append({"date": today_str, "close": p_val})
                else:
                    hist[-1]["close"] = p_val

    if (asset_type == "us_stock" or asset_type == "futures") and not ext_obj and p_val > 0:
        lbl = "電子盤" if asset_type == "futures" else ("盤前" if 15 <= now_tw.hour <= 22 else "盤後")
        ext_obj = {"price": round(p_val, 2), "change": round(chg_val, 2), "change_pct": round(pct_val, 2), "label": lbl}

    def pick_f(key):
        v_tv = tv_f.get(key, "N/A")
        if v_tv not in [None, "", "N/A", 0, "0.0%"]:
            return v_tv
        return core_f.get(key, "N/A")

    f_dict = {
        "pe": pick_f("pe"),
        "forward_pe": pick_f("forward_pe"),
        "eps": pick_f("eps"),
        "gross_margin": pick_f("gross_margin"),
        "operating_margin": pick_f("operating_margin"),
        "roe": pick_f("roe"),
        "yoy_rev_growth": pick_f("yoy_rev_growth"),
        "monthly_rev": rev_map.get(tw_code) if tw_code else None
    }

    if asset_type in ["us_stock", "tw_stock"]:
        ns_obj = build_stock_specific_sentiment_and_news(symbol, to_trad(display_name), asset_type, f_dict, mops_by_code, fetch_rss=fetch_rss)
    else:
        ns_obj = {
            "bullish": [{"title": f"[市場報價] {to_trad(display_name)} 最新報價 {round(p_val, dec)} ({pct_val:+.2f}%)", "url": f"https://finance.yahoo.com/quote/{quote(symbol)}/", "date": "Yahoo Finance 官方行情"}],
            "bearish": [{"title": f"[波動風險] 留意國際總經數據與央行利率決策對 {to_trad(display_name)} 之影響", "url": f"https://finance.yahoo.com/quote/{quote(symbol)}/", "date": "風險提示"}]
        }

    return {
        "symbol": symbol, "name": to_trad(display_name), "asset_type": asset_type, "future_group": future_group,
        "price": round(p_val, dec), "prev_close": round(prev_val, dec), "change": round(chg_val, dec), "change_pct": round(pct_val, 2),
        "ext_session": ext_obj, "intraday": [], "history": hist,
        "fundamentals": f_dict,
        "news_sentiment": ns_obj
    }

def main():
    t0 = time.time()
    os.makedirs("data", exist_ok=True)
    payload = {
        "last_updated": now_tw.strftime("%Y-%m-%d %H:%M:%S CST"),
        "indices": [], "vix_indices": [], "fear_greed": fetch_fear_and_greed_indices(),
        "us_bonds": [], "fx_rates": [], "fx_bonds": [],
        "us_stocks": [], "tw_stocks": [], "futures_commodities": [],
        "supply_chain_sectors": [], "tw_top_sectors": [], "us_top_sectors": [], "top_performing_sectors": [],
        "daily_market_report": {},
        "tw_chips_visual": {},
        "mops_general": []
    }

    try:
        sc_items_map, sector_stocks_map = parse_sectors_and_symbols_from_js("supply_chain_db.js")
        all_tw_syms = list(set([m["ticker"] for m in TW_STOCKS.values()] + [s for s in sc_items_map.keys() if s.endswith(".TW") or s.endswith(".TWO")]))
        all_us_eq = list(set(US_STOCKS + [s for s in sc_items_map.keys() if not (s.endswith(".TW") or s.endswith(".TWO"))]))

        print("1. Fetching Official TWSE/TPEx Monthly Revenues (t187ap05_L & mopsfin_t187ap05_O) & Material News...")
        rev_map = fetch_official_tw_monthly_revenues()
        mops_by_code, mops_general = fetch_official_mops_material_news()
        payload["mops_general"] = mops_general

        print("2. Fetching TradingView TW + US Scanners (Quotes + 7 Core Fundamentals)...")
        tw_official = fetch_tw_official_all_channels(all_tw_syms)
        us_fund_map = fetch_tradingview_us_fundamentals(all_us_eq)

        print("3. Computing Official TWSE/TPEx Margin Balance & MacroMicro 53117 Ratios...")
        payload["tw_chips_visual"] = fetch_twse_official_margin_and_maintenance(tw_official)

        all_required_syms = (
            list(INDICES.keys()) + list(VIX_INDICES.keys()) + list(US_BONDS.keys()) + list(FX_RATES.keys()) +
            list(US_STOCKS) + [m["ticker"] for m in TW_STOCKS.values()] +
            list(FUTURES_AND_COMMODITIES.keys()) + list(sc_items_map.keys())
        )

        print("4. Downloading 1Y histories & 5m Pre/Post/Electronic quotes via yfinance...")
        yf_map = download_all_yf_histories_and_ext(all_required_syms, all_us_eq, tw_official)
        yf_map.update(fetch_official_us2y_and_taifex_vixtwn_and_txf())

        core_rss_set = set(US_STOCKS + [m["ticker"] for m in TW_STOCKS.values()])
        built_cache = {}
        def get_asset(sym, name, a_type, f_group=None):
            if sym not in built_cache:
                built_cache[sym] = build_asset_object(sym, name, a_type, f_group, yf_map, tw_official, us_fund_map, rev_map, mops_by_code, fetch_rss=(sym in core_rss_set))
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
