# app.py

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from chatbot_logic import detect_intent, run_triage_step, run_appointment_step, start_appointment_flow, TRIAGE_RULES_MAPPED
import uuid

app = Flask(__name__)
# IMPORTANT: In a real app, use a long, complex secret key from environment variables
app.secret_key = 'super_secret_key_change_me' 

# Dummy User Database (In-Memory for this example)
USERS = {
    "testuser": {"password": "testpassword"} # In a real app, hash this password!
}

# -----------------------------------------------------------------------------
# Auth Routes (Register & Login)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return render_template('register.html', error="Username and password are required.")
        if username in USERS:
            return render_template('register.html', error="User already exists.")
        
        # In a real app, hash the password before storing!
        USERS[username] = {"password": password} 
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = USERS.get(username)
        if user and user["password"] == password: # In a real app, check HASH
            session['logged_in'] = True
            session['username'] = username
            # Initialize chat state for the user
            session['chat_state'] = {
                'messages': [{
                    'id': str(uuid.uuid4()),
                    'role': 'system',
                    'content': "👋 Welcome! I can help with clinic info, appointments, and basic triage (no diagnosis). If this is an emergency, call your local emergency number.",
                    'ts': datetime.now().strftime('%H:%M:%S')
                }],
                'triage_flow': None, # {'key': 'fever', 'answers': {}, 'step': 1}
                'appointment_flow': None # {'data': {}, 'step': 1}
            }
            return redirect(url_for('chatbot'))
        else:
            return render_template('login.html', error="Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('chat_state', None)
    return redirect(url_for('login'))

# -----------------------------------------------------------------------------
# Chatbot Route

@app.route('/')
def index():
    # If the user is logged in, send them to the chatbot.
    if session.get('logged_in'):
        return redirect(url_for('chatbot'))
    
    # If the user is NOT logged in, send them to the login page.
    return redirect(url_for('login')) # <--- This ensures login is the entry point

@app.route('/chatbot')
def chatbot():
    # This is the security check for the actual chat page.
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    state = session.get('chat_state', {'messages': []})
    return render_template('chatbot.html', messages=state['messages'])


@app.route('/chat', methods=['POST'])
# patientAI/app.py (REPLACEMENT for handle_chat route)

@app.route('/chat', methods=['POST'])
def handle_chat():
    # Authentication, input check, state retrieval (Keep existing code)
    if 'logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_input = request.json.get('message', '').strip()
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    state = session.get('chat_state')
    if not state:
        return jsonify({"error": "Chat state not initialized"}), 500

    messages = state['messages']
    triage_flow = state.get('triage_flow')
    appointment_flow = state.get('appointment_flow')
    
    # 1. Add user message
    user_msg = {
        'id': str(uuid.uuid4()), 
        'role': 'user', 
        'content': user_input, 
        'ts': datetime.now().strftime('%H:%M:%S')
    }
    messages.append(user_msg)
    
    bot_response = None
    new_triage_flow = triage_flow
    new_appointment_flow = appointment_flow
    
    # Always detect intent first. We will use this to check for interruption.
    intent = detect_intent(user_input)
    bot_meta = None
    
    # -----------------------------
    # 🔥 1. Handle Active Flows (Triage/Appointment)
    
    if triage_flow:
        # Check for interruption by a new strong intent (FAQ, Triage, or Redflag)
        if intent['type'] in ['faq', 'triage', 'redflag']:
            # INTERRUPTION: Triage flow is overridden.
            new_triage_flow = None
            # bot_response is left as None, allowing the code to proceed to block #2 
            # to process the new intent (e.g., 'book').
        else:
            # CONTINUE FLOW: Process user_input as an answer to the current triage question
            key = triage_flow['key']
            answers = triage_flow['answers']
            
            # NOTE: run_triage_step is fixed in chatbot_logic.py to correctly update answers
            result = run_triage_step(key, answers, user_input)
            bot_response = result['response']
            bot_meta = result.get('meta')

            if result['next_step'] != -1:
                new_triage_flow = {'key': key, 'answers': answers, 'step': result['next_step']}
            else:
                new_triage_flow = None
            
    elif appointment_flow:
        # APPOINTMENT FLOW: This is a purely sequential flow (no interruption check needed)
        step = appointment_flow['step']
        data = appointment_flow['data']
        
        result = run_appointment_step(step, data, user_input)
        bot_response = result['response']
        
        if result['next_step'] != -1:
            new_appointment_flow = {'step': result['next_step'], 'data': result['data']}
        else:
            new_appointment_flow = None

    # -----------------------------
    # 🔥 2. Handle New Intents (Only runs if no flow set bot_response, or if flow was interrupted)
    if not bot_response:
        
        if intent["type"] == "redflag":
            bot_response = f"⚠ You mentioned a potential red flag (\"{intent['match']}\"). Please seek emergency care immediately."
            bot_meta = {"level": "urgent"}
            
        elif intent["type"] == "faq":
            bot_response = intent["answer"]
            
            # If the FAQ is about appointment, start the flow
            if intent["intent"] in ["appointment", "book"]:
                start_flow = start_appointment_flow()
                bot_response = start_flow['response'] # Overwrite FAQ answer with flow start message
                new_appointment_flow = {'step': start_flow['next_step'], 'data': start_flow['data']}
                
        elif intent["type"] == "triage":
            key = intent['key']
            rule = TRIAGE_RULES_MAPPED.get(key)
            
            # Start Triage Flow
            if rule:
                start_question = rule['questions'][0] # type: ignore
                new_triage_flow = {'key': key, 'answers': {}, 'step': 1}
                bot_response = start_question
            
        else: # Unknown/Fallback
            bot_response = "🤖 I didn't fully get that. Could you rephrase or ask about appointments, hours, insurance, or start triage by mentioning 'fever', 'cough', 'rash', 'stomach pain', or 'dizziness'?"
            
    # -----------------------------
    # 3. Add bot message, update session, and return
    # ... (rest of bot_msg creation and session update) ...
    bot_msg = {
        'id': str(uuid.uuid4()),
        'role': 'assistant',
        'content': bot_response,
        'ts': datetime.now().strftime('%H:%M:%S'),
        'meta': bot_meta or {}
    }
    messages.append(bot_msg)

    session['chat_state'] = {
        'messages': messages,
        'triage_flow': new_triage_flow,
        'appointment_flow': new_appointment_flow
    }
    session.modified = True
    
    return jsonify({"messages": messages})

if __name__ == '__main__':
    # Run the app
    # You would need to create the /templates directory and the HTML files.
    app.run(debug=True)