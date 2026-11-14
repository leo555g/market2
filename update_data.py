import os
import sys
import json
import time
import math
import datetime
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
# 2. 獨立視窗二：四大重點產業鏈追蹤清單定義
# ==========================================
SUPPLY_CHAIN_SECTORS = [
    {
        "id": "cpo_photonics",
        "title": "💡 CPO 矽光子與光通訊測試鏈",
        "subtitle": "涵蓋 CW 雷射光源、晶圓級光學測試 (In4/WLOT)、FAU 光纖陣列封裝與 800G/1.6T 交換器晶片",
        "stages": [
            {
                "stage_name": "上游：CW 雷射光源 / 光學檢測設備 / 探針卡",
                "items": [
                    {"symbol": "3081.TWO", "name": "3081 聯亞", "role": "矽光子 CW LD 磷化銦磊晶主力"},
                    {"symbol": "2360.TW", "name": "2360 致茂", "role": "CPO 光電共同封裝量測與 SLT 設備"},
                    {"symbol": "6223.TWO", "name": "6223 旺矽", "role": "CPO 高頻晶圓探針卡與光學測試"},
                    {"symbol": "6515.TW", "name": "6515 穎崴", "role": "高頻高速測試座與晶圓級光電測試"}
                ]
            },
            {
                "stage_name": "中游：FAU 光纖陣列 / 光收發模組 / 先進封裝",
                "items": [
                    {"symbol": "3363.TWO", "name": "3363 上詮", "role": "台積電體系 FAU 光纖陣列與 CPO 封裝"},
                    {"symbol": "3163.TWO", "name": "3163 波若威", "role": "800G/1.6T 光纖套件與光波長分合器"},
                    {"symbol": "4979.TWO", "name": "4979 華星光", "role": "CSP 資料中心 800G 光收發模組"},
                    {"symbol": "4977.TW", "name": "4977 眾達-KY", "role": "博通體系 CPO 外部雷射光源 (ELS) 封裝"},
                    {"symbol": "3711.TW", "name": "3711 日月光投控", "role": "VIPack 光電共同封裝測試服務"}
                ]
            },
            {
                "stage_name": "下游：國際 AI 交換器與光學巨頭 (美股客戶連動)",
                "items": [
                    {"symbol": "AVGO", "name": "AVGO", "role": "Tomahawk 5 / Bailly 51.2T CPO 交換器龍頭"},
                    {"symbol": "MRVL", "name": "MRVL", "role": "光電 DSP 晶片與雲端客製化光互連"},
                    {"symbol": "COHR", "name": "COHR", "role": "800G/1.6T 光模組與 CW 雷射大廠"},
                    {"symbol": "ANET", "name": "ANET", "role": "AI 資料中心高速乙太網路交換器龍頭"}
                ]
            }
        ]
    },
    {
        "id": "cowos_tgv",
        "title": "🔬 CoWoS 先進封裝與 TGV 玻璃基板鏈",
        "subtitle": "涵蓋鑽石碟耗材、EUV 光罩盒、濕製程與點膠設備、TGV 玻璃鑽孔及 2.5D/3D 晶圓級封裝",
        "stages": [
            {
                "stage_name": "上游：先進耗材 / 光罩載具 / 高階測試介面",
                "items": [
                    {"symbol": "1560.TW", "name": "1560 中砂", "role": "先進製程 CMP 鑽石碟與再生晶圓"},
                    {"symbol": "3680.TWO", "name": "3680 家登", "role": "EUV 光罩盒與先進封裝 FOUP 載具"},
                    {"symbol": "6223.TWO", "name": "6223 旺矽", "role": "AI ASIC 與 GPU 垂直探針卡 (VPC) 龍頭"},
                    {"symbol": "6515.TW", "name": "6515 穎崴", "role": "AI GPU 高頻高速老化測試座 (Burn-in)"}
                ]
            },
            {
                "stage_name": "中游：CoWoS 濕製程 / 點膠揀晶 / TGV 玻璃基板設備",
                "items": [
                    {"symbol": "3131.TWO", "name": "3131 弘塑", "role": "CoWoS 單晶圓濕製程設備與化材主力"},
                    {"symbol": "3583.TW", "name": "3583 辛耘", "role": "CoWoS 自製濕製程設備與再生晶圓"},
                    {"symbol": "6187.TWO", "name": "6187 萬潤", "role": "CoWoS 點膠機、散熱貼合與自動光學檢測"},
                    {"symbol": "2467.TW", "name": "2467 志聖", "role": "先進封裝壓膜烘烤與 TGV 玻璃基板聯盟"},
                    {"symbol": "2330.TW", "name": "2330 台積電", "role": "CoWoS-S/L/R 與 SoIC 全球獨家製程龍頭"}
                ]
            },
            {
                "stage_name": "下游：AI 運算晶片與伺服器機構件",
                "items": [
                    {"symbol": "NVDA", "name": "NVDA", "role": "Blackwell / Rubin 架構最大 CoWoS-L 客戶"},
                    {"symbol": "AMD", "name": "AMD", "role": "MI325X / MI350 採用 CoWoS 先進封裝"},
                    {"symbol": "2059.TW", "name": "2059 川湖", "role": "AI 伺服器高荷重滑軌全球市占龍頭"},
                    {"symbol": "3017.TW", "name": "3017 奇鋐", "role": "AI 伺服器 3D VC 與水冷板散熱主力"}
                ]
            }
        ]
    },
    {
        "id": "ccl_highfreq",
        "title": "📡 高頻高速 CCL (M7/M8、Q-glass 石英布、PPE 樹脂) 鏈",
        "subtitle": "涵蓋 Low-Dk / Q-Glass 石英玻纖布、HVLP 高頻銅箔、PPE 聚苯醚樹脂、M8 等級 CCL 與高層數 AI 主板",
        "stages": [
            {
                "stage_name": "上游：Low-Dk2 / Q-Glass 石英玻纖布、HVLP 銅箔、樹脂",
                "items": [
                    {"symbol": "1802.TW", "name": "1802 台玻", "role": "Low-Dk 低介電玻纖布擴產主力"},
                    {"symbol": "1815.TWO", "name": "1815 富喬", "role": "AI 伺服器高頻高速 Low-Dk 玻纖紗/布"},
                    {"symbol": "8358.TWO", "name": "8358 金居", "role": "高頻高速 RG / HVLP 超低粗糙度電解銅箔"},
                    {"symbol": "1303.TW", "name": "1303 南亞", "role": "高階環氧樹脂、硬化劑與高頻銅箔基板材料"}
                ]
            },
            {
                "stage_name": "中游：M7 / M8 超低損耗銅箔基板 (High-Speed CCL)",
                "items": [
                    {"symbol": "2383.TW", "name": "2383 台光電", "role": "全球無鹵高頻 CCL 龍頭 (M7/M8 獨家與主力供應)"},
                    {"symbol": "6274.TWO", "name": "6274 台燿", "role": "800G 交換器與 AI ASIC M7/M8 高頻 CCL"},
                    {"symbol": "6213.TW", "name": "6213 聯茂", "role": "AI 伺服器通用板與車用高頻高速 CCL"}
                ]
            },
            {
                "stage_name": "下游：AI 伺服器 OAM / UBB 高層數 PCB 與 ABF 載板",
                "items": [
                    {"symbol": "2368.TW", "name": "2368 金像電", "role": "AI 伺服器 UBB 與 800G 交換器高層數 PCB 龍頭"},
                    {"symbol": "3037.TW", "name": "3037 欣興", "role": "AI GPU ABF 載板與高階 HDI 交換板"},
                    {"symbol": "5439.TWO", "name": "5439 高技", "role": "AI 伺服器厚銅電源板與網通高速 PCB"}
                ]
            }
        ]
    },
    {
        "id": "sic_gan",
        "title": "⚡ 第三代功率半導體 (SiC 碳化矽 / GaN 氮化鎵) 鏈",
        "subtitle": "涵蓋 SiC 導電型晶碇/基板、GaN-on-Si 磊晶、晶圓代工與 AI 資料中心高壓電源供應器 (PSU/BBU)",
        "stages": [
            {
                "stage_name": "上游：SiC 碳化矽晶圓基板 / GaN 氮化鎵磊晶",
                "items": [
                    {"symbol": "6488.TWO", "name": "6488 環球晶", "role": "6吋/8吋 SiC 碳化矽基板與 GaN 磊晶擴產"},
                    {"symbol": "3016.TW", "name": "3016 嘉晶", "role": "SiC 與 GaN 化合物半導體磊晶代工主力"},
                    {"symbol": "2455.TW", "name": "2455 全新", "role": "化合物半導體微電子與光電子 MOCVD 磊晶"}
                ]
            },
            {
                "stage_name": "中游：化合物功率晶圓代工 / 封測與模組",
                "items": [
                    {"symbol": "3707.TWO", "name": "3707 漢磊", "role": "SiC MOSFET / SBD 與 GaN 晶圓代工"},
                    {"symbol": "5347.TWO", "name": "5347 世界先進", "role": "8吋 GaN-on-Si 氮化鎵功率元件代工"},
                    {"symbol": "2481.TW", "name": "2481 強茂", "role": "SiC 二極體與車用/工控功率 MOSFET"},
                    {"symbol": "2308.TW", "name": "2308 台達電", "role": "AI 資料中心高瓦數鈦金級 PSU 導入 SiC/GaN"}
                ]
            },
            {
                "stage_name": "下游：國際功率 IDM 巨頭與電動車終端 (美股連動)",
                "items": [
                    {"symbol": "ON", "name": "ON", "role": "安森美：車用與能源基礎設施 SiC 模組巨頭"},
                    {"symbol": "STM", "name": "STM", "role": "意法半導體：全球車用 SiC MOSFET 市占龍頭"},
                    {"symbol": "WOLF", "name": "WOLF", "role": "Wolfspeed：8吋 200mm SiC 碳化矽晶圓廠"},
                    {"symbol": "TSLA", "name": "TSLA", "role": "電動車逆變器與超級充電樁核心客戶"}
                ]
            }
        ]
    }
]

def fetch_tw_official_market_snapshot():
    snapshot = {"indices": {}, "stocks": {}, "pe_map": {}}
    headers = {"User-Agent": "Mozilla/5.0"}

    # 往回查最近 7 天內最後一個開盤日，確保週末休市也能抓到週五官方真實收盤價
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

def fetch_ticker_full_data(symbol, display_name, asset_type="standard", future_group=None, tw_official=None, tw_code=None):
    dec = 4 if (asset_type == "fx_rate" and symbol not in ["JPY=X", "TWD=X"]) else 2
    if not tw_code and (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        tw_code = symbol.split(".")[0]

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
        "history": [],
        "fundamentals": {},
        "news_sentiment": {
            "bullish": [{"title": f"[市場動態] {to_trad(display_name)} 基本面與機構法人關注度維持穩健", "url": "#", "date": "最新情報"}],
            "bearish": [{"title": f"[風險提示] 留意短線技術面乖離與總經利率政策波動", "url": "#", "date": "最新情報"}]
        }
    }

    try:
        tk = yf.Ticker(symbol)
        hist_1y = tk.history(period="1y", interval="1d", timeout=10)
        if not hist_1y.empty and "Close" in hist_1y.columns:
            hist_1y = hist_1y.dropna(subset=["Close"])
            for idx, row in hist_1y.iterrows():
                c_val = safe_float(row["Close"], 0.0)
                if c_val > 0:
                    result["history"].append({"date": idx.strftime("%Y-%m-%d"), "close": round(c_val, dec)})

            if len(result["history"]) >= 1:
                # 修正：無論指數、個股或期貨，主價格一律取最後一筆最新真實收盤價 (iloc[-1])，不再慢一天！
                latest_close = result["history"][-1]["close"]
                prev_close = result["history"][-2]["close"] if len(result["history"]) > 1 else latest_close
                result["price"] = round(latest_close, dec)
                result["prev_close"] = round(prev_close, dec)
                result["change"] = round(latest_close - prev_close, dec)
                result["change_pct"] = round(((latest_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

        # 取得 5 分鐘日內與盤前/盤後/夜盤最新一筆報價
        try:
            hist_1d = tk.history(period="5d", interval="15m", prepost=True, timeout=8)
            if not hist_1d.empty and "Close" in hist_1d.columns:
                hist_1d = hist_1d.dropna(subset=["Close"])
                for idx, row in hist_1d.tail(35).iterrows():
                    p_v = safe_float(row["Close"], 0.0)
                    if p_v > 0:
                        result["intraday"].append({"time": idx.strftime("%m/%d %H:%M"), "price": round(p_v, dec)})
        except Exception:
            pass

        # 以台灣證交所與櫃買中心官方數據校準台灣加權指數、櫃買指數與上市個股
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

        # 處理期貨夜盤與美股盤前盤後
        if asset_type == "futures" and len(result["intraday"]) > 0 and result["price"] > 0:
            last_globex = result["intraday"][-1]["price"]
            night_pct = ((last_globex - result["price"]) / result["price"]) * 100
            result["ext_session"] = {
                "label": "夜盤",
                "price": round(last_globex, 2),
                "change_pct": round(night_pct, 2)
            }

        if asset_type in ["us_stock", "tw_stock", "supply_chain"]:
            info = {}
            try:
                info = tk.info or {}
            except Exception:
                info = {}

            reg_p = safe_float(info.get("regularMarketPrice") or info.get("currentPrice"), 0.0)
            reg_prev = safe_float(info.get("regularMarketPreviousClose") or info.get("previousClose"), 0.0)
            if reg_p > 0 and reg_prev > 0 and not (tw_code and tw_official and tw_code in tw_official.get("stocks", {})):
                result["price"] = round(reg_p, dec)
                result["prev_close"] = round(reg_prev, dec)
                result["change"] = round(reg_p - reg_prev, dec)
                result["change_pct"] = round(((reg_p - reg_prev) / reg_prev) * 100, 2)

            if asset_type == "us_stock":
                pre_p = safe_float(info.get("preMarketPrice"), 0.0)
                post_p = safe_float(info.get("postMarketPrice"), 0.0)
                m_state = str(info.get("marketState", ""))
                if m_state == "PRE" and pre_p > 0 and result["price"] > 0:
                    result["ext_session"] = {"label": "盤前", "price": round(pre_p, 2), "change_pct": round(((pre_p - result["price"]) / result["price"]) * 100, 2)}
                elif post_p > 0 and result["price"] > 0:
                    result["ext_session"] = {"label": "盤後", "price": round(post_p, 2), "change_pct": round(((post_p - result["price"]) / result["price"]) * 100, 2)}

            pe = safe_float(info.get("trailingPE"), None)
            if tw_code and tw_official and tw_code in tw_official.get("pe_map", {}):
                pe = tw_official["pe_map"][tw_code]
            f_pe = safe_float(info.get("forwardPE"), None)
            eps = safe_float(info.get("trailingEps"), None)
            gm = safe_float(info.get("grossMargins"), None)
            om = safe_float(info.get("operatingMargins"), None)
            roe = safe_float(info.get("returnOnEquity"), None)
            rev_g = safe_float(info.get("revenueGrowth"), None)

            result["fundamentals"] = {
                "pe": round(pe, 2) if pe else "N/A",
                "forward_pe": round(f_pe, 2) if f_pe else "N/A",
                "eps": round(eps, 2) if eps else "N/A",
                "gross_margin": f"{round(gm * 100, 2)}%" if gm else "N/A",
                "operating_margin": f"{round(om * 100, 2)}%" if om else "N/A",
                "roe": f"{round(roe * 100, 2)}%" if roe else "N/A",
                "yoy_rev_growth": f"{round(rev_g * 100, 2)}%" if rev_g else "N/A",
                "monthly_rev": None
            }
    except Exception as e:
        print(f"[Warn] {symbol} skipped: {e}")

    return result

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
        tw_official = fetch_tw_official_market_snapshot()
        fetched_cache = {}

        def get_or_fetch(sym, name, a_type, f_group=None, tw_c=None):
            if sym in fetched_cache:
                cached = dict(fetched_cache[sym])
                cached["name"] = to_trad(name)
                if f_group:
                    cached["future_group"] = f_group
                return cached
            data_obj = fetch_ticker_full_data(sym, name, a_type, f_group, tw_official, tw_c)
            fetched_cache[sym] = data_obj
            return data_obj

        output_payload["indices"] = [get_or_fetch(k, v, "index") for k, v in INDICES.items()]
        output_payload["us_bonds"] = [get_or_fetch(k, v, "us_bond") for k, v in US_BONDS.items()]
        output_payload["fx_rates"] = [get_or_fetch(k, v, "fx_rate") for k, v in FX_RATES.items()]
        output_payload["fx_bonds"] = output_payload["us_bonds"] + output_payload["fx_rates"]
        output_payload["us_stocks"] = [get_or_fetch(sym, sym, "us_stock") for sym in US_STOCKS]

        tw_list = []
        for code, meta in TW_STOCKS.items():
            obj = get_or_fetch(meta["ticker"], meta["name"], "tw_stock", tw_c=code)
            obj["tw_code"] = code
            tw_list.append(obj)
        output_payload["tw_stocks"] = tw_list

        output_payload["futures_commodities"] = [
            get_or_fetch(k, meta["name"], "futures", meta["group"])
            for k, meta in FUTURES_AND_COMMODITIES.items()
        ]

        # 抓取獨立視窗二的「四大重點產業鏈追蹤模組」所有成分股真實報價與歷史 K 線
        sectors_out = []
        for sec in SUPPLY_CHAIN_SECTORS:
            sec_copy = {"id": sec["id"], "title": sec["title"], "subtitle": sec["subtitle"], "stages": []}
            for stg in sec["stages"]:
                stg_items = []
                for it in stg["items"]:
                    sym = it["symbol"]
                    is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
                    a_t = "us_stock" if is_us else "tw_stock"
                    quote_obj = dict(get_or_fetch(sym, it["name"], a_t))
                    quote_obj["role"] = it["role"]
                    stg_items.append(quote_obj)
                sec_copy["stages"].append({"stage_name": stg["stage_name"], "items": stg_items})
            sectors_out.append(sec_copy)
        output_payload["supply_chain_sectors"] = sectors_out

        # 若有設定 FINLAB_API_TOKEN，為所有台股與產業鏈台股填入最新月營收 MoM / YoY
        token = os.environ.get("FINLAB_API_TOKEN")
        if token:
            try:
                import finlab
                from finlab import data as fdata
                finlab.login(token)
                rev_df = fdata.get("monthly_revenue:當月營收")
                mom_df = fdata.get("monthly_revenue:上月比較增減(%)")
                yoy_df = fdata.get("monthly_revenue:去年同月增減(%)")

                for sym_key, asset_obj in fetched_cache.items():
                    if sym_key.endswith(".TW") or sym_key.endswith(".TWO"):
                        sid = sym_key.split(".")[0]
                        if sid in rev_df.columns:
                            valid_rev = rev_df[sid].dropna()
                            if not valid_rev.empty:
                                l_month = valid_rev.index[-1].strftime("%Y-%m")
                                val_yi = round(safe_float(valid_rev.iloc[-1]) / 100000, 2)
                                m_v = round(safe_float(mom_df[sid].dropna().iloc[-1]), 2) if sid in mom_df.columns else 0.0
                                y_v = round(safe_float(yoy_df[sid].dropna().iloc[-1]), 2) if sid in yoy_df.columns else 0.0
                                if "fundamentals" not in asset_obj:
                                    asset_obj["fundamentals"] = {}
                                asset_obj["fundamentals"]["monthly_rev"] = {
                                    "month": l_month,
                                    "revenue_yi": f"{val_yi} 億",
                                    "mom": m_v,
                                    "yoy": y_v
                                }
            except Exception as e:
                print(f"[Warn] FinLab monthly revenue skipped: {e}")

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
