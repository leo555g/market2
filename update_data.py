import os
import json
import time
import datetime
import urllib.parse
import xml.etree.ElementTree as ET
import pytz
import requests
import urllib3
import pandas as pd
import numpy as np
import yfinance as yf
from opencc import OpenCC

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 使用基礎簡轉繁，並加上台灣金融專有名詞強制校正
cc = OpenCC('s2tw')

def to_trad(text):
    if text is None:
        return ""
    s = cc.convert(str(text))
    replacements = {
        "那斯達剋": "納斯達克",
        "納斯達剋": "納斯達克",
        "那斯達克": "納斯達克",
        "斯達剋": "斯達克",
        "達剋": "達克",
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
    s = s.replace("臺", "台")
    return s

def safe_float(val, default=0.0):
    try:
        if val is None or pd.isna(val):
            return default
        clean_str = str(val).replace(",", "").replace("%", "").replace("--", "").strip()
        if clean_str == "" or clean_str == "N/A":
            return default
        f = float(clean_str)
        return default if np.isnan(f) else f
    except Exception:
        return default

tw_tz = pytz.timezone('Asia/Taipei')
now_tw = datetime.datetime.now(tw_tz)

INDICES = {
    "^GSPC": "S&P 500 指數",
    "^DJI": "道瓊工業指數",
    "^IXIC": "納斯達克指數",
    "^SOX": "費城半導體指數",
    "^TWII": "台灣加權指數",
    "^N225": "日經 225 指數",
    "^KS11": "韓國 KOSPI 指數",
    "^FTSE": "英國富時 100",
    "^GDAXI": "德國 DAX 指數",
    "^FCHI": "法國 CAC 40"
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
    "ES=F": "小S&P期貨",
    "NQ=F": "小納斯達克期貨",
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

INDEX_COUNTRY_PROFILES = {
    "^GSPC": {
        "cb_name": "美國聯準會 (Fed)",
        "cb_query": "聯準會 OR FOMC OR 聯邦資金利率 OR 鮑爾 -爆料同學會",
        "macro_query": "美國 CPI OR 非農就業 OR 美國GDP OR 美國PMI OR 核心PCE -爆料同學會",
        "events_query": "標普500 OR 美股財報 OR 華爾街 美股盤勢 -爆料同學會",
        "cb_baseline_bull": "[美國聯準會 (Fed)] FOMC 維持政策利率觀察期，保留政策彈性並關注實質經濟擴張動能",
        "cb_baseline_bear": "[美國聯準會 (Fed)] 部分 FOMC 委員仍擔憂通膨黏著度，若物價反彈則高利率環境將維持更久",
        "macro_baseline_bull": "[美國總經] 美國就業市場維持韌性、企業資本支出與 AI 生產力投資強勁支撐 GDP 表現",
        "macro_baseline_bear": "[美國總經] 核心通膨與長天期美債殖利率居高，對高估值股票形成折現率壓力"
    },
    "^DJI": {
        "cb_name": "美國聯準會 (Fed)",
        "cb_query": "聯準會 OR FOMC OR 美國利率決策 -爆料同學會",
        "macro_query": "美國 製造業PMI OR 非農就業 OR 美國零售銷售 OR 美國CPI -爆料同學會",
        "events_query": "道瓊指數 OR 美股藍籌股 OR 傳統產業 金融股 美股 -爆料同學會",
        "cb_baseline_bull": "[美國聯準會 (Fed)] 聯準會穩定利率步伐，大型金融與價值型藍籌股受惠穩定利差環境",
        "cb_baseline_bear": "[美國聯準會 (Fed)] 資金成本維持相對高檔，企業融資與商用不動產壓力仍在",
        "macro_baseline_bull": "[美國總經] 美國內需消費與服務業韌性支撐大型藍籌企業營收",
        "macro_baseline_bear": "[美國總經] 製造業庫存調整與薪資成本可能壓抑傳統工業毛利率"
    },
    "^IXIC": {
        "cb_name": "美國聯準會 (Fed)",
        "cb_query": "聯準會 利率 OR 美債殖利率 科技股 OR FOMC -爆料同學會",
        "macro_query": "美國 核心CPI OR 美國科技業支出 OR 美國GDP -爆料同學會",
        "events_query": "納斯達克 OR 那斯達克 OR 大型科技股 OR 雲端AI 資本支出 -爆料同學會",
        "cb_baseline_bull": "[美國聯準會 (Fed)] 聯準會政策路徑透明，減緩長天期公債殖利率急升對科技股估值之衝擊",
        "cb_baseline_bear": "[美國聯準會 (Fed)] 高折現率環境對高本益比成長股較為敏感，市場密切關注 FOMC 官員談話",
        "macro_baseline_bull": "[美國總經] 美國企業軟體與 AI 基礎設施投資持續擴張，帶動科技部門生產力與獲利提升",
        "macro_baseline_bear": "[美國總經] 若核心服務業通膨降溫不如預期，市場對寬鬆預期推遲將引發科技股評價修正"
    },
    "^SOX": {
        "cb_name": "美國聯準會 (Fed)",
        "cb_query": "聯準會 利率 OR 美國晶片法案 政策 -爆料同學會",
        "macro_query": "全球半導體銷售額 OR 美國PMI OR 伺服器資本支出 -爆料同學會",
        "events_query": "費城半導體 OR AI晶片 OR CoWoS 台積電 輝達 博通 -爆料同學會",
        "cb_baseline_bull": "[美國聯準會 (Fed)] 貨幣政策趨於可預測，有利全球雲端巨頭維持長線資料中心資本支出規劃",
        "cb_baseline_bear": "[美國聯準會 (Fed)] 資金成本居高，消費性電子與車用工控晶片庫存回補速度受限",
        "macro_baseline_bull": "[產業與總經] AI 資料中心建置需求強勁，先進製程、封裝與高頻寬記憶體供不應求",
        "macro_baseline_bear": "[產業與總經] 跨國出口管制規範與關稅政策不確定性，可能干擾全球半導體供應鏈節奏"
    },
    "^TWII": {
        "cb_name": "台灣央行 (CBC)",
        "cb_query": "台灣央行 理監事會 OR 重貼現率 OR 楊金龍 OR 選擇性信用管制 -爆料同學會",
        "macro_query": "台灣 景氣對策信號 OR 台灣外銷訂單 OR 台灣GDP 主計總處 OR 台灣CPI -爆料同學會",
        "events_query": "台股 加權指數 外資買賣超 OR 台積電 權值股 盤勢 -爆料同學會 -CMoney",
        "cb_baseline_bull": "[台灣央行 (CBC)] 央行理監事會維持重貼現率 2.00% 穩健基調，並上修台灣全年 GDP 成長率預測",
        "cb_baseline_bear": "[台灣央行 (CBC)] 央行持續透過存款準備率與選擇性信用管制調節房市資金，且台美利差牽動外資匯出入",
        "macro_baseline_bull": "[台灣總經] AI 與高效能運算帶動資通訊與半導體出口暢旺，台灣 CPI 通膨維持溫和可控",
        "macro_baseline_bear": "[台灣總經] 傳產與成熟製程復甦步伐不均，需留意外資於期現貨籌碼調節及新台幣匯率波動"
    },
    "^N225": {
        "cb_name": "日本央行 (BoJ)",
        "cb_query": "日本央行 OR 日銀 升息 OR 植田和男 OR 日圓政策 -爆料同學會",
        "macro_query": "日本 CPI 通膨 OR 日本GDP OR 春鬥薪資 OR 日本出口 -爆料同學會",
        "events_query": "日經指數 OR 日股 外資 OR 東京威力科創 日本商社 -爆料同學會",
        "cb_baseline_bull": "[日本央行 (BoJ)] 日銀採取漸進溫和步調調整政策，實質利率仍處低檔，維持企業寬鬆融資環境",
        "cb_baseline_bear": "[日本央行 (BoJ)] 日本央行邁向利率正常化，若日圓急升或日債殖利率跳升，可能引發日股套利平倉賣壓",
        "macro_baseline_bull": "[日本總經] 日本企業加薪幅度創高帶動內需良性通膨循環，東證公司治理改革持續吸引長線外資",
        "macro_baseline_bear": "[日本總經] 進口能源成本與匯率雙向波動，對日本出口導向型車廠與機械業獲利造成干擾"
    },
    "^KS11": {
        "cb_name": "韓國央行 (BoK)",
        "cb_query": "韓國央行 利率 OR 韓國銀行 貨幣政策 -爆料同學會",
        "macro_query": "韓國 出口數據 OR 韓國CPI OR 韓國GDP 半導體出口 -爆料同學會",
        "events_query": "韓股 KOSPI OR 三星電子 SK海力士 記憶體 -爆料同學會",
        "cb_baseline_bull": "[韓國央行 (BoK)] 韓國通膨逐步受控，韓國央行貨幣政策具備轉向支撐內需與企業投資之空間",
        "cb_baseline_bear": "[韓國央行 (BoK)] 韓國家庭債務占 GDP 比重偏高，限制韓國央行快速大幅寬鬆之空間",
        "macro_baseline_bull": "[韓國總經] HBM 高頻寬記憶體與半導體出口年增率強勁，支撐韓國貿易順差表現",
        "macro_baseline_bear": "[韓國總經] 傳統石化、鋼鐵與電池產業面臨全球產能競爭，壓抑整體韓股估值修復"
    },
    "^FTSE": {
        "cb_name": "英國央行 (BoE)",
        "cb_query": "英國央行 利率 OR 英格蘭銀行 降息 升息 -爆料同學會",
        "macro_query": "英國 CPI 通膨 OR 英國GDP OR 英國就業數據 -爆料同學會",
        "events_query": "英國股市 富時100 OR 倫敦股市 能源股 金融股 -爆料同學會",
        "cb_baseline_bull": "[英國央行 (BoE)] 英格蘭銀行貨幣政策趨穩，高股息金融與跨國大型防禦型企業具備估值優勢",
        "cb_baseline_bear": "[英國央行 (BoE)] 英國服務業通膨與薪資增速仍具黏性，使英國央行維持相對審慎的利率立場",
        "macro_baseline_bull": "[英國總經] 大宗商品與能源巨頭現金流穩健，帶動富時 100 指數防禦抗跌能力",
        "macro_baseline_bear": "[英國總經] 英國本土內需製造業成長動能偏弱，受制於高借貸成本與財政預算壓力"
    },
    "^GDAXI": {
        "cb_name": "歐洲央行 (ECB)",
        "cb_query": "歐洲央行 利率 OR 拉加德 ECB 升息 降息 -爆料同學會",
        "macro_query": "德國 製造業PMI OR 德國IFO景氣指數 OR 歐元區CPI 德國GDP -爆料同學會",
        "events_query": "德國股市 DAX OR 思愛普 SAP 西門子 德國汽車股 -爆料同學會",
        "cb_baseline_bull": "[歐洲央行 (ECB)] 歐洲央行貨幣政策透明，歐元匯率相對穩定有利德國跨國出口巨頭海外獲利換算",
        "cb_baseline_bear": "[歐洲央行 (ECB)] 歐洲央行對潛在服務業通膨保持警戒，企業中長期融資成本仍高於疫情前水準",
        "macro_baseline_bull": "[德國總經] 德國工業軟體、自動化與國防基礎建設投資提供 DAX 指數底部支撐",
        "macro_baseline_bear": "[德國總經] 德國製造業 PMI 與汽車工業面臨能源轉型成本及海外市場競爭雙重挑戰"
    },
    "^FCHI": {
        "cb_name": "歐洲央行 (ECB)",
        "cb_query": "歐洲央行 利率 OR ECB 貨幣政策 歐元區 -爆料同學會",
        "macro_query": "歐元區 CPI OR 法國GDP OR 法國服務業PMI -爆料同學會",
        "events_query": "法國股市 CAC40 OR LVMH 精品股 歐洲股市 -爆料同學會",
        "cb_baseline_bull": "[歐洲央行 (ECB)] 歐元區整體通膨較高峰期回落，金融體系流動性維持穩定",
        "cb_baseline_bear": "[歐洲央行 (ECB)] 歐洲政策利率維持相對高檔，且法國財政赤字議題推升主權債利差關注度",
        "macro_baseline_bull": "[法國總經] 法國航太、能源與全球高端消費品牌具備強大定價權與全球市占率",
        "macro_baseline_bear": "[法國總經] 全球奢侈品消費動能放緩與歐洲政經預算協商不確定性影響市場信心"
    }
}

BULL_KEYWORDS = [
    "創高", "新高", "成長", "大增", "暴增", "買超", "上調", "調升", "上修", "優於預期", "利多",
    "獲利", "突破", "強勁", "擴產", "滿載", "看旺", "加碼", "大漲", "飆漲", "反彈", "轉買",
    "降息", "鴿派", "軟著陸", "放緩", "回落", "寬鬆", "激勵", "支撐", "回流", "順差", "亮眼",
    "beat", "surge", "soar", "upgrade", "bull", "record", "growth", "strong", "outperform", "buy", "rally", "dovish"
]
BEAR_KEYWORDS = [
    "下跌", "重挫", "衰退", "減少", "賣超", "下調", "調降", "下修", "低於預期", "利空", "虧損",
    "跌破", "疲軟", "砍單", "修正", "看淡", "減碼", "大跌", "暴跌", "賣壓", "警告", "風險",
    "升息", "鷹派", "通膨升溫", "停滯", "倒掛", "拋售", "外流", "關稅", "制裁", "衝突", "緊縮",
    "miss", "drop", "plunge", "downgrade", "bear", "weak", "cut", "sell", "fall", "decline", "risk", "warn", "hawkish"
]

NOISE_DOMAINS = ["爆料同學會", "CMoney", "股市爆料", "Dcard", "PTT"]

def fetch_rss_bucket(query_str, tag_prefix, max_items=6):
    bulls = []
    bears = []
    seen = set()

    try:
        encoded_q = urllib.parse.quote(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(rss_url, headers=headers, timeout=8)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall("./channel/item"):
                raw_title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else "#"
                pub_date = item.find("pubDate").text[:16] if item.find("pubDate") is not None and item.find("pubDate").text else "最新情報"

                title = to_trad(raw_title).strip()
                if not title or title in seen:
                    continue
                if any(noise in title for noise in NOISE_DOMAINS):
                    continue
                seen.add(title)

                b_score = sum(1 for kw in BULL_KEYWORDS if kw.lower() in title.lower())
                s_score = sum(1 for kw in BEAR_KEYWORDS if kw.lower() in title.lower())

                obj = {
                    "title": f"[{to_trad(tag_prefix)}] {title}",
                    "url": link,
                    "date": pub_date
                }

                if s_score > b_score:
                    bears.append(obj)
                elif b_score > s_score:
                    bulls.append(obj)
                else:
                    if len(bulls) <= len(bears):
                        bulls.append(obj)
                    else:
                        bears.append(obj)

                if len(bulls) + len(bears) >= max_items * 2:
                    break
    except Exception as e:
        print(f"[Warn] RSS bucket error ({query_str}): {e}")

    return bulls[:max_items], bears[:max_items]


def build_categorized_sentiment(symbol, display_name, asset_type, fundamentals, change_pct):
    if symbol in INDEX_COUNTRY_PROFILES:
        prof = INDEX_COUNTRY_PROFILES[symbol]
        cb_name = to_trad(prof["cb_name"])

        cb_bulls, cb_bears = fetch_rss_bucket(prof["cb_query"], cb_name, max_items=4)
        cb_bulls.insert(0, {"title": to_trad(prof["cb_baseline_bull"]), "url": "#", "date": "央行政策核心"})
        cb_bears.insert(0, {"title": to_trad(prof["cb_baseline_bear"]), "url": "#", "date": "央行政策風險"})

        m_bulls, m_bears = fetch_rss_bucket(prof["macro_query"], "總經數據", max_items=4)
        m_bulls.insert(0, {"title": to_trad(prof["macro_baseline_bull"]), "url": "#", "date": "總經基本面"})
        m_bears.insert(0, {"title": to_trad(prof["macro_baseline_bear"]), "url": "#", "date": "總經逆風"})

        ev_bulls, ev_bears = fetch_rss_bucket(prof["events_query"], "新聞時事", max_items=5)
        if len(ev_bulls) == 0:
            ev_bulls.append({"title": f"[新聞時事] {to_trad(display_name)} 權值股與機構法人買盤動態維持穩健", "url": "#", "date": "市場時事"})
        if len(ev_bears) == 0:
            ev_bears.append({"title": f"[新聞時事] {to_trad(display_name)} 短線留意高檔獲利了結與國際連動波動", "url": "#", "date": "市場時事"})

        return {
            "mode": "index_three_pillars",
            "central_bank_name": cb_name,
            "categories": {
                "central_bank": {
                    "label": f"🏦 {cb_name}決策",
                    "bullish": cb_bulls[:5],
                    "bearish": cb_bears[:5]
                },
                "macro": {
                    "label": "📊 總經數據指標",
                    "bullish": m_bulls[:5],
                    "bearish": m_bears[:5]
                },
                "events": {
                    "label": "📰 新聞時事與盤勢",
                    "bullish": ev_bulls[:5],
                    "bearish": ev_bears[:5]
                }
            },
            "bullish": [cb_bulls[0], m_bulls[0], ev_bulls[0]],
            "bearish": [cb_bears[0], m_bears[0], ev_bears[0]]
        }

    elif asset_type in ["futures", "fx_bond"]:
        cb_name = "台灣央行 / 聯準會" if "TWD" in symbol else ("中國人行 / 聯準會" if "CNY" in symbol else ("日本央行 / 聯準會" if "JPY" in symbol else ("歐洲央行 / 聯準會" if "EUR" in symbol else ("英國央行 / 聯準會" if "GBP" in symbol else "美國聯準會 (Fed)"))))
        cb_bulls, cb_bears = fetch_rss_bucket(f"{display_name} 央行 OR 聯準會 OR 利率 -爆料同學會", cb_name, max_items=4)
        m_bulls, m_bears = fetch_rss_bucket(f"{display_name} 庫存 OR 供需 OR 通膨 OR 經濟數據 -爆料同學會", "總經與供需", max_items=4)
        ev_bulls, ev_bears = fetch_rss_bucket(f"{display_name} 價格 OR 市場時事 -爆料同學會", "新聞時事", max_items=4)

        if not cb_bulls:
            cb_bulls.append({"title": f"[{cb_name}] 央行流動性與利率環境對 {to_trad(display_name)} 提供支撐", "url": "#", "date": "政策評估"})
        if not cb_bears:
            cb_bears.append({"title": f"[{cb_name}] 若央行維持緊縮立場或美元走強，將壓抑 {to_trad(display_name)} 表現", "url": "#", "date": "政策風險"})
        if not m_bulls:
            m_bulls.append({"title": f"[總經與供需] 全球實體需求與備貨動能支撐 {to_trad(display_name)} 基本面", "url": "#", "date": "總經供需"})
        if not m_bears:
            m_bears.append({"title": f"[總經與供需] 留意全球製造業周期波動對 {to_trad(display_name)} 需求之影響", "url": "#", "date": "總經風險"})
        if not ev_bulls:
            ev_bulls.append({"title": f"[新聞時事] 國際資金避險與資產配置需求帶動交投熱度", "url": "#", "date": "市場動態"})
        if not ev_bears:
            ev_bears.append({"title": f"[新聞時事] 短線留意技術面乖離與部位結算帶來之震盪", "url": "#", "date": "市場動態"})

        return {
            "mode": "index_three_pillars",
            "central_bank_name": cb_name,
            "categories": {
                "central_bank": {"label": f"🏦 {cb_name}", "bullish": cb_bulls[:5], "bearish": cb_bears[:5]},
                "macro": {"label": "📊 總經與供需數據", "bullish": m_bulls[:5], "bearish": m_bears[:5]},
                "events": {"label": "📰 新聞時事動態", "bullish": ev_bulls[:5], "bearish": ev_bears[:5]}
            },
            "bullish": [cb_bulls[0], m_bulls[0], ev_bulls[0]],
            "bearish": [cb_bears[0], m_bears[0], ev_bears[0]]
        }

    else:
        q_str = f"{display_name} 營收 OR 法說會 OR 財報 OR 訂單 -爆料同學會" if asset_type == "tw_stock" else f"{symbol} 美股 OR 財報 OR AI OR 華爾街 -爆料同學會"
        news_bulls, news_bears = fetch_rss_bucket(q_str, "新聞時事", max_items=5)

        fund_bulls = []
        fund_bears = []
        rev_g_str = str(fundamentals.get("yoy_rev_growth", "N/A")).replace("%", "")
        roe_str = str(fundamentals.get("roe", "N/A")).replace("%", "")
        pe_val = fundamentals.get("pe", "N/A")

        try:
            if rev_g_str != "N/A" and float(rev_g_str) > 10:
                fund_bulls.append({"title": f"[財報基本面] 最新季度營收年增率達 +{rev_g_str}%，成長動能強勁", "url": "#", "date": "財報指標"})
            elif rev_g_str != "N/A" and float(rev_g_str) < 0:
                fund_bears.append({"title": f"[財報基本面] 最新季度營收年增率為 {rev_g_str}%，短期營收動能放緩", "url": "#", "date": "財報指標"})
        except Exception:
            pass

        try:
            if roe_str != "N/A" and float(roe_str) >= 15:
                fund_bulls.append({"title": f"[獲利能力] 股東權益報酬率 (ROE) 達 {roe_str}%，資本回報效率優異", "url": "#", "date": "獲利指標"})
        except Exception:
            pass

        try:
            if pe_val != "N/A" and float(pe_val) > 40:
                fund_bears.append({"title": f"[估值風險] 目前本益比 (PE) 達 {pe_val} 倍，處於相對高檔位階，須留意追高波動", "url": "#", "date": "估值指標"})
            elif pe_val != "N/A" and 0 < float(pe_val) <= 22:
                fund_bulls.append({"title": f"[估值優勢] 目前本益比 (PE) 為 {pe_val} 倍，具備價值防禦空間", "url": "#", "date": "估值指標"})
        except Exception:
            pass

        if not fund_bulls:
            fund_bulls.append({"title": f"[基本面] {to_trad(display_name)} 核心業務與產業競爭地位維持穩健", "url": "#", "date": "基本面評估"})
        if not fund_bears:
            fund_bears.append({"title": f"[風險提示] 留意供應鏈成本、匯率變動與終端客戶拉貨節奏", "url": "#", "date": "基本面風險"})
        if not news_bulls:
            news_bulls.append({"title": f"[新聞時事] 法人機構持續關注 {to_trad(display_name)} 新產品與營運展望", "url": "#", "date": "市場消息"})
        if not news_bears:
            news_bears.append({"title": f"[新聞時事] 短線股價受國際科技股評價調整與籌碼換手影響", "url": "#", "date": "市場消息"})

        combined_bulls = fund_bulls + news_bulls
        combined_bears = fund_bears + news_bears

        return {
            "mode": "stock_two_pillars",
            "categories": {
                "fundamentals_mops": {
                    "label": "📑 MOPS重訊・月營收・財報指標",
                    "bullish": fund_bulls[:5],
                    "bearish": fund_bears[:5]
                },
                "events": {
                    "label": "📰 產業與個股新聞時事",
                    "bullish": news_bulls[:5],
                    "bearish": news_bears[:5]
                }
            },
            "bullish": combined_bulls[:6],
            "bearish": combined_bears[:6]
        }


def fetch_ticker_full_data(symbol, display_name, asset_type="standard"):
    result = {
        "symbol": symbol,
        "name": to_trad(display_name),
        "asset_type": asset_type,
        "price": 0.0,
        "prev_close": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "ext_session": None,
        "intraday": [],
        "history": [],
        "fundamentals": {},
        "news_sentiment": {"bullish": [], "bearish": []}
    }

    try:
        tk = yf.Ticker(symbol)

        hist_2y = tk.history(period="2y", interval="1d", timeout=10)
        if not hist_2y.empty and "Close" in hist_2y.columns:
            hist_2y = hist_2y.dropna(subset=["Close"])
            for idx, row in hist_2y.iterrows():
                result["history"].append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "close": round(safe_float(row["Close"]), 2)
                })

            if len(hist_2y) >= 1:
                latest_close = safe_float(hist_2y["Close"].iloc[-1])
                prev_close = safe_float(hist_2y["Close"].iloc[-2], latest_close) if len(hist_2y) > 1 else latest_close
                result["price"] = round(latest_close, 2)
                result["prev_close"] = round(prev_close, 2)
                result["change"] = round(latest_close - prev_close, 2)
                result["change_pct"] = round(((latest_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

        hist_1d = tk.history(period="1d", interval="5m", prepost=True, timeout=10)
        if not hist_1d.empty and "Close" in hist_1d.columns:
            hist_1d = hist_1d.dropna(subset=["Close"])
            for idx, row in hist_1d.iterrows():
                result["intraday"].append({
                    "time": idx.strftime("%H:%M"),
                    "price": round(safe_float(row["Close"]), 2)
                })

        info = {}
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        market_state = str(info.get("marketState", ""))
        reg_price = safe_float(info.get("regularMarketPrice"), result["price"])
        reg_prev = safe_float(info.get("regularMarketPreviousClose"), result["prev_close"])

        if reg_price > 0 and reg_prev > 0:
            result["price"] = round(reg_price, 2)
            result["prev_close"] = round(reg_prev, 2)
            result["change"] = round(reg_price - reg_prev, 2)
            result["change_pct"] = round(((reg_price - reg_prev) / reg_prev) * 100, 2)

        if asset_type == "us_stock":
            pre_p = safe_float(info.get("preMarketPrice"), 0.0)
            post_p = safe_float(info.get("postMarketPrice"), 0.0)

            if market_state == "PRE" and pre_p > 0 and result["price"] > 0:
                pre_pct = ((pre_p - result["price"]) / result["price"]) * 100
                result["ext_session"] = {
                    "label": "盤前",
                    "price": round(pre_p, 2),
                    "change_pct": round(pre_pct, 2)
                }
            elif market_state in ["POST", "POSTPOST", "CLOSED"] and post_p > 0 and result["price"] > 0:
                post_pct = ((post_p - result["price"]) / result["price"]) * 100
                result["ext_session"] = {
                    "label": "盤後",
                    "price": round(post_p, 2),
                    "change_pct": round(post_pct, 2)
                }
            elif len(result["intraday"]) > 0 and market_state != "REGULAR":
                last_intra = result["intraday"][-1]["price"]
                if abs(last_intra - result["price"]) > 0.01 and result["price"] > 0:
                    lbl = "盤前" if (16 <= now_tw.hour <= 22) else "盤後"
                    ext_pct = ((last_intra - result["price"]) / result["price"]) * 100
                    result["ext_session"] = {
                        "label": lbl,
                        "price": round(last_intra, 2),
                        "change_pct": round(ext_pct, 2)
                    }

        elif asset_type == "futures":
            if len(result["history"]) >= 2:
                day_settlement = result["history"][-2]["close"]
                prev_settlement = result["history"][-3]["close"] if len(result["history"]) >= 3 else day_settlement
                live_globex = result["intraday"][-1]["price"] if len(result["intraday"]) > 0 else result["price"]

                result["price"] = round(day_settlement, 2)
                result["prev_close"] = round(prev_settlement, 2)
                result["change"] = round(day_settlement - prev_settlement, 2)
                result["change_pct"] = round(((day_settlement - prev_settlement) / prev_settlement) * 100, 2) if prev_settlement else 0.0

                if day_settlement > 0:
                    night_pct = ((live_globex - day_settlement) / day_settlement) * 100
                    result["ext_session"] = {
                        "label": "夜盤",
                        "price": round(live_globex, 2),
                        "change_pct": round(night_pct, 2)
                    }

        if asset_type in ["us_stock", "tw_stock"]:
            pe = safe_float(info.get("trailingPE"), None)
            f_pe = safe_float(info.get("forwardPE"), None)
            eps = safe_float(info.get("trailingEps"), None)
            gm = safe_float(info.get("grossMargins"), None)
            om = safe_float(info.get("operatingMargins"), None)
            roe = safe_float(info.get("returnOnEquity"), None)
            rev_g = safe_float(info.get("revenueGrowth"), None)

            result["fundamentals"] = {
                "pe": round(pe, 2) if pe is not None else "N/A",
                "forward_pe": round(f_pe, 2) if f_pe is not None else "N/A",
                "eps": round(eps, 2) if eps is not None else "N/A",
                "gross_margin": f"{round(gm * 100, 2)}%" if gm is not None else "N/A",
                "operating_margin": f"{round(om * 100, 2)}%" if om is not None else "N/A",
                "roe": f"{round(roe * 100, 2)}%" if roe is not None else "N/A",
                "yoy_rev_growth": f"{round(rev_g * 100, 2)}%" if rev_g is not None else "N/A",
                "monthly_rev": None
            }
        else:
            high_52 = safe_float(info.get("fiftyTwoWeekHigh"), None)
            low_52 = safe_float(info.get("fiftyTwoWeekLow"), None)
            day_h = safe_float(info.get("dayHigh"), None)
            day_l = safe_float(info.get("dayLow"), None)
            result["fundamentals"] = {
                "high_52w": round(high_52, 2) if high_52 else "N/A",
                "low_52w": round(low_52, 2) if low_52 else "N/A",
                "day_high": round(day_h, 2) if day_h else "N/A",
                "day_low": round(day_l, 2) if day_l else "N/A"
            }

        result["news_sentiment"] = build_categorized_sentiment(
            symbol, display_name, asset_type, result["fundamentals"], result["change_pct"]
        )

    except Exception as e:
        print(f"[Warn] {symbol} error: {e}")

    return result


def fetch_mops_material_info(target_stock_ids):
    mops_url = "https://openapi.twse.com.tw/v1/mops/t05st01"
    announcements = {sid: [] for sid in target_stock_ids}
    all_recent_mops = []

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(mops_url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
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
        print(f"[Warn] MOPS fetch error: {e}")

    return announcements, all_recent_mops[:15]


def fetch_twse_official_single_day(dt_str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.twse.com.tw/zh/trading/foreign/bfi82u.html"
    }

    inst_res = None
    margin_res = None

    try:
        bfi_url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate={dt_str}&type=day"
        r = requests.get(bfi_url, headers=headers, timeout=8, verify=False)
        if r.status_code == 200:
            j = r.json()
            if j.get("stat") == "OK" and j.get("data"):
                foreign_diff = 0.0
                trust_diff = 0.0
                dealer_diff = 0.0
                for row in j["data"]:
                    name = str(row[0]).strip()
                    diff_yuan = safe_float(row[3], 0.0)
                    if "外資及陸資" in name and "外資自營商" not in name:
                        foreign_diff += diff_yuan / 1e8
                    elif "投信" in name:
                        trust_diff += diff_yuan / 1e8
                    elif "自營商" in name:
                        dealer_diff += diff_yuan / 1e8
                inst_res = {
                    "foreign": round(foreign_diff, 2),
                    "trust": round(trust_diff, 2),
                    "dealer": round(dealer_diff, 2)
                }
    except Exception as e:
        print(f"[Warn] TWSE BFI82U ({dt_str}) error: {e}")

    try:
        mar_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date={dt_str}&selectType=MS"
        r2 = requests.get(mar_url, headers=headers, timeout=8, verify=False)
        if r2.status_code == 200:
            j2 = r2.json()
            tables = j2.get("tables", [])
            if tables and len(tables) > 0:
                rows = tables[0].get("data", [])
                m_yi = 0.0
                s_wan = 0.0
                for row in rows:
                    item_name = str(row[0]).strip()
                    if "融資金額" in item_name and len(row) >= 6:
                        m_yi = safe_float(row[5], 0.0) / 1e5
                    elif "融券" in item_name and len(row) >= 6:
                        s_wan = safe_float(row[5], 0.0) / 10000.0
                if m_yi > 0:
                    margin_res = {
                        "margin_yi": round(m_yi, 2),
                        "short_wan": round(s_wan, 2)
                    }
    except Exception as e:
        print(f"[Warn] TWSE MI_MARGN ({dt_str}) error: {e}")

    return inst_res, margin_res


def fetch_tw_revenue_and_chips(tw_stocks_dict, twii_history_dates):
    chip_chart_data = {
        "dates": [],
        "foreign_buy": [],
        "trust_buy": [],
        "dealer_buy": [],
        "margin_balance": [],
        "short_balance": [],
        "margin_unit": "億元"
    }

    token = os.environ.get("FINLAB_API_TOKEN")
    if token:
        try:
            import finlab
            from finlab import data as fdata
            finlab.login(token)

            rev_df = fdata.get("monthly_revenue:當月營收")
            mom_df = fdata.get("monthly_revenue:上月比較增減(%)")
            yoy_df = fdata.get("monthly_revenue:去年同月增減(%)")

            for sid, s_obj in tw_stocks_dict.items():
                if sid in rev_df.columns:
                    valid_rev = rev_df[sid].dropna()
                    if not valid_rev.empty:
                        latest_month = valid_rev.index[-1].strftime("%Y-%m")
                        val_yi = round(safe_float(valid_rev.iloc[-1]) / 100000, 2)
                        mom_val = round(safe_float(mom_df[sid].dropna().iloc[-1]), 2) if sid in mom_df.columns else 0.0
                        yoy_val = round(safe_float(yoy_df[sid].dropna().iloc[-1]), 2) if sid in yoy_df.columns else 0.0
                        s_obj["fundamentals"]["monthly_rev"] = {
                            "month": latest_month,
                            "revenue_yi": f"{val_yi} 億",
                            "mom": mom_val,
                            "yoy": yoy_val
                        }

                        rev_item = {
                            "title": f"[MOPS月營收] {latest_month} 營收 {val_yi} 億元，年增 {yoy_val:+.2f}%、月增 {mom_val:+.2f}%",
                            "url": "https://mops.twse.com.tw/mops/#/web/home",
                            "date": latest_month
                        }
                        if yoy_val >= 0:
                            s_obj["news_sentiment"]["categories"]["fundamentals_mops"]["bullish"].insert(0, rev_item)
                            s_obj["news_sentiment"]["bullish"].insert(0, rev_item)
                        else:
                            s_obj["news_sentiment"]["categories"]["fundamentals_mops"]["bearish"].insert(0, rev_item)
                            s_obj["news_sentiment"]["bearish"].insert(0, rev_item)
        except Exception as e:
            print(f"[Warn] FinLab monthly revenue error: {e}")

    target_dates = twii_history_dates[-10:] if len(twii_history_dates) >= 10 else twii_history_dates
    for iso_d in target_dates:
        ymd = iso_d.replace("-", "")
        md_label = iso_d[5:].replace("-", "/")
        inst_d, mar_d = fetch_twse_official_single_day(ymd)
        if inst_d is not None:
            chip_chart_data["dates"].append(md_label)
            chip_chart_data["foreign_buy"].append(inst_d["foreign"])
            chip_chart_data["trust_buy"].append(inst_d["trust"])
            chip_chart_data["dealer_buy"].append(inst_d["dealer"])
            if mar_d is not None:
                chip_chart_data["margin_balance"].append(mar_d["margin_yi"])
                chip_chart_data["short_balance"].append(mar_d["short_wan"])
            else:
                chip_chart_data["margin_balance"].append(None)
                chip_chart_data["short_balance"].append(None)
        time.sleep(0.35)

    return chip_chart_data


def main():
    os.makedirs("data", exist_ok=True)

    print("1. Fetching Global Indices...")
    indices_data = [fetch_ticker_full_data(k, v, "index") for k, v in INDICES.items()]

    twii_dates = []
    for idx_obj in indices_data:
        if idx_obj["symbol"] == "^TWII" and idx_obj["history"]:
            twii_dates = [h["date"] for h in idx_obj["history"][-12:]]

    print("2. Fetching US Stocks...")
    us_stocks_data = [fetch_ticker_full_data(sym, sym, "us_stock") for sym in US_STOCKS]

    print("3. Fetching TW Stocks...")
    tw_stocks_map = {}
    for code, meta in TW_STOCKS.items():
        tw_stocks_map[code] = fetch_ticker_full_data(meta["ticker"], meta["name"], "tw_stock")
        tw_stocks_map[code]["tw_code"] = code

    print("4. Fetching MOPS Announcements...")
    mops_by_stock, mops_latest_list = fetch_mops_material_info(list(TW_STOCKS.keys()))
    for code, s_obj in tw_stocks_map.items():
        anns = mops_by_stock.get(code, [])
        s_obj["mops_announcements"] = anns
        for m in anns[:3]:
            subj = to_trad(m["subject"])
            m_obj = {
                "title": f"[MOPS重訊] {subj}",
                "url": m["url"],
                "date": f"{m['date']} {m['time']}"
            }
            if any(k in subj for k in BEAR_KEYWORDS):
                s_obj["news_sentiment"]["categories"]["fundamentals_mops"]["bearish"].insert(0, m_obj)
            else:
                s_obj["news_sentiment"]["categories"]["fundamentals_mops"]["bullish"].insert(0, m_obj)

    print("5. Fetching Official TWSE Institutional & Margin Data...")
    chip_chart_data = fetch_tw_revenue_and_chips(tw_stocks_map, twii_dates)

    print("6. Fetching Futures & Commodities...")
    futures_data = [fetch_ticker_full_data(k, v, "futures") for k, v in FUTURES_AND_COMMODITIES.items()]

    print("7. Fetching FX & Bonds...")
    fx_bonds_data = [fetch_ticker_full_data(k, v, "fx_bond") for k, v in FX_AND_BONDS.items()]

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

    print("Success! data/market_data.json generated.")

if __name__ == "__main__":
    main()
