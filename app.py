
import os
from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage, UnsendEvent
)
from datetime import datetime
import pytz

app = Flask(__name__)

# ======= ใส่ TOKEN / SECRET ของฟ่าง =======
CHANNEL_ACCESS_TOKEN = "M3vlwbrwKhblV7D8mR/t2yw6pkNkJGHwirpmvVyKv7NvXFFTbUzt8A4xPljbyTayaOjDZWLvYQAipzZ3Kk37ybEP3LoWKlmexIPspLWw/J9PcZnAmjWVovi0lmvymgdh4t417VAAtf5QEw/lPSp77gdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "6267215bc5bb5436a7f5869421982fc3"
YOUR_DOMAIN = "jinnee-bot.onrender.com"

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ======= ตัวเก็บข้อความและบิล =======
message_memory = {}  # เก็บข้อความ/ภาพ
chat_counter = {}    # group_id -> {"text": n, "image": m}
bill_number = {}     # group_id -> n

# =================== Serve ภาพ ===================
@app.route('/images/<filename>')
def serve_image(filename):
    if os.path.exists(filename):
        return send_file(filename, mimetype='image/jpeg')
    return "File not found", 404

# =================== Webhook ===================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid Signature Error")
        abort(400)
    except Exception as e:
        print("Error in /callback:", e)
        abort(500)
    return "OK"

# =================== รับข้อความ ===================
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    try:
        user_id = event.source.user_id
        group_id = getattr(event.source, 'group_id', user_id)
        text = event.message.text
        message_id = event.message.id

        # ---------- เริ่มนับบิลใหม่ ----------
        if text.strip() == "เพิ่มประกาศ":
            bill_number[group_id] = bill_number.get(group_id, 0) + 1
            chat_counter[group_id] = {"text": 0, "image": 0}
            message_memory.clear()  # ล้างข้อความเก่า
            try:
                line_bot_api.push_message(group_id, TextSendMessage(
                    text=f"เริ่มนับจากประกาศนี้เป็นบิลที่ {bill_number[group_id]} 🧾"
                ))
            except Exception as e:
                print("Push message failed (เพิ่มประกาศ):", e)
            return

        # ---------- สรุปบิล ----------
        if text.strip() == "###":
            counts = chat_counter.get(group_id, {"text": 0, "image": 0})
            total = counts["text"] + counts["image"]
            bill_no = bill_number.get(group_id, 1)
            summary = (
                f"✨สรุปบิลที่ {bill_no}✨\n"
                f"• ข้อความ: {counts['text']}\n"
                f"• ภาพ: {counts['image']}\n"
                f"🌷รวมทั้งหมด: {total} 📬"
            )
            try:
                line_bot_api.push_message(group_id, TextSendMessage(text=summary))
            except Exception as e:
                print("Push message failed (สรุปบิล):", e)
            return

        # ---------- นับข้อความ ----------
        if text.strip() != ".":
            chat_counter.setdefault(group_id, {"text": 0, "image": 0})
            chat_counter[group_id]["text"] += 1

        # เก็บข้อความ
        message_memory[message_id] = {
            "type": "text",
            "user_id": user_id,
            "text": text,
            "timestamp": datetime.now(pytz.timezone("Asia/Bangkok")),
            "group_id": group_id
        }

    except Exception as e:
        print("Error in handle_text:", e)

# =================== รับภาพ ===================
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    try:
        user_id = event.source.user_id
        group_id = getattr(event.source, 'group_id', user_id)
        message_id = event.message.id

        chat_counter.setdefault(group_id, {"text": 0, "image": 0})
        chat_counter[group_id]["image"] += 1

        # บันทึกภาพในเครื่อง
        image_content = line_bot_api.get_message_content(message_id)
        image_path = f"temp_{message_id}.jpg"
        with open(image_path, "wb") as f:
            for chunk in image_content.iter_content():
                f.write(chunk)

        # เก็บ memory
        message_memory[message_id] = {
            "type": "image",
            "user_id": user_id,
            "image_path": image_path,
            "timestamp": datetime.now(pytz.timezone("Asia/Bangkok")),
            "group_id": group_id
        }

    except Exception as e:
        print("Error in handle_image:", e)

# =================== จับยกเลิกข้อความ/ภาพ ===================
@handler.add(UnsendEvent)
def handle_unsend(event):
    try:
        message_id = event.unsend.message_id
        if message_id not in message_memory:
            return
        data = message_memory[message_id]
        group_id = data["group_id"]
        user_id = data["user_id"]

        # ดึงชื่อผู้ส่ง
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except:
            display_name = "ไม่ทราบชื่อ"

        timestamp = data["timestamp"].strftime("%d/%m/%Y %H:%M:%S")

        if data["type"] == "text":
            text = data["text"]
            reply = (
                f"[  ข้อความที่ถูกยกเลิก  ]\n"
                f"• ผู้ส่ง: {display_name}\n"
                f"• เวลา: {timestamp}\n"
                f"• ข้อความ : {text}"
            )
            try:
                line_bot_api.push_message(group_id, TextSendMessage(text=reply))
            except Exception as e:
                print("Push message failed (ข้อความยกเลิก):", e)

        elif data["type"] == "image":
            image_path = data["image_path"]
            reply_text = (
                f"[  ข้อความที่ถูกยกเลิก  ]\n"
                f"• ผู้ส่ง: {display_name}\n"
                f"• เวลา: {timestamp}\n"
                f"• ข้อความ : ภาพถูกยกเลิก"
            )
            try:
                line_bot_api.push_message(group_id, [
                    TextSendMessage(text=reply_text),
                    ImageSendMessage(
                        original_content_url=f"https://{YOUR_DOMAIN}/images/{os.path.basename(image_path)}",
                        preview_image_url=f"https://{YOUR_DOMAIN}/images/{os.path.basename(image_path)}"
                    )
                ])
            except Exception as e:
                print("Push message failed (ภาพยกเลิก):", e)

        # ลดจำนวนในบิล
        if group_id in chat_counter:
            chat_counter[group_id][data["type"]] = max(0, chat_counter[group_id][data["type"]] - 1)

        del message_memory[message_id]

    except Exception as e:
        print("Error in handle_unsend:", e)

# =================== รัน Flask สำหรับ Render ===================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
       
  

  
      
