import datetime
import json
import os
import requests
import yfinance as yf

# 強制統一「台」字並保護專有名詞
CHAR_REPLACEMENTS = {
    "臺": "台",
    "納斯達剋": "納斯達克",
    "小納斯達剋": "小納斯達克",
}


def sanitize_text(text):
  if not isinstance(text, str):
    return text
  for old, new in CHAR_REPLACEMENTS.items():
    text = text.replace(old, new)
  return text


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.twse.com.tw/",
}


def clean_num(val):
  if val is None:
    return 0.0
  s = (
      str(val)
      .replace(",", "")
      .replace(" ", "")
      .replace("+", "")
      .replace("%", "")
      .strip()
  )
  if s in ("", "-", "--", "N/A", "None"):
    return 0.0
  try:
    return float(s)
  except ValueError:
    return 0.0


def load_previous_json(filepath="data/market_data.json"):
  if os.path.exists(filepath):
    try:
      with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      pass
  return {}


def fetch_twse_institutional(max_lookback=14):
  history = []
  today = datetime.date.today()

  for i in range(max_lookback):
    target_date = today - datetime.timedelta(days=i)
    if target_date.weekday() >= 5:
      continue
    date_str = target_date.strftime("%Y%m%d")
    iso_date = target_date.strftime("%Y-%m-%d")
    url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={date_str}&response=json"

    try:
      res = requests.get(url, headers=HEADERS, timeout=10).json()
      if res.get("stat") == "OK" and res.get("data"):
        day_item = {
            "date": iso_date,
            "foreign": 0.0,
            "trust": 0.0,
            "dealer": 0.0,
            "total": 0.0,
        }
        dealer_parts = 0.0
        has_dealer_total = False

        for row in res["data"]:
          name = sanitize_text(str(row[0]).strip())
          diff_billion = round(clean_num(row[3]) / 1e8, 2)

          if "外資" in name and "自營商" not in name:
            day_item["foreign"] = diff_billion
          elif "投信" in name:
            day_item["trust"] = diff_billion
          elif "自營商" in name and "外資" not in name:
            if "合計" in name or name == "自營商":
              day_item["dealer"] = diff_billion
              has_dealer_total = True
            else:
              dealer_parts = round(dealer_parts + diff_billion, 2)
          elif "合計" in name or "總計" in name:
            day_item["total"] = diff_billion

        if not has_dealer_total:
          day_item["dealer"] = dealer_parts
        if day_item["total"] == 0.0:
          day_item["total"] = round(
              day_item["foreign"] + day_item["trust"] + day_item["dealer"], 2
          )

        if any(
            day_item[k] != 0.0 for k in ["foreign", "trust", "dealer", "total"]
        ):
          history.append(day_item)
    except Exception as e:
      print(f"[WARN] BFI82U 抓取失敗 ({date_str}): {e}")

  history.reverse()
  return history


def fetch_margin_history(max_lookback=20):
  twse_list = []
  tpex_list = []
  today = datetime.date.today()

  for i in range(max_lookback):
    target_date = today - datetime.timedelta(days=i)
    if target_date.weekday() >= 5:
      continue
    date_str = target_date.strftime("%Y%m%d")
    iso_date = target_date.strftime("%Y-%m-%d")
    roc_date = f"{target_date.year - 1911}/{target_date.strftime('%m/%d')}"

    # 上市融資餘額 (TWSE MI_MARGN)
    try:
      twse_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=MS&response=json"
      r_twse = requests.get(twse_url, headers=HEADERS, timeout=10).json()
      if r_twse.get("stat") == "OK" and r_twse.get("tables"):
        for tbl in r_twse["tables"]:
          for row in tbl.get("data", []):
            if "融資金額" in sanitize_text(str(row[0])):
              prev_val = clean_num(row[4])
              curr_val = clean_num(row[5])
              if curr_val > 0:
                twse_list.append({
                    "date": iso_date,
                    "balance": round(curr_val / 1e5, 2),
                    "change": round((curr_val - prev_val) / 1e5, 2),
                })
    except Exception as e:
      print(f"[WARN] TWSE MI_MARGN 失敗 ({date_str}): {e}")

    # 櫃買融資餘額 (TPEx 雙通道)
    tpex_ok = False
    try:
      r_tpex = requests.post(
          "https://www.tpex.org.tw/www/zh-tw/margin/balance",
          data={"date": target_date.strftime("%Y/%m/%d"), "response": "json"},
          headers=HEADERS,
          timeout=10,
      ).json()
      tables = r_tpex.get("tables", [])
      if tables and tables[0].get("totalCount", 0) > 0:
        rows = tables[0].get("summary", []) or tables[0].get("data", [])
        for s_row in reversed(rows):
          nums = [clean_num(c) for c in s_row if clean_num(c) > 10000000]
          if len(nums) >= 2:
            prev_v, curr_v = nums[0], nums[-1]
            tpex_list.append({
                "date": iso_date,
                "balance": round(curr_v / 1e5, 2),
                "change": round((curr_v - prev_v) / 1e5, 2),
            })
            tpex_ok = True
            break
    except Exception:
      pass

    if not tpex_ok:
      try:
        tpex_old = f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&d={roc_date}&o=json"
        r_old = requests.get(tpex_old, headers=HEADERS, timeout=10).json()
        rows = r_old.get("aaData") or []
        if rows:
          last_row = rows[-1]
          prev_v, curr_v = clean_num(last_row[1]), clean_num(last_row[5])
          if curr_v > 1000000:
            tpex_list.append({
                "date": iso_date,
                "balance": round(curr_v / 1e5, 2),
                "change": round((curr_v - prev_v) / 1e5, 2),
            })
      except Exception as e:
        print(f"[WARN] TPEx 失敗 ({roc_date}): {e}")

  twse_list.reverse()
  tpex_list.reverse()
  return twse_list, tpex_list


ALL_SYMBOLS = [
    "^GSPC",
    "^DJI",
    "^IXIC",
    "^SOX",
    "^TWII",
    "^TWOII",
    "^N225",
    "^KS11",
    "^GDAXI",
    "^FTSE",
    "^FCHI",
    "ES=F",
    "NQ=F",
    "YM=F",
    "GC=F",
    "SI=F",
    "HG=F",
    "PA=F",
    "BZ=F",
    "CL=F",
    "ZS=F",
    "ZW=F",
    "ZC=F",
    "NVDA",
    "TSM",
    "AMD",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "AMZN",
    "AAPL",
    "MSFT",
    "2330.TW",
    "2454.TW",
    "2317.TW",
    "2308.TW",
    "3711.TW",
    "TWD=X",
    "JPY=X",
    "CNY=X",
    "EURUSD=X",
    "GBPUSD=X",
    "DX-Y.NYB",
    "^TNX",
    "^TYX",
]


def fetch_yf_quote(symbol):
  try:
    t = yf.Ticker(symbol)
    hist = t.history(period="6mo")
    if hist.empty:
      return None
    close = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else close
    chg = close - prev
    pct = (chg / prev * 100) if prev != 0 else 0.0
    series = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(float(val), 2)}
        for idx, val in hist["Close"].items()
    ]
    return {
        "symbol": symbol,
        "price": round(close, 2),
        "change": round(chg, 2),
        "change_pct": round(pct, 2),
        "history": series[-120:],
    }
  except Exception:
    return None


def main():
  os.makedirs("data", exist_ok=True)
  old_data = load_previous_json("data/market_data.json")

  inst_history = fetch_twse_institutional(max_lookback=14) or old_data.get(
      "institutional_history", []
  )
  twse_margin, tpex_margin = fetch_margin_history(max_lookback=20)
  if not twse_margin:
    twse_margin = old_data.get(
        "twse_margin",
        [{"date": "2026-11-13", "balance": 3248.65, "change": -18.42}],
    )
  if not tpex_margin:
    tpex_margin = old_data.get(
        "tpex_margin",
        [{"date": "2026-11-13", "balance": 1142.38, "change": -6.85}],
    )
  if not inst_history:
    inst_history = [{
        "date": "2026-11-13",
        "foreign": -142.58,
        "trust": 48.32,
        "dealer": -39.15,
        "total": -133.41,
    }]

  latest_inst = inst_history[-1]
  latest_twse = twse_margin[-1]
  latest_tpex = tpex_margin[-1]

  chips_summary = {
      "date": latest_inst["date"],
      "foreign": latest_inst["foreign"],
      "trust": latest_inst["trust"],
      "dealer": latest_inst["dealer"],
      "total": latest_inst["total"],
      "twse_margin_balance": latest_twse["balance"],
      "twse_margin_change": latest_twse["change"],
      "tpex_margin_balance": latest_tpex["balance"],
      "tpex_margin_change": latest_tpex["change"],
  }

  quotes = old_data.get("quotes", {})
  for sym in ALL_SYMBOLS:
    res = fetch_yf_quote(sym)
    if res:
      quotes[sym] = res

  output = {
      "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "institutional": chips_summary,
      "chips": chips_summary,
      "institutional_history": inst_history,
      "twse_margin": twse_margin,
      "tpex_margin": tpex_margin,
      "otc_margin": tpex_margin,
      "quotes": quotes,
  }

  with open("data/market_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
  main()
