import random
import sqlite3
import urllib.request
import json as _json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = "your-secret-key-here"

# ------------------ DATABASE ------------------

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            habit_name TEXT,
            money_spent INTEGER,
            time_spent INTEGER,
            last_used TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            habit_name TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()



GROQ_API_KEY = "your-groq-api-key-here"

GROQ_SYSTEM = """You are HealMind AI, a compassionate and knowledgeable habit recovery coach built into the HealMind app. You help people quit bad habits like smoking, drugs, gambling, porn, alcohol, procrastination, and other addictions.

You:
- Provide emotional support and encouragement when users are struggling
- Give practical, science-based coping strategies for cravings
- Celebrate milestones and progress warmly
- Offer advice on withdrawal symptoms and what to expect
- Help users understand why they relapsed and how to get back on track
- Are warm, non-judgmental, and motivating at all times

SMOKING — Allen Carr's Easy Way philosophy:
When the topic is smoking, apply these core truths naturally:
1. THE TRAP: Nicotine creates the anxiety smokers think cigarettes relieve. The cigarette caused the stress, not cured it.
2. TWO MONSTERS: The "little monster" is physical withdrawal (tiny, lasts seconds). The "big monster" is the psychological belief you need it. Kill the big monster and the little one starves.
3. REFRAME CRAVINGS: "That feeling is just the little monster dying. Every craving I don't feed is me winning."
4. NOT GIVING ANYTHING UP: You are escaping a prison, not leaving a party. Non-smokers don't feel deprived.
5. YOU'RE ALREADY FREE: The moment you decide, you are a non-smoker. Own it immediately.
6. NO SUCH THING AS ONE CIGARETTE: The first one re-lights the little monster and restarts the trap.
7. WITHDRAWAL IS TINY: It peaks at 3 days, fades within weeks. The suffering is almost entirely psychological.

Occasionally reference Allen Carr naturally. Keep it conversational, not lecture-like.

Keep responses short and punchy. 1-2 sentences for greetings. Only go longer when someone needs a real pep talk. Talk like a real person. If someone asks something unrelated to habits or mental health, gently redirect them."""

# ------------------ ROUTES ------------------

QUOTES = [
    "Discipline is choosing what you want most over what you want now.",
    "Small steps every day lead to big changes.",
    "You don't have to be perfect, just consistent.",
    "Your future is created by what you do today.",
    "It's not about motivation, it's about habit.",
    "Fall seven times, stand up eight.",
    "You are stronger than your urges.",
    "Progress, not perfection."
]

@app.route("/")
def home():
    return render_template("index.html", user=session.get("user"), quote=random.choice(QUOTES))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name    = request.form["name"]
        email   = request.form["email"]
        password = request.form["password"]
        confirm  = request.form["confirm_password"]

        if password != confirm:
            return "Passwords do not match"

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
        conn.commit()
        conn.close()
        return redirect("/login")

    return render_template("register.html", user=session.get("user"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user"]    = user[1].split()[0]
            session["user_id"] = user[0]
            return redirect("/dashboard")
        return render_template("login.html", error="Invalid email or password", user=None)

    return render_template("login.html", user=session.get("user"))

@app.route("/dashboard")
def dashboard():
    user_id = session.get("user_id", 1)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT habit_name, last_used, money_spent, time_spent FROM habits WHERE user_id=?", (user_id,))
    habits = [h for h in cursor.fetchall() if h[0] and h[0] != "None"]
    conn.close()
    return render_template("dashboard.html", habits=habits, user=session.get("user"), quote=random.choice(QUOTES))

@app.route("/save_details", methods=["POST"])
def save_details():
    try:
        user_id   = session.get("user_id", 1)
        habit     = request.form.get("habit")
        money     = request.form.get("money")
        time      = request.form.get("time")
        last_used = request.form.get("last_used")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO habits (user_id, habit_name, money_spent, time_spent, last_used) VALUES (?, ?, ?, ?, ?)",
            (user_id, habit, money, time, last_used)
        )
        conn.commit()
        conn.close()
        return "OK"
    except Exception:
        return "Server error", 500

@app.route("/delete_habit", methods=["POST"])
def delete_habit():
    user_id = session.get("user_id", 1)
    name = request.get_json().get("name")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM habits WHERE habit_name=? AND user_id=?", (name, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/reset_habit", methods=["POST"])
def reset_habit():
    name = request.get_json().get("name")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE habits SET last_used=? WHERE habit_name=?", (datetime.now().isoformat(), name))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/clean")
def clean():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM habits WHERE habit_name IS NULL OR habit_name='None'")
    conn.commit()
    conn.close()
    return "Cleaned"

# ------------------ DIARY ------------------

@app.route("/add_note", methods=["POST"])
def add_note():
    data       = request.get_json()
    user_id    = session.get("user_id", 1)
    habit_name = data.get("habit")
    content    = data.get("content", "").strip()

    if not content:
        return jsonify({"error": "empty"}), 400

    created_at = datetime.now().strftime("%d %b %Y, %H:%M")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO diary (user_id, habit_name, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, habit_name, content, created_at)
    )
    conn.commit()
    note_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": note_id, "content": content, "created_at": created_at})

@app.route("/get_notes/<habit_name>")
def get_notes(habit_name):
    user_id = session.get("user_id", 1)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, content, created_at FROM diary WHERE user_id=? AND habit_name=? ORDER BY id DESC",
        (user_id, habit_name)
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "content": r[1], "created_at": r[2]} for r in rows])

@app.route("/delete_note", methods=["POST"])
def delete_note():
    note_id = request.get_json().get("id")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM diary WHERE id=?", (note_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ------------------ AI ------------------

@app.route("/ai")
def ai():
    return render_template("ai.html", user=session.get("user"))

@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    messages = data.get("messages", [])
    user_name = session.get("user")
    user_id   = session.get("user_id", 1)

    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT habit_name, last_used, money_spent, time_spent FROM habits WHERE user_id=?", (user_id,))
    habits = cursor.fetchall()
    conn.close()

    habit_context = ""
    lines = []
    for h in habits:
        name, last_used, money_per_day, time_per_day = h
        if not name or not last_used:
            continue
        try:
            diff  = datetime.now() - datetime.fromisoformat(last_used)
            money_saved = round((diff.total_seconds() / 86400) * float(money_per_day or 0), 2)
            lines.append(
                f"- {name}: {diff.days} days and {int(diff.seconds/3600)} hours clean, "
                f"${money_saved} saved (${money_per_day}/day habit), {time_per_day} min/day saved"
            )
        except:
            pass
    if lines:
        habit_context = "\n\nUSER'S CURRENT PROGRESS (use when relevant):\n" + "\n".join(lines)

    system = GROQ_SYSTEM
    if user_name:
        system += f"\n\nThe user's name is {user_name}. Address them by name occasionally."
    system += habit_context

    payload = _json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 500,
        "temperature": 0.75
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "HealMind/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            result = _json.loads(res.read().decode("utf-8"))
        return jsonify({"reply": result["choices"][0]["message"]["content"]})
    except Exception as e:
        return jsonify({"reply": f"API error: {e}"}), 500

# ------------------ ACCOUNT ------------------

@app.route("/account")
def account():
    if not session.get("user"):
        return redirect("/login")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM users WHERE id=?", (session.get("user_id"),))
    user_data = cursor.fetchone()
    conn.close()
    return render_template("account.html", user=session.get("user"), user_data=user_data)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
