// supply_chain_db.js — 20 大核心細分產業上、中、下游完整串接資料庫
window.FULL_SUPPLY_CHAIN_SECTORS = [
  {
    id: "memory",
    category: "半導體與AI硬體",
    title: "💾 記憶體 (HBM / DDR5 / NAND)",
    subtitle: "從高頻寬記憶體 HBM3e/HBM4、晶圓製造、控制 IC 到模組封測完整串接",
    stages: [
      {
        stage_name: "上游：IP 介面 / 記憶體控制晶片 / 晶圓設備",
        items: [
          { symbol: "6531.TW", name: "6531 愛普*", role: "VHM 3D 異質整合高頻寬記憶體 IP" },
          { symbol: "8299.TWO", name: "8299 群聯", role: "PCIe Gen5 SSD 控制晶片與企業級 aiDAPTIV+" },
          { symbol: "3260.TWO", name: "3260 威剛", role: "高階電競與工控記憶體控制與模組研發" }
        ]
      },
      {
        stage_name: "中游：DRAM / Flash 顆粒晶圓製造與國際原廠",
        items: [
          { symbol: "MU", name: "MU", role: "美光：HBM3e 與高階 DDR5 美股記憶體指標" },
          { symbol: "2408.TW", name: "2408 南亞科", role: "台灣 DRAM 顆粒製造龍頭 (切入 DDR5 與 AI 邊緣應用)" },
          { symbol: "2344.TW", name: "2344 華邦電", role: "利基型 DRAM、NOR Flash 與 CUBE 客製化高頻寬記憶體" },
          { symbol: "2337.TW", name: "2337 旺宏", role: "車用與工控高品質 NOR Flash 與 ROM 製造" }
        ]
      },
      {
        stage_name: "下游：伺服器記憶體模組與專業封測",
        items: [
          { symbol: "6239.TW", name: "6239 力成", role: "全球記憶體封測龍頭 (HBM 與邏輯晶片先進封裝)" },
          { symbol: "4967.TW", name: "4967 十銓", role: "高頻 DDR5 電競與 AI 工作站記憶體模組" },
          { symbol: "8271.TWO", name: "8271 宇瞻", role: "工控與垂直應用伺服器 SSD/DRAM 模組" }
        ]
      }
    ]
  },
  {
    id: "tgv_cowos",
    category: "半導體與AI硬體",
    title: "🔬 TGV 玻璃基板 & CoWoS 先進封裝",
    subtitle: "涵蓋玻璃核心基板 (TGV) 雷射改質、濕蝕刻、CoWoS 設備與 2.5D/3D 封裝",
    stages: [
      {
        stage_name: "上游：TGV 玻璃基板材料 / 鑽石碟 / 光罩盒",
        items: [
          { symbol: "GLW", name: "GLW", role: "康寧：TGV 高純度半導體玻璃基板晶圓母材" },
          { symbol: "1560.TW", name: "1560 中砂", role: "先進製程 CMP 鑽石碟與再生晶圓" },
          { symbol: "3680.TWO", name: "3680 家登", role: "EUV 光罩盒與先進封裝パネル載具" }
        ]
      },
      {
        stage_name: "中游：TGV 雷射穿孔 / 濕製程 / 點膠壓膜設備",
        items: [
          { symbol: "3131.TWO", name: "3131 弘塑", role: "CoWoS 單晶圓濕製程與 TGV 化學品/蝕刻設備" },
          { symbol: "3583.TW", name: "3583 辛耘", role: "CoWoS 自製濕製程設備與代理雷射設備" },
          { symbol: "6187.TWO", name: "6187 萬潤", role: "CoWoS 自動點膠、散熱貼合與 AOI 檢測設備" },
          { symbol: "2467.TW", name: "2467 志聖", role: "G2C+ 聯盟：TGV 玻璃基板貼膜與烘烤設備" },
          { symbol: "6640.TWO", name: "6640 均華", role: "G2C+ 聯盟：先進封裝高精度黏晶機與揀晶機" }
        ]
      },
      {
        stage_name: "下游：晶圓級先進封裝製造與 AI 晶片客戶",
        items: [
          { symbol: "2330.TW", name: "2330 台積電", role: "CoWoS-L / SoIC 先進封裝全球霸主" },
          { symbol: "NVDA", name: "NVDA", role: "Blackwell / Rubin 世代最大先進封裝客戶" }
        ]
      }
    ]
  },
  {
    id: "silicon_wafer",
    category: "半導體與AI硬體",
    title: "💿 矽晶圓 (Silicon Wafer)",
    subtitle: "從高純度多晶矽、矽晶棒長晶、12 吋拋光與磊晶矽晶圓到再生晶圓",
    stages: [
      {
        stage_name: "上游：高純度多晶矽原料與精密石英耗材",
        items: [
          { symbol: "6532.TWO", name: "6532 瑞耘", role: "半導體晶圓夾持環 (CMP 耗材) 與腔體零組件" },
          { symbol: "3413.TW", name: "3413 京鼎", role: "鴻海集團半導體前段蝕刻與薄膜設備模組" }
        ]
      },
      {
        stage_name: "中游：8 吋 / 12 吋拋光矽晶圓與磊晶矽晶圓",
        items: [
          { symbol: "6488.TWO", name: "6488 環球晶", role: "全球第三大 12 吋半導體矽晶圓與化合物晶圓龍頭" },
          { symbol: "3532.TW", name: "3532 台勝科", role: "台塑與日本 SUMCO 合資之 12 吋高階記憶體與邏輯矽晶圓" },
          { symbol: "6182.TWO", name: "6182 合晶", role: "8 吋與 12 吋重摻矽晶圓及車用功率磊晶晶圓" }
        ]
      },
      {
        stage_name: "下游：擋控片、再生晶圓與晶圓代工應用",
        items: [
          { symbol: "8028.TW", name: "8028 昇陽半導體", role: "全球最大 12 吋先進製程再生晶圓與晶圓薄化廠" },
          { symbol: "1560.TW", name: "1560 中砂", role: "3奈米/2奈米高階測試與再生晶圓供應商" }
        ]
      }
    ]
  },
  {
    id: "cpo_optical",
    category: "光通訊與網路",
    title: "💡 光通訊 & CPO 共同封裝光學",
    subtitle: "從磷化銦 CW 雷射磊晶、In4 光學檢測、FAU 光纖陣列到 800G/1.6T 光模組",
    stages: [
      {
        stage_name: "上游：CW 雷射磊晶 / 光電晶片 / 光學量測",
        items: [
          { symbol: "3081.TWO", name: "3081 聯亞", role: "800G/1.6T 矽光子 CW 連續波雷射磊晶主力" },
          { symbol: "2360.TW", name: "2360 致茂", role: "CPO 光學引擎 (OE) 晶圓級量測與系統級測試設備" },
          { symbol: "6442.TW", name: "6442 光聖", role: "美系 CSP 資料中心高芯數光纖光棒與主動元件" }
        ]
      },
      {
        stage_name: "中游：FAU 光纖陣列 / COUPE 封裝 / 光收發模組",
        items: [
          { symbol: "3363.TWO", name: "3363 上詮", role: "台積電矽光子聯盟：保偏光纖陣列 (FAU) 獨家技術" },
          { symbol: "3163.TWO", name: "3163 波若威", role: "CPO 分光器、光纖跳接線與 WDM 光學次模組" },
          { symbol: "3450.TW", name: "3450 聯鈞", role: "EML 雷射封裝與美系雲端大廠 AOC 主動光纜代工" },
          { symbol: "4979.TWO", name: "4979 華星光", role: "Marvell 體系 400G/800G 光收發模組主力廠" },
          { symbol: "6451.TW", name: "6451 訊芯-KY", role: "博通體系 51.2T CPO 光電共同封裝模組廠" }
        ]
      },
      {
        stage_name: "下游：高速網路交換器晶片與雲端客戶",
        items: [
          { symbol: "AVGO", name: "AVGO", role: "博通：全球交換器 ASIC 與 CPO 技術定義者" },
          { symbol: "MRVL", name: "MRVL", role: "邁威爾：光通訊 PAM4 DSP 晶片全球霸主" },
          { symbol: "2345.TW", name: "2345 智邦", role: "全球白牌 800G 資料中心高速交換器製造龍頭" }
        ]
      }
    ]
  },
  {
    id: "fiberglass_ccl_pcb_abf",
    category: "PCB與載板材料",
    title: "📡 玻纖布 ➔ CCL 銅箔基板 ➔ PCB & ABF 載板",
    subtitle: "完整串接上游 Low-Dk/Q-glass 石英布與 HVLP 銅箔、中游 M7/M8 CCL、至下游 ABF 載板與 OAM 板",
    stages: [
      {
        stage_name: "上游：玻纖布 (Low-Dk / Q-Glass) / HVLP 銅箔 / 樹脂",
        items: [
          { symbol: "1802.TW", name: "1802 台玻", role: "全球少數具備 Low-Dk 與超扁平電子級玻纖布大廠" },
          { symbol: "1815.TWO", name: "1815 富喬", role: "垂直整合玻纖紗與 Low-Dk 高頻玻纖布主力" },
          { symbol: "5340.TWO", name: "5340 建榮", role: "日東紡 (Nittobo) 集團旗下高階 NE-Glass/T-Glass 玻纖布廠" },
          { symbol: "8358.TWO", name: "8358 金居", role: "AI 伺服器 RG312 / HVLP 超低粗糙度高頻銅箔" },
          { symbol: "1303.TW", name: "1303 南亞", role: "高頻電子材料、PPE 改質樹脂與銅箔基板全系列整合" }
        ]
      },
      {
        stage_name: "中游：M7 / M8 高頻高速銅箔基板 (CCL)",
        items: [
          { symbol: "2383.TW", name: "2383 台光電", role: "M7/M8 高階無鹵素銅箔基板全球市占第一" },
          { symbol: "6274.TWO", name: "6274 台燿", role: "800G 交換器與 AI ASIC 高速低損耗 CCL 主力" },
          { symbol: "6213.TW", name: "6213 聯茂", role: "AI 伺服器主板與車用高頻高速銅箔基板" }
        ]
      },
      {
        stage_name: "下游：ABF 載板 (BT/ABF) 與 AI 高層數 PCB 主板",
        items: [
          { symbol: "3037.TW", name: "3037 欣興", role: "AI GPU 高層數大面積 ABF 載板與 HDI 光模組板龍頭" },
          { symbol: "8046.TW", name: "8046 南電", role: "網通交換器晶片與高階 CPU 用 ABF/BT 載板大廠" },
          { symbol: "3189.TW", name: "3189 景碩", role: "AI 显卡、記憶體與手機應用之 ABF/BT 載板主力" },
          { symbol: "2368.TW", name: "2368 金像電", role: "AI 伺服器 UBB/OAM 與雲端 800G 交換器多層 PCB 霸主" }
        ]
      }
    ]
  },
  {
    id: "passive_components",
    category: "電子零組件",
    title: "🔋 被動元件 (MLCC / 一體成型電感 / 電阻)",
    subtitle: "從高純度陶瓷粉末、電極漿料、高容值車規/AI 伺服器 MLCC 到通路應用",
    stages: [
      {
        stage_name: "上游：介電陶瓷粉末 / 導電漿料 / 氧化鋁基板",
        items: [
          { symbol: "6173.TWO", name: "6173 信昌電", role: "華新科集團：高階 MLCC 介電陶瓷粉末與晶片電容原料" },
          { symbol: "3624.TWO", name: "3624 光頡", role: "精密薄膜電阻與高頻電感上游材料技術" },
          { symbol: "8043.TWO", name: "8043 蜜望實", role: "太陽誘電高階 MLCC 代理與上游原料配套" }
        ]
      },
      {
        stage_name: "中游：高容值 MLCC / 晶片電阻 / 一體成型功率電感",
        items: [
          { symbol: "2327.TW", name: "2327 國巨", role: "全球晶片電阻第一、鉭質電容第一、高階車用與 AI MLCC 巨頭" },
          { symbol: "2492.TW", name: "2492 華新科", role: "全球前五大 MLCC 與晶片電阻製造大廠" },
          { symbol: "6449.TW", name: "6449 鈺邦", role: "全球前兩大捲繞式與晶片型固態電容 (V-Chip) 龍頭，供應 AI 主板" },
          { symbol: "6284.TWO", name: "6284 佳邦", role: "AI PC 與高功率伺服器用一體成型電感 (Molding Choke) 主力" }
        ]
      },
      {
        stage_name: "下游：AI 伺服器電源管理與主機板系統整合",
        items: [
          { symbol: "2456.TW", name: "2456 奇力新/凱美", role: "國巨集團旗下鋁質電解電容與風扇馬達元件" },
          { symbol: "3090.TW", name: "3090 日電貿", role: "台灣最大被動元件高階伺服器與工業應用通路龍頭" }
        ]
      }
    ]
  },
  {
    id: "power_semiconductors",
    category: "電子零組件",
    title: "⚡ 功率元件 (SiC / GaN / MOSFET / IGBT)",
    subtitle: "從第三代半導體基板磊晶、晶圓代工、高壓 MOSFET 設計到 AI 高瓦數電源",
    stages: [
      {
        stage_name: "上游：SiC 碳化矽基板 / GaN 磊晶 / 導線架",
        items: [
          { symbol: "6488.TWO", name: "6488 環球晶", role: "8吋 SiC 碳化矽基板與 GaN-on-Si 磊晶晶圓" },
          { symbol: "3016.TW", name: "3016 嘉晶", role: "矽磊晶與 SiC/GaN 化合物半導體磊晶量產廠" },
          { symbol: "2351.TW", name: "2351 順德", role: "全球前三大高功率車用與工業用導線架龍頭" }
        ]
      },
      {
        stage_name: "中游：功率晶圓代工 & MOSFET / 二極體設計封裝",
        items: [
          { symbol: "3707.TWO", name: "3707 漢磊", role: "SiC 與 GaN 化合物功率半導體專業晶圓代工" },
          { symbol: "5347.TWO", name: "5347 世界先進", role: "8吋 PMIC 電源管理 IC 與 GaN 功率元件代工龍頭" },
          { symbol: "2481.TW", name: "2481 強茂", role: "車用 MOSFET、SiC 二極體與高壓功率元件大廠" },
          { symbol: "3675.TWO", name: "3675 德微", role: "達爾集團旗下車規與 AI 伺服器保護元件及 SiC 封測" },
          { symbol: "8261.TW", name: "8261 富鼎", role: "鴻海集團旗下高低壓 MOSFET 與 IGBT 功率IC設計" }
        ]
      },
      {
        stage_name: "下游：國際 IDM 功率巨頭與高壓伺服器電源",
        items: [
          { symbol: "ON", name: "ON", role: "安森美：全球車用與 AI 資料中心功率模組指標" },
          { symbol: "MPWR", name: "MPWR", role: "芯源系統 (Monolithic Power)：AI GPU 垂直供電 PMIC 霸主" }
        ]
      }
    ]
  },
  {
    id: "thermal_cooling",
    category: "AI伺服器基建",
    title: "❄️ 散熱模組 (水冷板 Cold Plate / CDU / 快接頭)",
    subtitle: "涵蓋快接頭 (UQD)、冷卻液分配裝置 (CDU)、3D VC、水冷板到浸沒式散熱機櫃",
    stages: [
      {
        stage_name: "上游：水冷快接頭 (UQD) / 散熱風扇馬達 / 泵浦閥件",
        items: [
          { symbol: "6805.TW", name: "6805 富世達", role: "切入 AI 伺服器水冷轉接頭、滑軌與浮動快接頭模組" },
          { symbol: "2059.TW", name: "2059 川湖", role: "AI 水冷機櫃高承重導軌與快接頭機構件配套" },
          { symbol: "2421.TW", name: "2421 建準", role: "AI 伺服器高轉速對轉散熱風扇與水冷散熱排風扇" }
        ]
      },
      {
        stage_name: "中游：水冷板 (Cold Plate) / 分歧管 (Manifold) / CDU",
        items: [
          { symbol: "3017.TW", name: "3017 奇鋐", role: "CSP 雲端巨頭 3D VC、水冷板與分歧管最大供應商" },
          { symbol: "3324.TWO", name: "3324 雙鴻", role: "水冷板、CDU 冷卻液分配裝置與分歧管自製率龍頭" },
          { symbol: "2486.TW", name: "2486 一詮", role: "高階半導體均熱片 (Heat Spreader) 與金屬散熱蓋板" },
          { symbol: "6230.TW", name: "6230 尼得科超眾", role: "日本 Nidec 集團旗下 AI 水冷 CDU 與機櫃散熱模組" }
        ]
      },
      {
        stage_name: "下游：L11/L12 水冷機櫃系統整合與資料中心基建",
        items: [
          { symbol: "VRT", name: "VRT", role: "Vertiv：全球資料中心液冷與電力基礎設施龍頭" },
          { symbol: "8210.TW", name: "8210 勤誠", role: "AI 伺服器高密度水冷機殼與機櫃機構整合龍頭" }
        ]
      }
    ]
  },
  {
    id: "bbu_power",
    category: "AI伺服器基建",
    title: "🔋 BBU 備援電池單元 & AI 伺服器高壓電源",
    subtitle: "GB200/GB300 標配之鋰電池芯、BMS 電池管理、BBU 模組到 5.5kW+ 高壓 PSU",
    stages: [
      {
        stage_name: "上游：高倍率鋰電池芯 / 電池正負極材料 / 電源管理 IC",
        items: [
          { symbol: "4739.TW", name: "4739 康普", role: "動力與儲能鋰電池正極材料硫酸鎳、硫酸鈷主力" },
          { symbol: "4721.TWO", name: "4721 美琪瑪", role: "鋰電池正極材料與高純度電池化學品" },
          { symbol: "5269.TW", name: "5269 祥碩", role: "高速傳輸與伺服器周邊控制晶片" }
        ]
      },
      {
        stage_name: "中游：AI 伺服器 BBU 備援電池模組製造",
        items: [
          { symbol: "6781.TW", name: "6781 AES-KY", role: "全球 CSP 資料中心 BBU 備援電池模組市占第一龍頭" },
          { symbol: "3211.TWO", name: "3211 順達", role: "轉型高毛利資料中心 BBU 與儲能電池模組主力" },
          { symbol: "6121.TWO", name: "6121 新普", role: "全球最大筆電電池集團，透過子公司 AES-KY 掌握 BBU 龍頭地位" },
          { symbol: "4931.TWO", name: "4931 新盛力", role: "專攻資料中心 BBU、UPS 與輕型電動載具鋰電池模組" },
          { symbol: "6558.TW", name: "6558 興能高", role: "小型化客製鋰電池與儲能管理系統研發" }
        ]
      },
      {
        stage_name: "下游：AI 機櫃 Power Shelf 電源供應器整合",
        items: [
          { symbol: "2308.TW", name: "2308 台達電", role: "全球 AI 伺服器 Power Shelf、BBU 與 DC-DC 電源霸主" },
          { symbol: "2301.TW", name: "2301 光寶科", role: "雲端資料中心 33kW+ Power Shelf 與 BBU 整合供應商" }
        ]
      }
    ]
  },
  {
    id: "cpu_semiconductor",
    category: "半導體與AI硬體",
    title: "🧠 CPU / AI ASIC / 半導體核心製程",
    subtitle: "從 EDA 矽智財 IP、IC 設計 (CPU/GPU/ASIC) 到先進晶圓代工",
    stages: [
      {
        stage_name: "上游：EDA 電子設計自動化 & Silicon IP 矽智財",
        items: [
          { symbol: "ARM", name: "ARM", role: "全球行動與資料中心低功耗 CPU 架構 IP 霸主" },
          { symbol: "3661.TW", name: "3661 世芯-KY", role: "美系 CSP 雲端巨頭 AI ASIC 客製化晶片設計服務龍頭" },
          { symbol: "3443.TW", name: "3443 創意", role: "台積電旗下高階 AI ASIC、HBM 介面 IP 與先進封裝設計" },
          { symbol: "3529.TWO", name: "3529 力旺", role: "全球嵌入式非揮發性記憶體 (eNVM) 與 PUF 資安 IP 龍頭" },
          { symbol: "6643.TWO", name: "6643 M31", role: "高速傳輸介面 (PCIe/USB/MIPI) 與基礎元件矽智財" }
        ]
      },
      {
        stage_name: "中游：CPU / GPU / 旗艦 SoC 晶片設計",
        items: [
          { symbol: "NVDA", name: "NVDA", role: "Grace CPU + Blackwell GPU 超級晶片全球霸主" },
          { symbol: "AMD", name: "AMD", role: "EPYC 伺服器 CPU 與 Instinct AI GPU 雙成長引擎" },
          { symbol: "INTC", name: "INTC", role: "x86 PC 與 Xeon 伺服器 CPU 大廠" },
          { symbol: "2454.TW", name: "2454 聯發科", role: "天璣旗艦 SoC、WoA 筆電 CPU 與資料中心 SerDes ASIC" },
          { symbol: "2379.TW", name: "2379 瑞昱", role: "高速乙太網通晶片、Wi-Fi 7 與車用交換器 IC 龍頭" }
        ]
      },
      {
        stage_name: "下游：先進與成熟製程晶圓代工製造",
        items: [
          { symbol: "2330.TW", name: "2330 台積電", role: "全球 3奈米 / 2奈米 CPU 與 AI 晶片獨家代工基地" },
          { symbol: "2303.TW", name: "2303 聯電", role: "22/28奈米特殊製程、OLED 驅動 IC 與矽光子中介層代工" }
        ]
      }
    ]
  },
  {
    id: "osat_testing",
    category: "半導體與AI硬體",
    title: "🔍 封測 (OSAT / 晶圓針測 / 測試座 / 老化測試)",
    subtitle: "從高頻探針卡、測試座 (Socket)、ATE 測試機台到晶圓凸塊與系統級封測",
    stages: [
      {
        stage_name: "上游：高頻探針卡 (Probe Card) / 測試座 (Socket) / 導線架",
        items: [
          { symbol: "6223.TWO", name: "6223 旺矽", role: "全球前五大探針卡廠，壟斷多數 AI ASIC 與 GPU 垂直探針卡" },
          { symbol: "6515.TW", name: "6515 穎崴", role: "高階同軸測試座 (Coaxial Socket) 與 SLT 系統級測試座龍頭" },
          { symbol: "6510.TWO", name: "6510 精測", role: "高速 PCB 晶圓測試板與 MEMS 探針卡" },
          { symbol: "6217.TWO", name: "6217 中探針", role: "大電流測試探針與高功率老化測試針" }
        ]
      },
      {
        stage_name: "中游：專業晶圓測試、最終測試 (FT) 與系統級封測 (OSAT)",
        items: [
          { symbol: "3711.TW", name: "3711 日月光投控", role: "全球第一大封測廠 (FOCoS 先進封裝與 VIPack 平台)" },
          { symbol: "2449.TW", name: "2449 京元電子", role: "輝達與國際 AI 晶片最大專業晶圓測試與成品測試 (FT) 基地" },
          { symbol: "6257.TW", name: "6257 矽格", role: "網通、AI 手機 SoC 與高速傳輸晶片封測主力" },
          { symbol: "3265.TWO", name: "3265 台星科", role: "矽光子 CPO 封測合作與美系 AI/HPC 晶圓級凸塊封裝" }
        ]
      },
      {
        stage_name: "下游：測試分類機 (Handler) 與 SLT 系統檢測設備",
        items: [
          { symbol: "2360.TW", name: "2360 致茂", role: "AI GPU SLT 系統級測試機台與溫控老化測試設備龍頭" },
          { symbol: "6438.TW", name: "6438 迅得", role: "半導體先進封測廠 AMHS 自動化搬運與倉儲系統" }
        ]
      }
    ]
  },
  {
    id: "leo_satellite_space_defense",
    category: "太空軍工與航運",
    title: "🛰️ 低軌衛星 & 太空科技 & 軍工國防",
    subtitle: "從航太高階合金鍛造、衛星高頻微波元件、地面接收站到無人機與造艦國防",
    stages: [
      {
        stage_name: "上游：航太特殊合金 / 衛星高頻 PCB / 相位陣列天線晶片",
        items: [
          { symbol: "5009.TWO", name: "5009 榮剛", role: "航太、能源與國防等級特殊合金鋼全球合格供應商" },
          { symbol: "2313.TW", name: "2313 華通", role: "全球低軌衛星 (天上衛星板+地面接收板) HDI PCB 第一大供應商" },
          { symbol: "2367.TW", name: "2367 耀華", role: "低軌衛星高頻地面接收板與車用雷達硬軟結合板" },
          { symbol: "3105.TWO", name: "3105 穩懋", role: "全球最大砷化鎵晶圓代工廠 (衛星高頻 PA 功率放大器)" }
        ]
      },
      {
        stage_name: "中游：衛星高頻微波收發模組 / 航太發動機零組件",
        items: [
          { symbol: "3491.TWO", name: "3491 昇達科", role: "Starlink 與 Kuiper 低軌衛星高頻毫米波中空波導元件龍頭" },
          { symbol: "6285.TW", name: "6285 啟碁", role: "美系低軌衛星家用地面接收路由器與車用網通主力代工廠" },
          { symbol: "3004.TW", name: "3004 豐達科", role: "奇異與賽峰集團認證之航太發動機高強度扣件主力" },
          { symbol: "4541.TWO", name: "4541 晟田", role: "航太起落架、發動機機匣與半導體設備精密加工" },
          { symbol: "8222.TW", name: "8222 寶一", role: "航空發動機高溫燃燒段薄鈑金屬件" }
        ]
      },
      {
        stage_name: "下游：軍用高教機 / 無人機系統 / 國艦國造總成",
        items: [
          { symbol: "2634.TW", name: "2634 漢翔", role: "台灣航太與軍工龍頭：勇鷹高教機、F-16 維保與發動機機匣" },
          { symbol: "8033.TW", name: "8033 雷虎", role: "軍用商規長程無人機 (UAV) 與無人艇系統研發" },
          { symbol: "2645.TW", name: "2645 長榮航太", role: "全球前十大飛機維修廠與軍用機體製造、無人機組裝" },
          { symbol: "2608.TW", name: "2608 台船/龍德", role: "國艦國造、海巡艦艇與潛艦防衛工程" }
        ]
      }
    ]
  },
  {
    id: "shipping_aviation",
    category: "太空軍工與航運",
    title: "🚢 航運 (貨櫃航運 / 散裝航運 / 航空貨運與承攬)",
    subtitle: "從造船與港埠貨櫃集散、全球遠洋貨櫃與散裝船隊到國際物流承攬",
    stages: [
      {
        stage_name: "上游：造船修船 / 內陸貨櫃集散倉儲 / 碼頭裝卸",
        items: [
          { symbol: "2607.TW", name: "2607 榮運", role: "長榮集團旗下大型內陸貨櫃集散場、造櫃與船隊租賃" },
          { symbol: "2613.TW", name: "2613 中櫃", role: "基隆、台中與高雄港碼頭貨櫃裝卸與保稅倉儲" }
        ]
      },
      {
        stage_name: "中游：遠洋與近洋貨櫃航運 / 散裝船隊 / 航空客貨運",
        items: [
          { symbol: "2603.TW", name: "2603 長榮", role: "台灣貨櫃航運龍頭：歐美遠洋線高比重與環保新船隊優勢" },
          { symbol: "2609.TW", name: "2609 陽明", role: "全球前十大貨櫃航商：深耕歐美與亞洲主力航線" },
          { symbol: "2615.TW", name: "2615 萬海", role: "亞洲近洋線霸主並擴展美西遠洋高毛利航線" },
          { symbol: "2606.TW", name: "2606 裕民", role: "遠東集團旗下台灣最大海岬型 (Capesize) 散裝航運龍頭" },
          { symbol: "2637.TW", name: "2637 慧洋-KY", role: "台灣船隊規模最大之巴拿馬型與輕便型散裝船東" },
          { symbol: "2618.TW", name: "2618 長榮航", role: "客運與 AI 伺服器高價空運包機雙引擎" },
          { symbol: "2610.TW", name: "2610 華航", role: "全球前段班全貨機機隊，直接受惠 AI 伺服器與電商空運需求" }
        ]
      },
      {
        stage_name: "下游：海空運承攬物流與跨境供應鏈管理",
        items: [
          { symbol: "2636.TW", name: "2636 台驊投控", role: "海空鐵全方位國際物流承攬與供應鏈倉儲" },
          { symbol: "5609.TWO", name: "5609 中菲行", role: "深耕東南亞、印度與美歐科技業空海運物流承攬大廠" }
        ]
      }
    ]
  },
  {
    id: "cybersecurity",
    category: "軟體資安與生技",
    title: "🛡️ 資安與雲端軟體服務",
    subtitle: "從硬體密碼安全晶片、網路防火牆設備到 SOC 託管資安監控與雲端服務",
    stages: [
      {
        stage_name: "上游：硬體信任根 (PUF) 資安 IP / 工控網安硬體平台",
        items: [
          { symbol: "3529.TWO", name: "3529 力旺", role: "NeoPUF 晶片級硬體資安矽智財，防範量子與側信道攻擊" },
          { symbol: "6245.TWO", name: "6245 立端", role: "全球電信級網路安全硬體平台 (UTM/SD-WAN) 代工龍頭" },
          { symbol: "3088.TWO", name: "3088 艾訊", role: "工業自動化與網通資安硬體平台" }
        ]
      },
      {
        stage_name: "中游：零信任資安軟體 / AI 威脅偵測 / 國際資安巨頭",
        items: [
          { symbol: "PANW", name: "PANW", role: "Palo Alto Networks：全球次世代防火牆與 AI 資安平台霸主" },
          { symbol: "CRWD", name: "CRWD", role: "CrowdStrike：全球雲端原生端點安全 (EDR/XDR) 龍頭" },
          { symbol: "6690.TWO", name: "6690 安碁資訊", role: "宏碁集團旗下台灣最大 SOC 資安威脅監控中心" },
          { symbol: "6561.TWO", name: "6561 是方", role: "中華電信旗下 IDC 機房中心與雲端交換網路資安服務" }
        ]
      },
      {
        stage_name: "下游：金融與政府資安系統整合 / 多雲託管服務",
        items: [
          { symbol: "2453.TW", name: "2453 凌群", role: "金融證券交易系統、政府公部門與 AI 資安系統整合" },
          { symbol: "3029.TW", name: "3029 零壹", role: "台灣最大企業級 IT 基礎架構與資安軟體代理整合商" },
          { symbol: "6689.TW", name: "6689 伊雲谷", role: "AWS 等跨國公有雲託管與雲端資安合規顧問龍頭" }
        ]
      }
    ]
  },
  {
    id: "biotech_medical",
    category: "軟體資安與生技",
    title: "🧬 生技醫療 (新藥研發 / CDMO / 高階醫材 / 通路)",
    subtitle: "從新藥臨床授權、原料藥與生物藥 CDMO 代工，到高階醫療器材與連鎖藥局",
    stages: [
      {
        stage_name: "上游：新藥研發授權 / 特色原料藥 (API) / 基因檢測",
        items: [
          { symbol: "6446.TW", name: "6446 藥華藥", role: "罕見血癌新藥 Ropeg 全球多國藥證銷售與 ET 新適應症擴張" },
          { symbol: "1795.TW", name: "1795 美時", role: "高門檻癌症與中樞神經特殊學名藥外銷美歐日龍頭" },
          { symbol: "4105.TWO", name: "4105 東洋", role: "困難學名藥、微脂體製劑與重症抗感染藥物領導廠" }
        ]
      },
      {
        stage_name: "中游：生物藥 CDMO 委託開發代工 / 高階隱形眼鏡與醫材",
        items: [
          { symbol: "6472.TW", name: "6472 保瑞", role: "台灣最大跨國製藥集團：併購美國藥廠建構全球 CDMO 霸主" },
          { symbol: "6589.TW", name: "6589 台康生技", role: "生物相似藥開發與國際級大分子微生物/哺乳動物細胞 CDMO" },
          { symbol: "6491.TW", name: "6491 晶碩", role: "矽水膠隱形眼鏡高自動化製造與自有品牌外銷" },
          { symbol: "1707.TW", name: "1707 葡萄王", role: "益生菌與樟芝發酵保健品代工及多角化直銷通路" }
        ]
      },
      {
        stage_name: "下游：大型連鎖藥局通路與洗腎醫療服務",
        items: [
          { symbol: "6469.TW", name: "6469 大樹", role: "台灣第一大連鎖複合式醫藥保健藥局通路" },
          { symbol: "4175.TWO", name: "4175 杏一", role: "全台醫院型連鎖醫療用品與居家照護通路龍頭" },
          { symbol: "4104.TW", name: "4104 佳醫", role: "台灣洗腎血液透析中心營運與高階醫療設備代理龍頭" }
        ]
      }
    ]
  },
  {
    id: "finance_insurance",
    category: "金融保險與內需",
    title: "🏦 金融與保險 (壽險金控 / 商業銀行 / 產險 / 證券)",
    subtitle: "涵蓋資金拆借與再保、大型壽險型金控、企金消金銀行及產險證券服務",
    stages: [
      {
        stage_name: "上游：專業再保險 / 票券資金拆借 / 壽險雙雄金控",
        items: [
          { symbol: "2851.TW", name: "2851 中再保", role: "台灣唯一本土專業再保險公司，承接國內外產壽險分入業務" },
          { symbol: "2881.TW", name: "2881 富邦金", role: "金控獲利王：旗下富邦人壽、台北富邦銀行、富邦產險均居龍頭" },
          { symbol: "2882.TW", name: "2882 國泰金", role: "台灣資產規模最大金控：國泰人壽龐大美債與台股部位受惠資本市場" }
        ]
      },
      {
        stage_name: "中游：銀行主體型金控 (財富管理 / 外幣放款 / 信用卡)",
        items: [
          { symbol: "2891.TW", name: "2891 中信金", role: "消金、信用卡、財富管理與海外分支機構獲利龍頭" },
          { symbol: "2886.TW", name: "2886 兆豐金", role: "官股金控龍頭：企金外匯業務與美元利差收益指標" },
          { symbol: "2884.TW", name: "2884 玉山金", role: "高端財富管理手續費與跨境企業金融高成長代表" },
          { symbol: "2892.TW", name: "2892 第一金", role: "核心銀行淨利差穩健、高配息防禦型官股金控" }
        ]
      },
      {
        stage_name: "下游：純產物保險 / 證券經紀自營 / 租賃融資",
        items: [
          { symbol: "2885.TW", name: "2885 元大金", role: "台灣證券經紀與 ETF 投信霸主，直接受惠台股高成交量" },
          { symbol: "2850.TW", name: "2850 新產", role: "核保利潤穩健、車險與商業火險市占領先之純產險模範生" },
          { symbol: "5871.TW", name: "5871 中租-KY", role: "台灣與東協中小企業設備租賃與分期融資龍頭" }
        ]
      }
    ]
  },
  {
    id: "consumer_retail",
    category: "金融保險與內需",
    title: "🛒 民生消費與連鎖零售餐飲",
    subtitle: "從大宗農畜油脂原料、品牌食品製造，到超商量販、百貨電商與連鎖餐飲",
    stages: [
      {
        stage_name: "上游：大宗穀物油脂加工 / 飼料與白肉雞畜牧供給",
        items: [
          { symbol: "1210.TW", name: "1210 大成", role: "台灣農畜飼料、白肉雞一條龍與商用食品加工龍頭" },
          { symbol: "1215.TW", name: "1215 卜蜂", role: "泰國正大集團旗下台灣飼料、肉品加工與即食調理食品主力" },
          { symbol: "1227.TW", name: "1227 佳格", role: "燕麥穀物、健康食用油與成人營養補充品領導品牌" }
        ]
      },
      {
        stage_name: "中游：綜合食品飲料製造 / 烘焙與冷鏈物流",
        items: [
          { symbol: "1216.TW", name: "1216 統一", role: "亞洲食品與民生消費巨頭，整合製造、冷鏈與全通路生態系" },
          { symbol: "1229.TW", name: "1229 聯華", role: "台灣麵粉製造龍頭並轉型工業氣體與神通資訊科技控股" },
          { symbol: "1264.TWO", name: "1264 德麥", role: "大中華區最大高階烘焙原料進口與技術服務商" }
        ]
      },
      {
        stage_name: "下游：超商量販通路 / 連鎖餐飲集團 / 居家生活百貨",
        items: [
          { symbol: "2912.TW", name: "2912 統一超", role: "台灣與菲律賓 7-ELEVEN 超商霸主，整合物流與家樂福量販" },
          { symbol: "5903.TWO", name: "5903 全家", role: "全台第二大便利商店通路，鮮食與數位會員經濟高成長" },
          { symbol: "5904.TWO", name: "5904 寶雅", role: "台灣美妝生活雜貨與五金居家連鎖專門店龍頭" },
          { symbol: "2727.TW", name: "2727 王品", role: "台灣最大跨品牌連鎖餐飲集團 (涵蓋火鍋、燒肉、鐵板燒)" },
          { symbol: "2753.TW", name: "2753 八方雲集", role: "國民餐飲連鎖霸主，積極拓展美國加州與德州門市版圖" }
        ]
      }
    ]
  }
];
