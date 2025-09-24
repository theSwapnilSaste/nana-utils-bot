from flask import Flask, request, jsonify
import requests, sqlite3, json, os, datetime

app = Flask(__name__)
DB_FILE = "history.db"
SECRET_KEY = os.environ.get("VERIFIER_SECRET", "changeme")  # set in environment

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

def log_verification(token, status, result):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    masked = token[:5] + "..." + token[-5:]  # mask token for safety
    cur.execute("INSERT INTO verifications (token_checked, status, result_json, timestamp) VALUES (?,?,?,?)",
                (masked, status, json.dumps(result), datetime.datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

@app.route("/verify", methods=["GET"])
def verify():
    # --- Auth ---
    key = request.args.get("key")
    if key != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    # --- Params ---
    token = request.args.get("token")
    fetch_updates = request.args.get("updates", "false").lower() == "true"
    if not token:
        return jsonify({"error": "Missing token"}), 400

    base_url = f"https://api.telegram.org/bot{token}"
    resp_me = requests.get(f"{base_url}/getMe").json()

    if not resp_me.get("ok"):
        result = {"status": "invalid", "error": resp_me.get("description")}
        log_verification(token, "invalid", result)
        return jsonify(result)

    result = {"status": "valid", "bot_info": resp_me["result"]}

    if fetch_updates:
        resp_updates = requests.get(f"{base_url}/getUpdates").json()
        result["updates"] = resp_updates if resp_updates.get("ok") else {"status": "no updates"}

    # log result
    log_verification(token, "valid", result)
    return jsonify(result)

@app.route("/history", methods=["GET"])
def history():
    # --- Auth ---
    key = request.args.get("key")
    if key != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, token_checked, status, result_json, timestamp FROM verifications ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "token_checked": row[1],
            "status": row[2],
            "result_json": json.loads(row[3]),
            "timestamp": row[4]
        })

    return jsonify(history)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
