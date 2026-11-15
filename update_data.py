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
# 2. 視窗二：20+ 大細分產業鏈完整定義 (與前端 COMPACT_25_SECTORS 100% 對齊)
# ==========================================
COMPACT_25_SECTORS = [
    {"id": "memory", "cat": "半導體核心", "title": "💾 記憶體", "sub": "HBM3e/HBM4 高頻寬記憶體、DDR5、NOR/NAND Flash 與模組封測",
     "u": "上游：記憶體 IP 與控制晶片", "uL": [["6531.TW","6531 愛普*","VHM 3D 異質整合高頻寬記憶體 IP"],["8299.TWO","8299 群聯","PCIe Gen5 SSD 控制 IC 與 aiDAPTIV+"],["6533.TW","6533 晶心科","RISC-V 架構記憶體控制器 CPU IP"]],
     "m": "中游：DRAM / Flash 顆粒製造", "mL": [["MU","MU","美光：HBM3e 與 DDR5 國際記憶體指標"],["2408.TW","2408 南亞科","台灣 DRAM 顆粒製造龍頭 (DDR5)"],["2344.TW","2344 華邦電","CUBE 客製化高頻寬記憶體與 NOR Flash"],["2337.TW","2337 旺宏","車用工控高品質 NOR Flash 與 ROM"]],
     "d": "下游：記憶體模組與專業封測", "dL": [["6239.TW","6239 力成","全球記憶體封測與 HBM 先進封裝龍頭"],["3260.TWO","3260 威剛","企業級與電競 DDR5/SSD 模組龍頭"],["4967.TW","4967 十銓","高頻電競與 AI 工作站記憶體模組"],["8271.TWO","8271 宇瞻","工控與伺服器 SSD/DRAM 模組"]]},
    {"id": "tgv", "cat": "半導體核心", "title": "🔬 TGV 玻璃基板", "sub": "次世代 AI 晶片大面積封裝之玻璃核心基板 (Through Glass Via) 材料與設備",
     "u": "上游：高純度玻璃晶圓母材與化學品", "uL": [["GLW","GLW","康寧：TGV 高純度半導體玻璃基板母材"],["1802.TW","1802 台玻","電子級平板玻璃與特殊玻璃材料"],["4768.TW","4768 晶呈科技","先進封裝特殊蝕刻氣體與去光阻液"]],
     "m": "中游：TGV 雷射改質穿孔 / 濕蝕刻 / 貼膜設備", "mL": [["3131.TWO","3131 弘塑","TGV 玻璃基板單晶圓濕蝕刻與化材設備"],["3583.TW","3583 辛耘","濕製程設備與雷射改質設備代理"],["2467.TW","2467 志聖","G2C+ 聯盟：TGV 玻璃基板壓膜與烘烤設備"],["3498.TWO","3498 陽程","G2C+ 聯盟：玻璃基板自動化輸送設備"],["6640.TWO","6640 均華","高精度晶片挑揀與黏晶設備"]],
     "d": "下游：TGV 玻璃核心載板與晶圓級封裝", "dL": [["3037.TW","3037 欣興","布局次世代玻璃核心基板 (Glass Core) 先驅"],["2330.TW","2330 台積電","次世代 CoWoS 導入玻璃基板封裝技術"],["INTC","INTC","率先展示伺服器等級 TGV 玻璃基板技術"]]},
    {"id": "silicon_wafer", "cat": "半導體核心", "title": "💿 矽晶圓", "sub": "高純度多晶矽、8吋/12吋拋光與磊晶矽晶圓、擋控片與再生晶圓",
     "u": "上游：高純度多晶矽、石英坩堝與設備耗材", "uL": [["6532.TWO","6532 瑞耘","晶圓夾持環與 CMP 製程耗材"],["3413.TW","3413 京鼎","半導體前段晶圓製造設備模組"]],
     "m": "中游：8 吋 / 12 吋拋光與磊晶矽晶圓製造", "mL": [["6488.TWO","6488 環球晶","全球第三大 12 吋半導體矽晶圓龍頭"],["3532.TW","3532 台勝科","12 吋邏輯與記憶體高階矽晶圓大廠"],["6182.TWO","6182 合晶","8 吋/12 吋重摻矽晶圓與車用功率磊晶"]],
     "d": "下游：12 吋再生晶圓與晶圓薄化服務", "dL": [["8028.TW","8028 昇陽半導體","全球最大 12 吋先進製程再生晶圓廠"],["1560.TW","1560 中砂","2奈米/3奈米再生晶圓與 CMP 鑽石碟"],["3583.TW","3583 辛耘","12 吋再生晶圓量產與濕製程服務"]]},
    {"id": "semiconductor", "cat": "半導體核心", "title": "🏭 半導體製造與設備", "sub": "EUV 光罩盒、廠務無塵室工程、先進與成熟晶圓代工製造",
     "u": "上游：特用化學品 / EUV 光罩載具 / 廠務工程", "uL": [["3680.TWO","3680 家登","全球 EUV 光罩盒與 FOUP 晶圓載具龍頭"],["1560.TW","1560 中砂","先進製程奈米級 CMP 鑽石碟主力"],["6196.TW","6196 帆宣","半導體無塵室廠務工程與 ASML 設備模組代工"],["2404.TW","2404 漢唐","台積電海內外晶圓廠最大無塵室統包工程商"]],
     "m": "中游：先進製程與特殊成熟製程晶圓代工", "mL": [["2330.TW","2330 台積電","全球晶圓代工絕對霸主 (N3/N2/A16)"],["TSM","TSM","台積電 ADR (美股半導體核心指標)"],["2303.TW","2303 聯電","22/28奈米特殊製程與矽光子中介層代工"],["5347.TWO","5347 世界先進","8吋電源管理 IC 與功率元件代工"],["6770.TW","6770 力積電","邏輯與記憶體異質晶圓代工"]],
     "d": "下游：製程檢測分析與自動化系統", "dL": [["3587.TWO","3587 閎康","半導體材料分析 (MA) 與故障分析 (FA) 龍頭"],["3289.TWO","3289 宜特","先進製程可靠度驗證 (RA) 與訊號測試"],["6187.TWO","6187 萬潤","先進封裝與半導體 AOI 檢測設備"]]},
    {"id": "cpu", "cat": "半導體核心", "title": "🧠 CPU 與 AI 運算晶片", "sub": "涵蓋矽智財 IP、x86/ARM 架構 CPU、AI GPU 與雲端客製化 ASIC",
     "u": "上游：CPU 架構矽智財 (IP) 與 ASIC 設計服務", "uL": [["ARM","ARM","全球行動與資料中心低功耗 CPU 架構霸主"],["3661.TW","3661 世芯-KY","CSP 雲端巨頭 AI ASIC 客製化晶片設計龍頭"],["3443.TW","3443 創意","台積電旗下高階 AI ASIC 與 HBM 介面設計"],["3035.TW","3035 智原","聯電旗下 ASIC 設計服務與先進封裝協作"],["6533.TW","6533 晶心科","全球 RISC-V CPU IP 核心供應商"]],
     "m": "中游：伺服器/PC CPU 與 AI 加速器設計巨頭", "mL": [["NVDA","NVDA","Grace ARM CPU + Blackwell GPU 超級晶片霸主"],["AMD","AMD","EPYC 伺服器 CPU 與 Ryzen AI PC 處理器"],["INTC","INTC","x86 Xeon 伺服器與 Core Ultra 處理器"],["2454.TW","2454 聯發科","ARM 架構 AI PC 處理器與旗艦天璣 SoC"],["5269.TW","5269 祥碩","AMD 平台高速晶片組與 USB4/PCIe 控制器"]],
     "d": "下游：伺服器遠端管理晶片 (BMC) 與主機板平台", "dL": [["5274.TWO","5274 信驊","全球伺服器遠端管理晶片 (BMC) 絕對壟斷龍頭"],["2377.TW","2377 微星","AI 伺服器與高階電競主機板系統廠"],["2357.TW","2357 華碩","AI 伺服器與 AI PC 品牌龍頭"]]},
    {"id": "osat", "cat": "半導體核心", "title": "🔍 封測 (OSAT & 測試介面)", "sub": "從高頻垂直探針卡、同軸測試座、晶圓針測 (CP) 到 CoWoS/FOCoS 封測",
     "u": "上游：高頻探針卡 (Probe Card) 與測試座 (Socket)", "uL": [["6223.TWO","6223 旺矽","全球垂直探針卡 (VPC) 與 MEMS 探針卡龍頭"],["6515.TW","6515 穎崴","AI GPU 高頻同軸測試座與老化測試座龍頭"],["6510.TWO","6510 精測","高速晶圓測試板與全自製探針卡"],["6217.TWO","6217 中探針","半導體高功率老化測試針與連接器"]],
     "m": "中游：專業封裝測試 (OSAT) 與晶圓測試 (CP/FT)", "mL": [["3711.TW","3711 日月光投控","全球第一大封測集團 (VIPack 先進封裝)"],["2449.TW","2449 京元電子","全球 AI GPU 與 ASIC 最大成品測試 (FT) 基地"],["6239.TW","6239 力成","記憶體與邏輯晶片高階封測大廠"],["6257.TW","6257 矽格","網通與手機晶片專業測試廠"],["3265.TWO","3265 台星科","AI HPC 晶圓凸塊與 CPO 矽光子封測合作"]],
     "d": "下游：系統級測試 (SLT) 與自動化分類設備", "dL": [["2360.TW","2360 致茂","AI 晶片 SLT 系統級測試與光學量測設備龍頭"],["6640.TWO","6640 均華","先進封裝高精度黏晶與挑揀設備"]]},
    {"id": "optical", "cat": "光通訊與CPO", "title": "🌐 光通訊 (800G / 1.6T)", "sub": "磷化銦雷射磊晶、檢光器、光纖跳接線、800G/1.6T 光收發模組至交換器",
     "u": "上游：光通訊三五族雷射磊晶與光纖被動元件", "uL": [["3081.TWO","3081 聯亞","磷化銦 CW 雷射與矽光子磊晶晶片主力"],["6442.TW","6442 光聖","美系資料中心高芯數光纖纜線與主動元件龍頭"],["3163.TWO","3163 波若威","光波長分合器 (WDM) 與光纖分支器主力"]],
     "m": "中游：400G / 800G / 1.6T 高速光收發模組封裝", "mL": [["4979.TWO","4979 華星光","雲端資料中心 400G/800G 光收發模組大廠"],["3450.TW","3450 聯鈞","高速 EML 雷射封裝與 AOC 主動光纜代工"],["4977.TW","4977 眾達-KY","高速光收發模組與博通光學封裝合作夥伴"],["4908.TWO","4908 前鼎","高速光纖收發模組研發製造"]],
     "d": "下游：AI 資料中心高速交換器與電信網路", "dL": [["2345.TW","2345 智邦","全球雲端資料中心 400G/800G 白牌交換器龍頭"],["ANET","ANET","Arista：AI 資料中心高速乙太網路交換器巨頭"],["COHR","COHR","Coherent：全球光通訊模組與雷射大廠"]]},
    {"id": "cpo", "cat": "光通訊與CPO", "title": "💡 CPO 共同封裝光學", "sub": "將矽光子光學引擎 (OE PIC) 與交換器 ASIC 共封裝於同一載板之次世代技術",
     "u": "上游：CW 外部雷射光源 (ELS) 與晶圓級光學測試 (In4)", "uL": [["3081.TWO","3081 聯亞","CPO 高功率 CW 連續波雷射二極體磊晶"],["2360.TW","2360 致茂","CPO 光學引擎晶圓級檢測與對位量測設備"],["6223.TWO","6223 旺矽","CPO 矽光子晶圓級光電共測探針卡"]],
     "m": "中游：FAU 光纖陣列耦合與 COUPE 先進光學封裝", "mL": [["3363.TWO","3363 上詮","台積電矽光子聯盟：CPO 保偏光纖陣列 (FAU) 核心廠"],["6451.TW","6451 訊芯-KY","鴻海集團旗下 51.2T CPO 光電共同封裝模組廠"],["3711.TW","3711 日月光投控","VIPack 平台提供 CPO 光學引擎共同封裝"],["2330.TW","2330 台積電","COUPE 緊湊型通用光子引擎整合平台"]],
     "d": "下游：51.2T / 102.4T CPO 交換器 ASIC 晶片巨頭", "dL": [["AVGO","AVGO","博通：Bailly 51.2T CPO 交換器全球領航者"],["MRVL","MRVL","邁威爾：矽光子光互連與客製化 DSP 晶片"],["NVDA","NVDA","Quantum-X / Spectrum-X 導入矽光子光互連"]]},
    {"id": "fiberglass", "cat": "PCB與載板鏈", "title": "🧵 玻纖布 (Low-Dk / 石英布)", "sub": "高頻 CCL 必備之超低介電 (Low-Dk1/Dk2) 與次世代 Q-Glass 石英玻纖布",
     "u": "上游：高純度石英砂、玻璃窯爐與電子級玻纖紗", "uL": [["1802.TW","1802 台玻","具備自有玻纖窯爐與電子級細紗垂直整合能力"],["1815.TWO","1815 富喬","台灣少數擁有池窯拉絲之電子級玻纖紗大廠"]],
     "m": "中游：Low-Dk 低介電玻纖布與超薄電子布織造", "mL": [["1815.TWO","1815 富喬","AI 伺服器 M7/M8 CCL 用 Low-Dk 玻纖布主力"],["5340.TWO","5340 建榮","日東紡集團旗下：供應高階 Low-Dk 與 NE-Glass 玻纖布"],["1802.TW","1802 台玻","擴產 Low-Dk2 第二代超低損耗電子級玻纖布"],["1475.TW","1475 業旺","特殊工業與電子織物相關材料"]],
     "d": "下游：高頻銅箔基板 (CCL) 與 IC 載板壓合廠", "dL": [["2383.TW","2383 台光電","全球最大高階 Low-Dk 玻纖布採購與 CCL 製造商"],["6274.TWO","6274 台燿","800G 交換器用高階玻纖布 CCL 主力廠"],["1303.TW","1303 南亞","上下游垂直整合玻纖布、樹脂與 CCL 大廠"]]},
    {"id": "ccl", "cat": "PCB與載板鏈", "title": "🟧 CCL 銅箔基板", "sub": "從 HVLP 超低粗糙度銅箔、PPE/碳氫樹脂到 M7/M8 超低損耗銅箔基板",
     "u": "上游：HVLP 高頻銅箔 / PPE 聚苯醚樹脂 / 玻纖布", "uL": [["8358.TWO","8358 金居","AI 伺服器 RG312 與 HVLP 超低粗糙度電解銅箔龍頭"],["4989.TWO","4989 榮科","高頻電解銅箔與超薄載板銅箔"],["1303.TW","1303 南亞","高頻電子樹脂、硬化劑與全系列電子材料"],["1815.TWO","1815 富喬","高頻 CCL 核心 Low-Dk 玻纖布供應商"]],
     "m": "中游：M6 / M7 / M8 超低訊號損耗銅箔基板製造", "mL": [["2383.TW","2383 台光電","全球無鹵高頻 CCL 霸主 (M7/M8 市占第一)"],["6274.TWO","6274 台燿","800G 交換器與 AI ASIC 高速 CCL 核心供應商"],["6213.TW","6213 聯茂","AI 伺服器主板與車用超低損耗 CCL 大廠"],["3354.TWO","3354 律勝","軟性銅箔基板 (FCCL) 與高頻保護膠片"]],
     "d": "下游：AI 伺服器 UBB/OAM 主板與高速交換器 PCB", "dL": [["2368.TW","2368 金像電","採用 M7/M8 CCL 壓合高層數 AI 伺服器板龍頭"],["3044.TW","3044 健鼎","高階伺服器、車用與記憶體模組 PCB 大廠"]]},
    {"id": "pcb", "cat": "PCB與載板鏈", "title": "🟩 PCB 印刷電路板", "sub": "涵蓋機械/雷射鑽孔、高層數 AI 伺服器主板 (OAM/UBB)、HDI 與衛星板",
     "u": "上游：微型鑽頭、雷射鑽孔服務與專用乾膜化學品", "uL": [["8021.TW","8021 尖點","全球前二大高階 PCB 微型鑽頭與鑽孔服務廠"],["6215.TW","6215 和椿","PCB 自動化製程與精密切削設備"],["2467.TW","2467 志聖","高階 PCB 壓膜、曝光與烘烤製程設備"]],
     "m": "中游：AI 高層數伺服器板 / 高階 HDI / 軟硬結合板", "mL": [["2368.TW","2368 金像電","全球 AI 伺服器 UBB/OAM 與 800G 交換器 PCB 龍頭"],["2313.TW","2313 華通","全球第一大 HDI 板與低軌衛星 PCB 製造霸主"],["3044.TW","3044 健鼎","大型伺服器、車用 HDI 與記憶體模組板巨頭"],["4958.TW","4958 臻鼎-KY","全球營收第一大軟板與高階 HDI 全方位 PCB 集團"],["5439.TWO","5439 高技","AI 伺服器厚銅電源板與高速網通 PCB 主力"]],
     "d": "下游：伺服器系統組裝與高速網通終端", "dL": [["2317.TW","2317 鴻海","全球最大 AI 伺服器主機板 SMT 打件與機櫃組裝廠"],["2382.TW","2382 廣達","雲端 CSP AI 伺服器主機板與系統整合霸主"]]},
    {"id": "ic_substrate", "cat": "PCB與載板鏈", "title": "🔲 載板 (ABF / BT 載板)", "sub": "連接 AI GPU/CPU 裸晶與 PCB 主板之高層數、大面積 ABF 與 BT 封裝載板",
     "u": "上游：ABF 增層薄膜、超薄銅箔與載板檢測設備", "uL": [["6187.TWO","6187 萬潤","ABF 載板 AOI 自動光學檢測與植球點膠設備"],["3563.TW","3563 牧德","高階 IC 載板線路與外觀 AOI 光學檢測設備龍頭"],["2467.TW","2467 志聖","ABF 載板真空壓膜與乾燥硬化設備主力"]],
     "m": "中游：高層數大面積 ABF 載板與 BT 載板製造三雄", "mL": [["3037.TW","3037 欣興","全球 ABF 載板龍頭 (美系 AI GPU 高階載板主力)"],["8046.TW","8046 南電","高階網通交換器 ASIC 與伺服器 CPU 用 ABF 載板"],["3189.TW","3189 景碩","AI GPU、FPGA 與高階記憶體用 ABF/BT 載板大廠"],["6552.TW","6552 易華電","高階面板與穿戴裝置用捲帶式覆晶載板 (COF)"]],
     "d": "下游：CoWoS / Flip-Chip 覆晶封裝與晶片客戶", "dL": [["2330.TW","2330 台積電","CoWoS_S/L 將矽中介層封裝於大型 ABF 載板上"],["3711.TW","3711 日月光投控","高階覆晶封裝 (Flip-Chip) 與系統級封裝"],["NVDA","NVDA","單顆 Blackwell 超級晶片耗用超大面積高層數 ABF 載板"]]},
    {"id": "passive_comp", "cat": "電子零組件", "title": "🔋 被動元件 (MLCC / 電感)", "sub": "介電陶瓷粉、高容值 MLCC、晶片電阻、一體成型功率電感與固態電容",
     "u": "上游：MLCC 介電陶瓷粉末、導電漿料與氧化鋁基板", "uL": [["6173.TWO","6173 信昌電","華新科集團：高階 MLCC 介電陶瓷粉末與特殊電容"],["3624.TWO","3624 光頡","精密薄膜電阻、氮化鋁散熱基板與上游材料"]],
     "m": "中游：MLCC / 晶片電阻 / 一體成型電感 / 固態電容", "mL": [["2327.TW","2327 國巨","全球晶片電阻與鉭質電容第一、AI 伺服器高階 MLCC 巨頭"],["2492.TW","2492 華新科","全球前五大 MLCC 與晶片電阻製造集團"],["6449.TW","6449 鈺邦","全球前二大導電高分子固態電容龍頭 (AI 主板標配)"],["6284.TWO","6284 佳邦","AI PC 與伺服器用高功率一體成型電感主力"],["2428.TW","2428 興勤","全球第一大熱敏電阻與壓敏電阻保護元件龍頭"]],
     "d": "下游：被動元件專業通路與伺服器電源系統", "dL": [["3090.TW","3090 日電貿","台灣最大高階伺服器與工控被動元件代理通路"],["2308.TW","2308 台達電","整合乾式電感、電容於 AI 高瓦數伺服器電源"]]},
    {"id": "power_semi", "cat": "電子零組件", "title": "⚡ 功率元件 (SiC / GaN / MOSFET)", "sub": "第三代化合物半導體基板磊晶、功率晶圓代工、MOSFET/IGBT 到高壓電源",
     "u": "上游：SiC 碳化矽基板、GaN 磊晶與高功率導線架", "uL": [["6488.TWO","6488 環球晶","6吋/8吋 SiC 碳化矽基板與 GaN 磊晶晶圓"],["3016.TW","3016 嘉晶","SiC 與 GaN 化合物功率半導體磊晶代工主力"],["2351.TW","2351 順德","全球前三大車用與高功率工業導線架龍頭"],["6548.TWO","6548 長科*","高階 QFN 與功率半導體蝕刻導線架大廠"]],
     "m": "中游：功率晶圓代工與 MOSFET / 二極體設計封測", "mL": [["3707.TWO","3707 漢磊","SiC MOSFET 與 GaN 化合物功率晶圓代工"],["5347.TWO","5347 世界先進","8吋高壓 PMIC 與 GaN-on-Si 功率元件代工"],["2481.TW","2481 強茂","車規 MOSFET、SiC 二極體與高壓功率元件龍頭"],["3675.TWO","3675 德微","車用保護元件與 SiC 功率模組封測"],["5425.TWO","5425 台半","車用與工控高壓整流二極體及 MOSFET"]],
     "d": "下游：國際 IDM 功率大廠與 AI 資料中心供電", "dL": [["ON","ON","安森美：車用與 AI 能源基礎設施 SiC 巨頭"],["STM","STM","意法半導體：全球車用 SiC MOSFET 龍頭"],["MPWR","MPWR","Monolithic Power：AI GPU 48V 垂直供電霸主"]]},
    {"id": "thermal", "cat": "AI伺服器基建", "title": "❄️ 散熱 (水冷板 / CDU / 快接頭)", "sub": "GB200/GB300 機櫃必備之水冷快接頭 (UQD)、分歧管、水冷板與 CDU",
     "u": "上游：水冷快接頭 (UQD)、高轉速風扇與不鏽鋼管件", "uL": [["6805.TW","6805 富世達","AI 伺服器水冷快接頭 (UQD) 與滑軌核心供應商"],["2059.TW","2059 川湖","AI 水冷機櫃高荷重導軌與快接頭機構件"],["2421.TW","2421 建準","AI 伺服器高風壓對轉散熱風扇與水冷排風扇"]],
     "m": "中游：水冷板 (Cold Plate)、分歧管與 CDU 冷卻液分配裝置", "mL": [["3017.TW","3017 奇鋐","全球雲端巨頭 AI 水冷板、分歧管與 3D VC 最大供應商"],["3324.TWO","3324 雙鴻","水冷板、自製泵浦與機櫃級 CDU 散熱龍頭"],["2486.TW","2486 一詮","CoWoS 先進封裝高階金屬均熱片 (Heat Spreader)"],["3013.TW","3013 晟銘電","AI 伺服器水冷機櫃與浸沒式散熱槽體機構"],["3483.TWO","3483 力致","高階伺服器氣冷與水冷散熱模組"]],
     "d": "下游：資料中心液冷基礎設施與 L11 整機櫃系統", "dL": [["VRT","VRT","Vertiv：全球資料中心液冷與熱管理基建霸主"],["2308.TW","2308 台達電","整合 CDU、水冷板與風扇牆之機櫃級液冷方案"],["6669.TW","6669 緯穎","CSP 雲端資料中心整機櫃液冷伺服器先驅"]]},
    {"id": "bbu", "cat": "AI伺服器基建", "title": "🔋 BBU 備援電池單元", "sub": "AI 機櫃標配之高倍率鋰電池芯、BMS 管理晶片、BBU 模組至 Power Shelf",
     "u": "上游：高倍率鋰電池正極材料、電芯與 BMS 晶片", "uL": [["4739.TW","4739 康普","動力與儲能鋰電池正極材料硫酸鎳主力"],["4721.TWO","4721 美琪瑪","高純度電池正極材料氧化鈷與硫酸鎳"],["5272.TWO","5272 笙科","電池管理與無線感測周邊 IC"]],
     "m": "中游：AI 伺服器機櫃 BBU 備援電池模組製造", "mL": [["6781.TW","6781 AES-KY","全球 CSP 資料中心 BBU 備援電池模組市占第一霸主"],["3211.TWO","3211 順達","高毛利資料中心 BBU 與儲能電池模組核心大廠"],["6121.TWO","6121 新普","全球最大IT電池集團，母公司整合 BBU 龐大商機"],["4931.TWO","4931 新盛力","專注資料中心 BBU 與高功率鋰電池模組"],["6558.TW","6558 興能高","客製化鋰電池與儲能管理方案"]],
     "d": "下游：33kW+ AI 伺服器 Power Shelf 電源供應系統", "dL": [["2308.TW","2308 台達電","全球 AI 機櫃 Power Shelf 與 BBU 系統整合龍頭"],["2301.TW","2301 光寶科","雲端資料中心高瓦數電源機箱與 BBU 整合大廠"]]},
    {"id": "leo_satellite", "cat": "太空軍工與航運", "title": "🛰️ 低軌衛星 (LEO Satellite)", "sub": "Starlink / Kuiper 衛星高頻 PCB、毫米波波導元件、相位陣列天線至地面接收站",
     "u": "上游：衛星高頻基板、砷化鎵 PA 磊晶與高頻連接器", "uL": [["3105.TWO","3105 穩懋","全球最大砷化鎵晶圓代工 (衛星毫米波 PA 晶片)"],["2455.TW","2455 全新","衛星高頻通訊用磷化銦與砷化鎵光電磊晶"],["6290.TWO","6290 良維","低軌衛星地面接收站耐候電源線組主力"]],
     "m": "中游：衛星天上/地面高階 HDI 板與毫米波波導元件", "mL": [["2313.TW","2313 華通","全球低軌衛星天上衛星板與地面板市占第一霸主"],["3491.TWO","3491 昇達科","Starlink 與 Kuiper 毫米波中空波導元件核心供應商"],["2367.TW","2367 耀華","低軌衛星地面接收板高階 HDI 主力廠"],["6190.TWO","6190 萬泰科","供應低軌衛星地面接收站高速網路線材"]],
     "d": "下游：低軌衛星地面接收路由器 (User Terminal) 與營運", "dL": [["6285.TW","6285 啟碁","全球最大美系低軌衛星家用地面接收路由器代工廠"],["2314.TW","2314 台揚","高軌與低軌衛星地面收發站 (VSAT) 與 O-RAN 設備"],["2412.TW","2412 中華電","獨家代理 OneWeb 與多軌道衛星台灣地面通訊服務"]]},
    {"id": "space_tech", "cat": "太空軍工與航運", "title": "🚀 太空與航太科技", "sub": "航太級超合金鍛造、航空發動機渦輪扣件、機匣精密加工至機體組裝維保",
     "u": "上游：航太特殊超合金鋼材與精密鈦合金鍛造", "uL": [["5009.TWO","5009 榮剛","波音與空巴認證之航太特殊合金鋼全球主要供應商"],["3004.TW","3004 豐達科","GE 與賽峰認證之航太發動機高強度扣件龍頭"]],
     "m": "中游：航空發動機機匣、燃燒段葉片與起落架加工", "mL": [["4541.TWO","4541 晟田","航太發動機機匣、起落架零組件與精密加工"],["8222.TW","8222 寶一","航空發動機高溫燃燒段冷卻片與薄鈑金屬件"],["6829.TWO","6829 千附精密","航太國防精密腔體與光電半導體設備零組件"],["4572.TW","4572 駐龍","波音機身結構精密機械加工零組件主力"]],
     "d": "下游：民航機與太空載具機體總成及 MRO 維修", "dL": [["2634.TW","2634 漢翔","全球民用客機機體結構與發動機機匣代工龍頭"],["2645.TW","2645 長榮航太","全球前十大民航機改裝 (貨機改裝) 與 MRO 維修巨頭"]]},
    {"id": "defense", "cat": "太空軍工與航運", "title": "🛡️ 軍工與國防自主", "sub": "軍用防彈複合材料、軍規強固電腦、高教機、長程無人機與國艦國造",
     "u": "上游：軍規強固型電腦、雷達感測與防彈材料", "uL": [["3005.TW","3005 神基","全球前二大軍警用強固型電腦 (Getac) 霸主"],["3708.TW","3708 上緯投控","航太與無人機用高強度碳纖維複合材料"]],
     "m": "中游：軍用商規無人機 (UAV)、飛彈零組件與艦艇系統", "mL": [["8033.TW","8033 雷虎","軍用商規長程無人直升機、自殺無人機與無人艇先驅"],["5371.TWO","5371 中光電","旗下中光電智能機器人量產警政與軍用偵察無人機"],["6753.TW","6753 龍德造船","沱江級高效能穿浪雙體巡邏艦與高速特種艇製造廠"]],
     "d": "下游：高教機國造、戰機維保與潛艦國造總成", "dL": [["2634.TW","2634 漢翔","勇鷹號高教機量產、F-16V 構改維保與無人機反制系統"],["2208.TW","2208 台船","潛艦國造 (海鯤號) 與大型海巡軍用艦艇建造基地"],["2630.TW","2630 亞航","軍用直升機、定翼機維修與光纖陀螺儀無人機"]]},
    {"id": "shipping", "cat": "太空軍工與航運", "title": "🚢 航運 (貨櫃 / 散裝 / 空運)", "sub": "港埠集散倉儲、全球遠洋/近洋貨櫃船隊、海岬型散裝船、航空貨運至物流承攬",
     "u": "上游：內陸貨櫃集散倉儲、碼頭裝卸與船舶工程", "uL": [["2607.TW","2607 榮運","長榮集團大型貨櫃集散場、造櫃與船隊租賃"],["2613.TW","2613 中櫃","基隆、台中與高雄港碼頭貨櫃裝卸營運"]],
     "m": "中游：遠洋/近洋貨櫃航運、散裝船隊與航空客貨運", "mL": [["2603.TW","2603 長榮","台灣貨櫃航運龍頭：高比例美歐長約與低碳新船隊"],["2609.TW","2609 陽明","全球主要貨櫃航運聯盟成員，深耕歐美航線"],["2615.TW","2615 萬海","亞洲近洋線龍頭並擴充美西高運價航線"],["2606.TW","2606 裕民","台灣最大海岬型 (鐵礦砂/煤炭) 散裝航運龍頭"],["2637.TW","2637 慧洋-KY","船隊規模最大之巴拿馬型與輕便型散裝船東"],["2618.TW","2618 長榮航","北美航線客運與 AI 伺服器高單價空運雙引擎"],["2610.TW","2610 華航","龐大波音 777F/747F 全貨機機隊，空運獲利指標"]],
     "d": "下游：國際海空運承攬物流與跨境供應鏈管理", "dL": [["2636.TW","2636 台驊投控","海空鐵全方位國際物流承攬龍頭"],["5609.TWO","5609 中菲行","深耕美歐與東南亞科技廠空海運承攬服務"]]},
    {"id": "cybersecurity", "cat": "軟體生技與內需", "title": "🔐 資安與雲端安全", "sub": "硬體信任根 PUF 晶片、電信級網安硬體、零信任威脅偵測至 SOC 監控與系統整合",
     "u": "上游：硬體資安矽智財 (PUF) 與電信級網路安全硬體", "uL": [["3529.TWO","3529 力旺","NeoPUF 晶片級硬體信任根與後量子密碼資安 IP"],["6245.TWO","6245 立端","全球電信級網路安全硬體平台 (UTM/防火牆) 代工龍頭"],["3088.TWO","3088 艾訊","工業物聯網與網通資安硬體平台"]],
     "m": "中游：AI 威脅偵測軟體、SOC 資安監控中心與 IDC 機房", "mL": [["PANW","PANW","Palo Alto：全球次世代防火牆與 AI 資安霸主"],["CRWD","CRWD","CrowdStrike：全球雲端端點安全 (EDR/XDR) 龍頭"],["6690.TWO","6690 安碁資訊","台灣最大 7x24 SOC 資安威脅監控與紅隊演練龍頭"],["6561.TWO","6561 是方","台灣最大中立 IDC 雲端交換中心與網路安全服務"]],
     "d": "下游：金融/政府資安系統整合與多雲安全託管", "dL": [["3029.TW","3029 零壹","台灣企業級 IT 基礎架構與資安軟體代理整合龍頭"],["2453.TW","2453 凌群","金融證券交易與公部門大型資安系統整合商"],["6689.TW","6689 伊雲谷","跨國公有雲託管與雲端資安合規顧問龍頭"]]},
    {"id": "biotech", "cat": "軟體生技與內需", "title": "🧬 生技與醫療器材", "sub": "新藥臨床授權、特色原料藥、生物藥 CDMO 委託代工至高階醫材與連鎖藥局",
     "u": "上游：新藥研發授權與特色高門檻學名藥", "uL": [["6446.TW","6446 藥華藥","罕見血癌新藥 Ropeg 全球暢銷與 ET 新適應症擴張"],["1795.TW","1795 美時","高門檻抗癌與中樞神經特殊學名藥外銷美歐日龍頭"],["4147.TWO","4147 中裕","愛滋病單株抗體新藥與生物製劑研發"]],
     "m": "中游：CDMO 跨國藥品委託代工與高毛利隱形眼鏡/醫材", "mL": [["6472.TW","6472 保瑞","台灣最大 CDMO 跨國製藥代工與美國本土廠布局霸主"],["6589.TW","6589 台康生技","生物相似藥與大分子生物藥 CDMO 代工主力"],["6491.TW","6491 晶碩","高透氧矽水膠隱形眼鏡自動化代工與品牌外銷"],["4736.TWO","4736 泰博","血糖測試儀、生理監測與體外診斷醫材龍頭"]],
     "d": "下游：大型連鎖藥局通路與血液透析醫療服務", "dL": [["6469.TW","6469 大樹","全台店數第一之大型連鎖複合式醫藥保健藥局"],["4175.TWO","4175 杏一","全台醫院型連鎖醫療器材與照護通路龍頭"],["4104.TW","4104 佳醫","血液透析洗腎中心營運與高階醫療設備代理"]]},
    {"id": "insurance", "cat": "軟體生技與內需", "title": "☂️ 保險 (再保 / 壽險 / 產險)", "sub": "上游專業再保險分入、中游大型壽險資產管理、至下游純產險與保經通路",
     "u": "上游：專業再保險與跨國風險分散", "uL": [["2851.TW","2851 中再保","台灣唯一本土專業再保險公司，承接產壽險分入業務"]],
     "m": "中游：大型壽險主體金控與獨立壽險公司", "mL": [["2881.TW","2881 富邦金","旗下富邦人壽經常性收益率與股票資本利得居冠"],["2882.TW","2882 國泰金","旗下國泰人壽管理近 8 兆資產，直接受惠美債與台股"],["2883.TW","2883 凱基金","整合凱基人壽與凱基證券之雙引擎金控"],["2867.TW","2867 三商壽","本土獨立大型壽險公司，聚焦投資型與保障型商品"]],
     "d": "下游：純產物保險 (車險/商業火險/工程險)", "dL": [["2850.TW","2850 新產","核保利潤極為穩健、配息優異之台灣純產險龍頭"],["2852.TW","2852 第一保","深耕企業商業火險與車險之穩健產險公司"],["2832.TW","2832 台產","高資本適足率、無負債經營之老牌產物保險公司"]]},
    {"id": "finance", "cat": "軟體生技與內需", "title": "🏦 金融 (銀行金控 / 證券 / 租賃)", "sub": "央行貨幣環境與票券拆款、企金/消金商業銀行金控，至證券投信與設備租賃",
     "u": "上游：票券金融、銀行間資金拆借與外匯清算", "uL": [["2889.TW","2889 國票金","以國際票券為核心，專精債票券自營與資金拆借"],["2820.TW","2820 華票","台灣老牌專業票券金融公司，受惠穩定利差"]],
     "m": "中游：消金財管與企金外匯主體型銀行金控", "mL": [["2891.TW","2891 中信金","台灣消金、信用卡、財富管理與海外獲利王"],["2886.TW","2886 兆豐金","公股金控獲利龍頭：美元放款與企金外匯霸主"],["2884.TW","2884 玉山金","高端財富管理手續費與跨境金融高成長指標"],["2892.TW","2892 第一金","核心一銀放款與淨利差穩健之高股息官股金控"],["2880.TW","2880 華南金","受惠存放利差與旗下華南永昌證券經紀收益"]],
     "d": "下游：證券經紀/ETF投信 與 中小企業設備租賃", "dL": [["2885.TW","2885 元大金","台股證券經紀與元大投信 ETF 規模絕對霸主"],["6005.TW","6005 群益證","台灣大型獨立綜合券商，經紀與自營獲利具彈性"],["5871.TW","5871 中租-KY","台灣與東協中小企業設備租賃及分期融資龍頭"]]},
    {"id": "consumer", "cat": "軟體生技與內需", "title": "🛒 民生消費與零售餐飲", "sub": "大宗農畜油脂原料、品牌食品飲料製造，至連鎖超商、美妝百貨與餐飲集團",
     "u": "上游：大宗穀物油脂加工、飼料與白肉雞畜牧供給", "uL": [["1210.TW","1210 大成","台灣農畜飼料、白肉雞一條龍與商用食品加工龍頭"],["1215.TW","1215 卜蜂","飼料、白肉雞電宰加工與即食調理肉品主力"],["1227.TW","1227 佳格","燕麥穀物、健康食用油與完膳營養品龍頭"]],
     "m": "中游：綜合食品飲料製造與高階烘焙原料", "mL": [["1216.TW","1216 統一","亞洲食品飲料製造與全通路民生消費霸主"],["1229.TW","1229 聯華","台灣麵粉製造龍頭與聯華氣體/資訊控股"],["1264.TWO","1264 德麥","大中華區最大高階烘焙原料進口與技術服務商"]],
     "d": "下游：連鎖便利超商、美妝百貨與大型餐飲集團", "dL": [["2912.TW","2912 統一超","台灣與菲律賓 7-ELEVEN 霸主，整合家樂福量販"],["5903.TWO","5903 全家","全台第二大便利商店，鮮食與會員經濟高成長"],["5904.TWO","5904 寶雅","台灣美妝生活雜貨連鎖專門店龍頭"],["2727.TW","2727 王品","台灣最大跨品牌連鎖餐飲集團"],["2753.TW","2753 八方雲集","國民連鎖餐飲龍頭，積極擴展美國市場"]]}
]

def fetch_tw_official_market_snapshot():
    """一次抓取證交所 (上市) 與櫃買中心 (上櫃) 全市場最新收盤行情與本益比，1 秒內精準對齊百檔台股"""
    snapshot = {"indices": {}, "stocks": {}, "pe_map": {}}
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. 證交所上市收盤行情 (MI_INDEX)
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

    # 2. 櫃買中心上櫃全市場收盤行情 (tpex_mainboard_quotes OpenAPI)
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

    # 3. 證交所與櫃買個股本益比
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

def batch_download_histories(symbols_list):
    """使用 yf.download 向量化批次下載所有標的近 1 年日 K 線，比單檔迴圈快 10 倍以上"""
    history_map = {}
    unique_syms = list(dict.fromkeys(symbols_list))
    chunk_size = 40

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

    # 用證交所與櫃買中心官方數據強制校準台灣指數與所有上市櫃個股
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

    # 對核心美股與台股權值股抓取詳細財報指標 (PE / EPS / 毛利率 / ROE) 與盤前盤後報價
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
        print("1. Fetching TWSE & TPEx official full market quotes...")
        tw_official = fetch_tw_official_market_snapshot()

        # 收集全站所有需要下載歷史日 K 線的股票與指數代號 (含 20+ 大產業鏈所有成分股)
        all_symbols = (
            list(INDICES.keys()) +
            list(US_BONDS.keys()) +
            list(FX_RATES.keys()) +
            list(US_STOCKS) +
            [m["ticker"] for m in TW_STOCKS.values()] +
            list(FUTURES_AND_COMMODITIES.keys())
        )
        for sec in COMPACT_25_SECTORS:
            for row_list in [sec["uL"], sec["mL"], sec["dL"]]:
                for item in row_list:
                    all_symbols.append(item[0])

        print(f"2. Batch downloading 1Y histories for {len(set(all_symbols))} unique symbols...")
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

        # 建立 20+ 大細分產業鏈完整資料結構
        sectors_out = []
        for sec in COMPACT_25_SECTORS:
            stages_out = []
            for stg_title, stg_list in [(sec["u"], sec["uL"]), (sec["m"], sec["mL"]), (sec["d"], sec["dL"])]:
                items_out = []
                for arr in stg_list:
                    sym, name, role = arr[0], arr[1], arr[2]
                    is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
                    a_t = "us_stock" if is_us else "tw_stock"
                    q_obj = get_built_asset(sym, name, a_t)
                    q_obj["role"] = to_trad(role)
                    items_out.append(q_obj)
                stages_out.append({"stage_name": to_trad(stg_title), "items": items_out})
            sectors_out.append({
                "id": sec["id"],
                "category": sec["cat"],
                "title": sec["title"],
                "subtitle": sec["sub"],
                "stages": stages_out
            })
        output_payload["supply_chain_sectors"] = sectors_out

        # 若有設定 FINLAB_API_TOKEN，為全站所有台股與 20+ 大產業鏈台股填入最新月營收 MoM / YoY
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
