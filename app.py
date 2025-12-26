import os
import time
from flask import Flask, request, jsonify, render_template, session
from google import genai
from google.genai import types
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_2025_secure'  # Change for production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Increased to 50MB for Gemini 3

# --- CONFIGURATION (UPDATED FOR 2025) ---
GOOGLE_API_KEY = "AIzaSyAA2Iwnr8NjG-B7WRnLHjNvz10NszSrJJc"

# Initialize the new Client (replaces the old genai.configure)
client = genai.Client(api_key=GOOGLE_API_KEY)

# The latest model as of Dec 2025
MODEL_ID = 'gemini-3-flash-preview'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def home():
    if 'history' not in session:
        session['history'] = []
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"Uploading {filename} to Gemini 3...")
        
        # NEW SDK: Upload file
        # The new SDK handles uploads via client.files
        gemini_file = client.files.upload(path=filepath)
        
        # Wait for processing (Gemini 3 is faster, but we still check)
        while gemini_file.state == "PROCESSING":
            time.sleep(1)
            gemini_file = client.files.get(name=gemini_file.name)

        # Store the file name (ID) in session
        session['current_file_name'] = gemini_file.name
        session['current_file_display'] = filename
        
        return jsonify({"success": True, "filename": filename})

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    history = session.get('history', [])

    # NEW SDK: Construct the content list
    # We rebuild the conversation history for every request (stateless RESTful pattern)
    conversation_contents = []
    
    for entry in history:
        conversation_contents.append(
            types.Content(
                role=entry['role'],
                parts=[types.Part.from_text(text=entry['text'])]
            )
        )

    # Handle Pending File
    if 'current_file_name' in session:
        file_name = session.pop('current_file_name')
        file_display = session.pop('current_file_display')
        
        # Add the file to the user's message
        # In Gemini 3, we refer to the uploaded file by its name (URI equivalent)
        user_message_part = types.Part.from_text(text=user_input)
        file_part = types.Part.from_uri(file_uri=file_name, mime_type="application/pdf") # Auto-detect mime-type in prod
        
        conversation_contents.append(
            types.Content(role='user', parts=[file_part, user_message_part])
        )
        user_log_text = f"[Attached: {file_display}] {user_input}"
    else:
        conversation_contents.append(
            types.Content(role='user', parts=[types.Part.from_text(text=user_input)])
        )
        user_log_text = user_input

    try:
        # Generate Content with Gemini 3 Flash
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=conversation_contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=2048
            )
        )
        
        bot_text = response.text

        # Update History
        history.append({"role": "user", "text": user_log_text})
        history.append({"role": "model", "text": bot_text})
        
        # Keep history short (last 10 turns) to save tokens/session space
        if len(history) > 20: 
            history = history[-20:]
            
        session['history'] = history
        return jsonify({"response": bot_text})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"response": "I encountered an error connecting to Gemini 3. Please try again."}), 500

@app.route('/clear', methods=['POST'])
def clear_history():
    session.pop('history', None)
    session.pop('current_file_name', None)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run()
