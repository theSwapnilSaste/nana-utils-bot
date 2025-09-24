import os
import requests
import sqlite3
import json
import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# -------------------- CONFIG --------------------
BOT_TOKEN = os.environ.get("VERIFIER_BOT_TOKEN")
OWNER_ID = os.environ.get("OWNER_ID")

if not BOT_TOKEN or not OWNER_ID:
    raise Exception("Missing BOT_TOKEN or OWNER_ID environment variables")

OWNER_ID = int(OWNER_ID)
DB_FILE = "history.db"
# ------------------------------------------------

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_checked TEXT,
            status TEXT,
            result_json TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# Log verification to DB
def log_verification(token, status, result):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    masked = token[:5] + "..." + token[-5:]  # mask token
    cur.execute(
        "INSERT INTO verifications (token_checked, status, result_json, timestamp) VALUES (?,?,?,?)",
        (masked, status, json.dumps(result), datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

# -------------------- BOT COMMANDS --------------------
def verify_command(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("Unauthorized.")
        return

    if len(context.args) == 0:
        update.message.reply_text("Usage: /verify <bot_token>")
        return

    token = context.args[0]
    base_url = f"https://api.telegram.org/bot{token}"

    try:
        resp_me = requests.get(f"{base_url}/getMe", timeout=10).json()
    except Exception as e:
        update.message.reply_text(f"Error: {e}")
        return

    if not resp_me.get("ok"):
        result = {"status": "invalid", "error": resp_me.get("description")}
        log_verification(token, "invalid", result)
        update.message.reply_text(f"❌ Invalid token:\n{json.dumps(result, indent=2)}")
        return

    result = {"status": "valid", "bot_info": resp_me["result"]}

    try:
        resp_updates = requests.get(f"{base_url}/getUpdates", timeout=10).json()
        result["updates"] = resp_updates if resp_updates.get("ok") else {"status": "no updates"}
    except:
        result["updates"] = {"status": "no updates"}

    log_verification(token, "valid", result)
    update.message.reply_text(f"✅ Token is valid:\n{json.dumps(result, indent=2)}")

def history_command(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("Unauthorized.")
        return

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, token_checked, status, result_json, timestamp FROM verifications ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()

    messages = []
    for row in rows:
        messages.append(f"ID: {row[0]}\nToken: {row[1]}\nStatus: {row[2]}\nTime: {row[4]}")

    update.message.reply_text("\n\n".join(messages) if messages else "No history.")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    init_db()
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("verify", verify_command))
    dp.add_handler(CommandHandler("history", history_command))

    print("🔹 Nana Utils Bot started. Listening for commands...")
    updater.start_polling()
    updater.idle()
