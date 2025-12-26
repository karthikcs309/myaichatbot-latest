import os
from flask import Flask, request, jsonify, render_template, session
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")

# Configure Gemini (ENV VAR ONLY)
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-3-flash-preview")

@app.route("/")
def home():
    session.setdefault("history", [])
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    history = session.get("history", [])

    try:
        response = model.generate_content(user_input)
        bot_text = response.text

        history.append({"role": "user", "text": user_input})
        history.append({"role": "model", "text": bot_text})

        session["history"] = history[-20:]

        return jsonify({"response": bot_text})

    except Exception as e:
        print(e)
        return jsonify({"response": "Gemini error. Try again."}), 500

@app.route("/clear", methods=["POST"])
def clear():
    session.clear()
    return jsonify({"success": True})
