#!/usr/bin/env python3
"""
smart_shield_protectable.py

Enhanced Smart Shield prototype:
 - ML detection (SVM, RandomForest, LogisticRegression)
 - Real HTTP capture via Flask
 - Active protection: IP blocklist with expiry, auto-block on detection, rate-limiting
 - Persistent tamper-evident logs (blockchain-like) stored in SQLite
 - Monitoring endpoints: /stats, /blockchain, /blocked
 - Demo mode to exercise detection+blocking

Usage:
  pip install flask scikit-learn pandas requests
  python smart_shield_protectable.py --demo
  python smart_shield_protectable.py
"""

import argparse
import hashlib
import json
import random
import re
import sqlite3
import threading
import time
import signal
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests
from flask import Flask, jsonify, request, abort
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC

# ---------------------------
# Config
# ---------------------------
HOST = "127.0.0.1"
PORT = 5000
DB_FILE = "smart_shield.db"
RANDOM_SEED = 42

# Protection parameters (tune as needed)
RATE_LIMIT_WINDOW = 10          # seconds window
RATE_LIMIT_REQUESTS = 10        # max requests in window before rate-limit triggered
AUTO_BLOCK_ON_RATE = True       # auto-block when exceeding rate limit
AUTO_BLOCK_DURATION = 60 * 60   # seconds (1 hour) block duration when auto-blocked
AUTO_BLOCK_ON_DETECTION = True  # auto-block when ML ensemble says attack
DETECTION_PROB_THRESHOLD = 0.6  # per-model probability threshold to count as "attack vote"

random.seed(RANDOM_SEED)

# ---------------------------
# Database (SQLite) helpers
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    # blockchain table: index (auto), timestamp, data(JSON), prev_hash, hash
    c.execute("""
    CREATE TABLE IF NOT EXISTS blockchain (
        idx INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        data TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        hash TEXT NOT NULL
    );
    """)
    # blocked ips table: ip, blocked_at, expires_at, reason
    c.execute("""
    CREATE TABLE IF NOT EXISTS blocked_ips (
        ip TEXT PRIMARY KEY,
        blocked_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        reason TEXT
    );
    """)
    conn.commit()
    return conn

db_conn = init_db()
db_lock = threading.Lock()  # protect DB from concurrent writes

def add_chain_block(data_dict):
    """Append a block to the persistent blockchain table and return the block row as dict."""
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("SELECT hash FROM blockchain ORDER BY idx DESC LIMIT 1;")
        row = cur.fetchone()
        prev_hash = row[0] if row else "0"
        payload = json.dumps(data_dict, sort_keys=True) + prev_hash
        block_hash = hashlib.sha256(payload.encode()).hexdigest()
        ts = datetime.utcnow().isoformat() + "Z"
        cur.execute("INSERT INTO blockchain (timestamp, data, prev_hash, hash) VALUES (?, ?, ?, ?)",
                    (ts, json.dumps(data_dict), prev_hash, block_hash))
        db_conn.commit()
        idx = cur.lastrowid
        return {"idx": idx, "timestamp": ts, "data": data_dict, "prev_hash": prev_hash, "hash": block_hash}

def list_chain_blocks(limit=1000):
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("SELECT idx, timestamp, data, prev_hash, hash FROM blockchain ORDER BY idx ASC LIMIT ?;", (limit,))
        rows = cur.fetchall()
        return [{"idx": r[0], "timestamp": r[1], "data": json.loads(r[2]), "prev_hash": r[3], "hash": r[4]} for r in rows]

def block_ip_persist(ip, duration_seconds, reason="auto"):
    blocked_at = datetime.utcnow()
    expires_at = blocked_at + timedelta(seconds=duration_seconds)
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("INSERT OR REPLACE INTO blocked_ips (ip, blocked_at, expires_at, reason) VALUES (?, ?, ?, ?)",
                    (ip, blocked_at.isoformat() + "Z", expires_at.isoformat() + "Z", reason))
        db_conn.commit()

def unblock_ip_persist(ip):
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("DELETE FROM blocked_ips WHERE ip = ?;", (ip,))
        db_conn.commit()

def list_blocked_ips():
    # Return blocked IPs, but exclude expired ones (also clean them up)
    now = datetime.utcnow().isoformat() + "Z"
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("SELECT ip, blocked_at, expires_at, reason FROM blocked_ips;")
        rows = cur.fetchall()
        result = []
        expired = []
        for ip, blocked_at, expires_at, reason in rows:
            if expires_at <= now:
                expired.append(ip)
            else:
                result.append({"ip": ip, "blocked_at": blocked_at, "expires_at": expires_at, "reason": reason})
        # cleanup expired
        for ip in expired:
            cur.execute("DELETE FROM blocked_ips WHERE ip = ?;", (ip,))
        db_conn.commit()
    return result

def is_ip_blocked(ip):
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("SELECT expires_at FROM blocked_ips WHERE ip = ?;", (ip,))
        row = cur.fetchone()
        if not row:
            return False
        expires_at = row[0]
        if expires_at <= (datetime.utcnow().isoformat() + "Z"):
            # expired — cleanup
            cur.execute("DELETE FROM blocked_ips WHERE ip = ?;", (ip,))
            db_conn.commit()
            return False
        return True

# ---------------------------
# Synthetic dataset & feature extraction
# ---------------------------
def generate_requests_dataset(n=600):
    normal_payloads = [
        "GET /home?id=123 HTTP/1.1",
        "POST /login user=admin&pass=secret",
        "GET /search?q=flowers",
        "POST /comment data=hello",
        "GET /products?id=45",
        "POST /order item=book&qty=1",
        "GET /about",
        "GET /contact?subject=help",
        "GET /docs/overview"
    ]
    attack_payloads = [
        "GET /login?id=' OR '1'='1",
        "POST /search?q=<script>alert(1)</script>",
        "GET /page?file=../../etc/passwd",
        "POST /exec?cmd=rm -rf /",
        "GET /item?id=1; DROP TABLE users; --",
        "GET /download?path=/var/www/../../etc/shadow",
        "GET /?user=admin'--",
        "POST /upload filename=../../../etc/hosts",
        "GET /?q=<svg/onload=alert(1)>"
    ]
    data, labels = [], []
    for _ in range(n):
        if random.random() < 0.57:
            data.append(random.choice(normal_payloads))
            labels.append(0)
        else:
            data.append(random.choice(attack_payloads))
            labels.append(1)
    return pd.DataFrame({"payload": data, "label": labels})

def extract_features_from_payload(payload_series: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"payload": payload_series})
    df["len"] = df["payload"].apply(len)
    df["has_sql_quote"] = df["payload"].str.contains("'", case=False, regex=False).astype(int)
    df["has_script_tag"] = df["payload"].str.contains(r"<script>|<svg|onload=", case=False, regex=True).astype(int)
    df["has_path_traversal"] = df["payload"].str.contains(r"\.\./", regex=True).astype(int)
    df["has_cmd_or_sql_keywords"] = df["payload"].str.contains(
        r"\b(rm|exec|cmd|DROP|TABLE|--|UNION|SELECT)\b", case=False, regex=True
    ).astype(int)
    # count suspicious chars like ; or %3C or %27 or <>
    df["semi_colon"] = df["payload"].str.contains(";", regex=False).astype(int)
    df["encoded_chars"] = df["payload"].str.contains(r"%3C|%3E|%27|%3B", case=False, regex=True).astype(int)
    return df[["len", "has_sql_quote", "has_script_tag", "has_path_traversal", "has_cmd_or_sql_keywords", "semi_colon", "encoded_chars"]]

# ---------------------------
# Train ML models
# ---------------------------
def train_models(random_state=RANDOM_SEED):
    df = generate_requests_dataset(700)
    X = extract_features_from_payload(df["payload"])
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=random_state)

    models = {
        "SVM": SVC(kernel="linear", probability=True, random_state=random_state),
        "RandomForest": RandomForestClassifier(n_estimators=120, random_state=random_state),
        "LogisticRegression": LogisticRegression(max_iter=400, random_state=random_state)
    }

    trained = {}
    for name, m in models.items():
        m.fit(X_train, y_train)
        preds = m.predict(X_test)
        acc = accuracy_score(y_test, preds)
        trained[name] = {"model": m, "accuracy": acc}
    # ensemble accuracy on test set
    ensemble_preds = []
    for i in range(len(X_test)):
        sample = X_test.iloc[[i]]
        votes = []
        for info in trained.values():
            votes.append(int(info["model"].predict(sample)[0]))
        ensemble_preds.append(1 if sum(votes) >= (len(votes)/2) else 0)
    ensemble_acc = accuracy_score(y_test, ensemble_preds)
    return trained, ensemble_acc

# ---------------------------
# Rate limiter + in-memory counters
# ---------------------------
# structure: ip -> list of timestamps of recent requests (prune periodically)
rate_counters = {}
rate_lock = threading.Lock()

def record_request_and_check_rate(ip):
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    with rate_lock:
        arr = rate_counters.get(ip, [])
        # drop older than window_start
        arr = [t for t in arr if t >= window_start]
        arr.append(now)
        rate_counters[ip] = arr
        if len(arr) > RATE_LIMIT_REQUESTS:
            return False, len(arr)  # rate exceeded
        return True, len(arr)

# ---------------------------
# Flask app & logic
# ---------------------------
app = Flask("smart_shield_protectable")

trained_models = {}
ensemble_accuracy = 0.0

metrics = {
    "total_requests": 0,
    "total_attacks_detected": 0,
    "blocked_requests": 0,
    "by_prediction": {"normal": 0, "attack": 0}
}

def get_remote_ip():
    # trust X-Forwarded-For if present (for proxied scenarios) else remote_addr
    xff_header = request.headers.get("X-Forwarded-For", "")
    xff = xff_header.split(",")[0].strip() if xff_header else ""
    return xff or request.remote_addr or "unknown"

def normalize_payload(method, path, query, body):
    if query and body:
        return f"{method} {path}?{query} BODY:{body}"
    elif query:
        return f"{method} {path}?{query}"
    elif body:
        return f"{method} {path} BODY:{body}"
    else:
        return f"{method} {path}"

def classify_payload(payload_text):
    feats = extract_features_from_payload(pd.Series([payload_text]))
    votes = {}
    probs = {}
    for name, info in trained_models.items():
        model = info["model"]
        pred = int(model.predict(feats)[0])
        prob = None
        if hasattr(model, "predict_proba"):
            try:
                prob = float(model.predict_proba(feats)[0][1])
            except Exception:
                prob = None
        elif hasattr(model, "decision_function"):
            try:
                val = float(model.decision_function(feats)[0])
                prob = abs(val) / (1 + abs(val))
            except Exception:
                prob = None
        votes[name] = pred
        probs[name] = prob
    # count votes using probability threshold for robustness
    prob_votes = 0
    valid_probs = [p for p in probs.values() if p is not None]
    for name, p in probs.items():
        if p is not None and p >= DETECTION_PROB_THRESHOLD:
            prob_votes += 1
    # fallback: use prediction votes if probabilities missing
    if len(valid_probs) >= 1:
        # use prob_votes
        is_attack = prob_votes >= (len(probs) / 2)
    else:
        is_attack = sum(votes.values()) >= (len(votes) / 2)
    return {"votes": votes, "probs": probs, "is_attack": bool(is_attack)}

@app.before_request
def enforcement_middleware():
    """
    Called before each request:
      - check if IP blocked => deny
      - rate limit and possibly auto-block
    """
    ip = get_remote_ip()
    metrics["total_requests"] += 1

    # check persisted blocklist
    if is_ip_blocked(ip):
        metrics["blocked_requests"] += 1
        # immediately return 403 for blocked IPs
        abort(403, description="Your IP is blocked.")

    # rate limiting
    ok, count = record_request_and_check_rate(ip)
    if not ok:
        # rate exceeded
        if AUTO_BLOCK_ON_RATE:
            reason = f"rate_limit_exceeded:{count}_in_{RATE_LIMIT_WINDOW}s"
            block_ip_persist(ip, AUTO_BLOCK_DURATION, reason)
            add_chain_block({"event": "auto_block_rate", "ip": ip, "count": count, "window": RATE_LIMIT_WINDOW, "reason": reason})
            metrics["total_attacks_detected"] += 1
            metrics["by_prediction"]["attack"] += 1
            abort(403, description="Your IP has been blocked due to rate limit.")
        else:
            # just return 429 Too Many Requests
            abort(429, description="Rate limit exceeded. Slow down.")

@app.route("/", methods=["GET", "POST"])
def capture():
    ip = get_remote_ip()
    method = request.method
    path = request.path
    query = request.query_string.decode(errors="ignore") if request.query_string else ""
    body = request.get_data(as_text=True) or ""
    payload = normalize_payload(method, path, query, body)

    # classify
    result = classify_payload(payload)
    prediction = "attack" if result["is_attack"] else "normal"

    # prepare log entry
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "src_ip": ip,
        "method": method,
        "path": path,
        "query": query,
        "body": body[:1000],
        "payload_summary": payload if len(payload) <= 300 else payload[:300] + "...",
        "prediction": prediction,
        "model_votes": result["votes"],
        "model_probs": result["probs"]
    }

    # if attack, persist to blockchain and optionally auto-block IP
    if result["is_attack"]:
        metrics["total_attacks_detected"] += 1
        metrics["by_prediction"]["attack"] += 1
        block = add_chain_block(entry)
        if AUTO_BLOCK_ON_DETECTION:
            block_ip_persist(ip, AUTO_BLOCK_DURATION, reason="ml_detection")
            # append a block to record auto-block event too
            add_chain_block({"event": "auto_block_detection", "ip": ip, "block_idx": block["idx"]})
        entry["block_hash"] = block["hash"]
        return jsonify({"status": "blocked", "detection": entry}), 200

    # normal
    metrics["by_prediction"]["normal"] += 1
    return jsonify({"status": "ok", "detection": entry}), 200

@app.route("/blockchain", methods=["GET"])
def get_chain():
    limit = int(request.args.get("limit", "1000"))
    return jsonify(list_chain_blocks(limit=limit))

@app.route("/blocked", methods=["GET", "POST", "DELETE"])
def manage_blocked():
    """
    GET /blocked -> list blocked IPs
    POST /blocked  { "ip": "1.2.3.4", "duration": 3600, "reason": "admin" } -> block
    DELETE /blocked  { "ip": "1.2.3.4" } -> unblock
    """
    if request.method == "GET":
        return jsonify(list_blocked_ips())
    elif request.method == "POST":
        data = request.get_json(force=True)
        ip = data.get("ip")
        dur = int(data.get("duration", AUTO_BLOCK_DURATION))
        reason = data.get("reason", "manual")
        if not ip:
            return jsonify({"error": "ip required"}), 400
        block_ip_persist(ip, dur, reason)
        add_chain_block({"event": "manual_block", "ip": ip, "duration": dur, "reason": reason})
        return jsonify({"result": "blocked", "ip": ip}), 200
    else:
        data = request.get_json(force=True)
        ip = data.get("ip")
        if not ip:
            return jsonify({"error": "ip required"}), 400
        unblock_ip_persist(ip)
        add_chain_block({"event": "manual_unblock", "ip": ip})
        return jsonify({"result": "unblocked", "ip": ip}), 200

@app.route("/stats", methods=["GET"])
def stats():
    model_stats = {name: {"accuracy": info["accuracy"]} for name, info in trained_models.items()}
    return jsonify({
        "models": model_stats,
        "ensemble_accuracy": ensemble_accuracy,
        "metrics": metrics,
        "blocked": list_blocked_ips()
    })

@app.route("/shutdown", methods=["POST"])
def shutdown():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        return "Shutdown only available in dev server", 500
    func()
    return "Shutting down..."

# ---------------------------
# Demo requests to exercise the system
# ---------------------------
def run_demo_requests():
    print("[demo] Sending requests to demonstrate detection and blocking...")
    examples = [
        {"method": "GET", "url": f"http://{HOST}:{PORT}/", "params": {"id":"123"}},
        {"method": "GET", "url": f"http://{HOST}:{PORT}/login", "params": {"id":"' OR '1'='1"}},
        {"method": "GET", "url": f"http://{HOST}:{PORT}/search", "params": {"q":"<script>alert(1)</script>"}},
        {"method": "GET", "url": f"http://{HOST}:{PORT}/page", "params": {"file":"../../etc/passwd"}},
        {"method": "POST", "url": f"http://{HOST}:{PORT}/exec", "data": "cmd=rm -rf /"},
        # Requests from same IP to trigger rate limit (we'll send many rapid requests)
    ]
    session = requests.Session()
    responses = []
    for req in examples:
        try:
            if req["method"] == "GET":
                r = session.get(req["url"], params=req.get("params"), timeout=5)
            else:
                r = session.post(req["url"], data=req.get("data"), timeout=5)
            try:
                body = r.json()
            except Exception:
                body = r.text
            responses.append((req, r.status_code, body))
            time.sleep(0.2)
        except Exception as e:
            responses.append((req, "ERROR", str(e)))

    # Now send rapid requests to trigger rate-limit from same IP
    rl_url = f"http://{HOST}:{PORT}/"
    for i in range(RATE_LIMIT_REQUESTS + 3):
        try:
            r = session.get(rl_url, params={"q": f"test{i}"}, timeout=3)
            try:
                body = r.json()
            except Exception:
                body = r.text
            responses.append(({"method":"GET","url":rl_url,"params":{"q":f"test{i}"}}, r.status_code, body))
        except Exception as e:
            responses.append(({"method":"GET","url":rl_url}, "ERROR", str(e)))
        time.sleep(0.2)

    # Print responses
    print("\n[demo] Responses:")
    for req, status, body in responses:
        print("----------------------------------------------------------------")
        print(f"{req['method']} {req['url']} params={req.get('params')} data={req.get('data')}")
        print("Status:", status)
        if isinstance(body, dict):
            print(json.dumps(body, indent=2))
        else:
            print(body)
    print("----------------------------------------------------------------")

    # Show blockchain and blocked IPs
    try:
        bc = requests.get(f"http://{HOST}:{PORT}/blockchain", timeout=4).json()
        blocked = requests.get(f"http://{HOST}:{PORT}/blocked", timeout=4).json()
        print("\n[demo] Blockchain entries (last 10):")
        print(json.dumps(bc[-10:], indent=2))
        print("\n[demo] Blocked IPs:")
        print(json.dumps(blocked, indent=2))
    except Exception as e:
        print("[demo] Could not fetch chain/blocked:", e)

# ---------------------------
# Entrypoint & server lifecycle
# ---------------------------
def start_server(demo_mode=False):
    global trained_models, ensemble_accuracy
    print("[*] Training models...")
    trained_models, ensemble_accuracy = train_models()
    print("[*] Trained models:")
    for name, info in trained_models.items():
        print(f"  - {name}: {info['accuracy']*100:.2f}%")
    print(f"  - ensemble accuracy: {ensemble_accuracy*100:.2f}%")

    # run flask app in thread
    def run_app():
        # Flask's builtin will block this thread; running without reloader for cleanliness
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_app, daemon=True)
    server_thread.start()
    print(f"[*] Flask server started at http://{HOST}:{PORT}/ (thread id {server_thread.ident})")

    demo_thread = None
    if demo_mode:
        # wait briefly for server to accept connections
        time.sleep(1.0)
        demo_thread = threading.Thread(target=run_demo_requests, daemon=True)
        demo_thread.start()

    # Wait for keyboard interrupt or server thread termination
    try:
        while True:
            time.sleep(0.5)
            # join with timeout to keep loop responsive
            if not server_thread.is_alive():
                print("[*] Server thread stopped.")
                break
            # optionally cleanup expired blocked IPs periodically
            # call list_blocked_ips() to trigger cleanup of expired entries
    except KeyboardInterrupt:
        print("\n[!] KeyboardInterrupt received. Shutting down server...")
        try:
            requests.post(f"http://{HOST}:{PORT}/shutdown", timeout=2)
        except Exception:
            pass
    finally:
        # give shutdown a moment
        time.sleep(0.5)
        try:
            db_conn.close()
        except Exception:
            pass
        print("[*] Exiting.")

def handle_signals(signum, frame):
    print(f"\n[!] Signal {signum} received, exiting.")
    try:
        db_conn.close()
    except Exception:
        pass
    sys.exit(0)

# Register signal handlers for clean exit
signal.signal(signal.SIGINT, handle_signals)
signal.signal(signal.SIGTERM, handle_signals)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Shield Protectable - demo/prototype WAF with ML & blockchain-like logs")
    parser.add_argument("--demo", action="store_true", help="Run demo requests after server starts")
    parser.add_argument("--host", default=HOST, help="Host to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=PORT, help="Port to bind (default 5000)")
    args = parser.parse_args()

    HOST = args.hostcld
    PORT = args.port

    start_server(demo_mode=args.demo)
