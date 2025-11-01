
import os
from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage, UnsendEvent
from datetime import datetime
import pytz

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN", "CHJScm6eOVvEqpKzbP7Y0fYj5tVRlaA72LjvZH5Zzye9FzDZBROUF0sBVQgj31Pu52Xw9zoXTHz9syr3D6asy8RX7g+GXeHBKUr+eAHwQKtYz9pDsewuN8x1lwxp4bZeqj6C2cQ92/CBQB5nDac2owdB04t89/1O/w1cDnyilFU=")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET", "5b32df6428ad0f8861a721bf688522c0")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise ValueError("❌ โปรดตั้งค่า Environment Variables: CHANNEL_ACCESS_TOKEN และ CHANNEL_SECRET")

app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

message_memory = {}
chat_counter = {}

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text
    message_id = event.message.id
    group_id = getattr(event.source, 'group_id', user_id)
    chat_counter.setdefault(group_id, {"text": 0, "image": 0})
    chat_counter[group_id]["text"] += 1
    message_memory[message_id] = {"type": "text", "user_id": user_id, "text": text,
                                  "timestamp": datetime.now(pytz.timezone('Asia/Bangkok')),
                                  "group_id": group_id}

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    message_id = event.message.id
    group_id = getattr(event.source, 'group_id', user_id)
    chat_counter.setdefault(group_id, {"text": 0, "image": 0})
    chat_counter[group_id]["image"] += 1
    image_content = line_bot_api.get_message_content(message_id)
    image_path = f"temp_{message_id}.jpg"
    with open(image_path, 'wb') as f:
        for chunk in image_content.iter_content():
            f.write(chunk)
    message_memory[message_id] = {"type": "image", "user_id": user_id, "image_path": image_path,
                                  "timestamp": datetime.now(pytz.timezone('Asia/Bangkok')),
                                  "group_id": group_id}

@app.route('/images/<message_id>.jpg')
def serve_image(message_id):
    filepath = f"temp_{message_id}.jpg"
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/jpeg')
    return "File not found", 404

@handler.add(UnsendEvent)
def handle_unsend(event):
    message_id = event.unsend.message_id
    if message_id not in message_memory:
        return
    data = message_memory[message_id]
    user_id = data["user_id"]
    group_id = data["group_id"]
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except:
        display_name = "ไม่ทราบชื่อ"
    timestamp = data["timestamp"].strftime("%d/%m/%Y %H:%M")
    if data["type"] == "text":
        reply_text = (f"[ ข้อความที่ถูกยกเลิก ]\n"
                      f"• ผู้ส่ง : {display_name}\n"
                      f"• เวลาส่ง : {timestamp}\n"
                      f"• ประเภท : ข้อความ\n"
                      f"• ข้อความ : \"{data['text']}\"")
        line_bot_api.push_message(group_id, TextSendMessage(text=reply_text))
    elif data["type"] == "image":
        image_url = f"https://your-server-url/images/{message_id}.jpg"
        reply_text = (f"[ ข้อความที่ถูกยกเลิก ]\n"
                      f"• ผู้ส่ง : {display_name}\n"
                      f"• เวลาส่ง : {timestamp}\n"
                      f"• ประเภท : ภาพ\n"
                      f"• ข้อความ : ”ภาพยกเลิก“")
        line_bot_api.push_message(group_id, [
            TextSendMessage(text=reply_text),
            ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
        ])
    del message_memory[message_id]

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
