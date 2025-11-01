
import os
from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage, UnsendEvent
)
from datetime import datetime
import pytz

# ============================================================
# 🔧 ใส่ TOKEN และ SECRET ของฟ่างตรงนี้
# ============================================================
CHANNEL_ACCESS_TOKEN = CHANNEL_ACCESS_TOKEN = "M3vlwbrwKhblV7D8mR/t2yw6pkNkJGHwirpmvVyKv7NvXFFTbUzt8A4xPljbyTayaOjDZWLvYQAipzZ3Kk37ybEP3LoWKlmexIPspLWw/J9PcZnAmjWVovi0lmvymgdh4t417VAAtf5QEw/lPSp77gdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "6267215bc5bb5436a7f5869421982fc3"

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
app = Flask(__name__)

message_memory = {}
chat_counter = {}
bill_number = {}

# ============================================================
# 💬 เก็บข้อความ + เริ่มบิล + สรุปบิล
# ============================================================
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text
    message_id = event.message.id
    group_id = getattr(event.source, 'group_id', user_id)

    # เริ่มนับบิลใหม่
    if text.startswith("เพิ่มประกาศ"):
        bill_number[group_id] = bill_number.get(group_id, 0) + 1
        chat_counter[group_id] = {"text": 0, "image": 0}
        line_bot_api.push_message(
            group_id,
            TextSendMessage(text=f"เริ่มนับจากประกาศนี้เป็นบิลที่ {bill_number[group_id]} 🧾")
        )
        return

    # สรุปบิล
    if text.strip() == "###":
        counts = chat_counter.get(group_id, {"text": 0, "image": 0})
        total = counts["text"] + counts["image"]
        bill_no = bill_number.get(group_id, 1)
        summary = (
            f"📊 สรุปบิลที่ {bill_no}\n"
            f"• ข้อความ: {counts['text']}\n"
            f"• ภาพ: {counts['image']}\n"
            f"รวมทั้งหมด: {total} รายการ"
        )
        line_bot_api.push_message(group_id, TextSendMessage(text=summary))
        return

    # นับข้อความ
    if text.strip() != ".":
        chat_counter.setdefault(group_id, {"text": 0, "image": 0})
        chat_counter[group_id]["text"] += 1

    message_memory[message_id] = {
        "type": "text",
        "user_id": user_id,
        "text": text,
        "timestamp": datetime.now(pytz.timezone('Asia/Bangkok')),
        "group_id": group_id
    }

# ============================================================
# 🖼 เก็บภาพ
# ============================================================
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

    message_memory[message_id] = {
        "type": "image",
        "user_id": user_id,
        "image_path": image_path,
        "timestamp": datetime.now(pytz.timezone('Asia/Bangkok')),
        "group_id": group_id
    }

# ============================================================
# 🖼 Serve ภาพ
# ============================================================
@app.route('/images/<message_id>.jpg')
def serve_image(message_id):
    path = f"temp_{message_id}.jpg"
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return "File not found", 404

# ============================================================
# 🚫 จับยกเลิกข้อความ/ภาพ
# ============================================================
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

    timestamp = data["timestamp"].strftime("%d/%m/%Y %H:%M:%S")
    msg_type = "ข้อความ" if data["type"] == "text" else "ภาพ"

    if data["type"] == "text":
        text = data["text"]
        reply_text = (
            f"[ {text} ]\n"
            f"• ผู้ส่ง: {display_name}\n"
            f"• เวลาส่ง: {timestamp}\n"
            f"• ประเภท: {msg_type}"
        )
        line_bot_api.push_message(group_id, TextSendMessage(text=reply_text))
    else:
        image_url = f"https://{request.host}/images/{message_id}.jpg"
        reply_text = (
            f"[ ภาพถูกยกเลิก ]\n"
            f"• ผู้ส่ง: {display_name}\n"
            f"• เวลาส่ง: {timestamp}\n"
            f"• ประเภท: {msg_type}"
        )
        line_bot_api.push_message(group_id, [
            TextSendMessage(text=reply_text),
            ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
        ])

    del message_memory[message_id]

# ============================================================
# 🌐 Webhook
# ============================================================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ============================================================
# 🚀 รันบน Render (24 ชั่วโมง)
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
