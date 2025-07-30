import os, requests, json
from datetime import datetime, timedelta, timezone
from flask import Flask

from linebot import LineBotApi
from linebot.models import TextSendMessage

app = Flask(__name__)

# 環境変数から取得（Renderで設定する）
LBG = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
USER_ID = os.environ["TARGET_USER_ID"]

STATE_FILE = "last_id.txt"

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

def get_recent_eq():
    try:
        jst = timezone(timedelta(hours=+9))
        start = (datetime.now(jst) - timedelta(minutes=10)).isoformat()
        params = {
            "format": "geojson",
            "starttime": start,
            "minmagnitude": 3.5  # M3.5以上
        }
        r = requests.get(USGS_URL, params=params, timeout=15)
        r.raise_for_status()
        return r.json()["features"]
    except Exception as e:
        print(f"API Error: {e}")
        return []

def load_last_id():
    try:
        if os.path.exists(STATE_FILE):
            return open(STATE_FILE).read().strip()
        return ""
    except:
        return ""

def save_last_id(eqid):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(eqid)
    except:
        pass

@app.route("/")
def home():
    return "地震速報Bot動いてます！🌏"

@app.route("/checkquake")
def check():
    try:
        quakes = get_recent_eq()
        if not quakes:
            return "no quake"

        latest = quakes[0]
        last_sent = load_last_id()
        
        if latest["id"] == last_sent:
            return "already sent"

        # 地震情報を整形
        prop = latest["properties"]
        mag = prop.get('mag', '不明')
        place = prop.get('place', '不明')
        
        # 時刻を日本時間に変換
        utc_time = datetime.fromtimestamp(prop['time']/1000, tz=timezone.utc)
        jst_time = utc_time.astimezone(timezone(timedelta(hours=9)))
        
        msg = f"""🌏地震速報
マグニチュード: {mag}
場所: {place}
発生時刻: {jst_time.strftime('%m/%d %H:%M')} JST"""

        # LINEに送信
        LBG.push_message(USER_ID, TextSendMessage(text=msg))
        save_last_id(latest["id"])
        return "sent"
        
    except Exception as e:
        print(f"Error: {e}")
        return f"error: {e}"

if __name__ == "__main__":
    app.run(debug=True)
