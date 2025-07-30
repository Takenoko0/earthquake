import os, requests, json
from datetime import datetime, timedelta, timezone
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# 環境変数から取得（Renderで設定する）
LBG = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
USER_ID = os.environ.get("TARGET_USER_ID", "")  # 最初は空でもOK

handler = WebhookHandler(CHANNEL_SECRET)

STATE_FILE = "last_id.txt"
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# 地震API関連の関数
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

# ルート設定
@app.route("/")
def home():
    return "地震速報Bot動いてます！🌏"

@app.route("/checkquake")
def check():
    try:
        # TARGET_USER_IDが設定されていない場合はエラー
        if not USER_ID:
            return "TARGET_USER_ID not set. Please send a message to the bot first."
        
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

# LINE Webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # ユーザーIDを取得・表示
    user_id = event.source.user_id
    user_message = event.message.text
    
    print(f"🎯 USER_ID: {user_id}")
    print(f"📝 Message: {user_message}")
    
    # 特別なコマンド処理
    if user_message.lower() == "id":
        reply_text = f"あなたのユーザーID:\n{user_id}\n\nこれをTARGET_USER_IDに設定してね！📋"
    elif user_message.lower() == "test":
        reply_text = "テスト成功！🎉\nBot は正常に動作しています。"
    elif "地震" in user_message:
        reply_text = "地震速報Botが稼働中です🌏\n5分ごとに最新の地震情報をチェックしています！"
    else:
        reply_text = f"メッセージを受信しました📨\n\n💡コマンド:\n・「id」→ ユーザーIDを表示\n・「test」→ 動作テスト\n・「地震」→ Bot状態確認"
    
    # 返信
    LBG.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run(debug=True)
