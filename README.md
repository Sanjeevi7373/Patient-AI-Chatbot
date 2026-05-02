🩺 Patient Chatbot + Smart Shield Security System

🚀 A Full Stack AI-powered Patient Chatbot with:

🔐 User Authentication (Login/Register)
🤖 Intelligent Chatbot (FAQ + Triage + Appointment Booking)
🧠 AI-based Symptom Analysis
🛡️ Smart Shield (ML-based Web Attack Detection System)
📌 Features
💬 Chatbot System
Answer clinic FAQs (timings, location, insurance, etc.)
Symptom-based triage (fever, cough, rash, etc.)
Emergency red-flag detection 🚨
Appointment booking flow 📅
🔐 Authentication System
Login & Register pages
Session-based authentication
Secure user handling (basic implementation)
🧠 AI Logic
Intent detection using NLP techniques
Rule-based + pattern matching chatbot
Step-by-step triage questioning system
🛡️ Smart Shield (Advanced)
ML models (SVM, Random Forest, Logistic Regression)
Attack detection (SQL Injection, XSS, Path Traversal)
Auto IP blocking 🚫
Blockchain-style tamper-proof logging
Rate limiting protection
🏗️ Project Structure
📦 patient-chatbot
 ┣ 📂 templates
 ┃ ┣ chatbot.html
 ┃ ┣ login.html
 ┃ ┗ register.html
 ┣ 📂 static
 ┃ ┗ images/
 ┣ app.py
 ┣ chatbot_logic.py
 ┣ smart_shield.py
 ┗ README.md
⚙️ Installation & Setup
1️⃣ Clone Repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
2️⃣ Create Virtual Environment
python -m venv .venv
3️⃣ Activate Environment

Windows:

.venv\Scripts\activate

Mac/Linux:

source .venv/bin/activate
4️⃣ Install Dependencies
pip install flask scikit-learn pandas requests
▶️ Run the Application
Start Chatbot
python app.py

👉 Open in browser:

http://127.0.0.1:5000
Start Smart Shield (Security System)
python smart_shield.py --demo
🧠 How It Works
🔹 Chat Flow
User logs in
Sends message
Intent detection runs
Based on input:
FAQ → direct answer
Symptom → triage flow
Appointment → booking flow

👉 Example UI handling messages

🔹 Triage System
Detect symptoms like:
fever
cough
stomach pain
Ask dynamic questions
Provide:
✅ Self-care
🏥 Clinic visit
🚨 Emergency
🔹 Smart Shield Security
Captures HTTP requests
Extracts features
Runs ML models
If attack detected:
Logs in blockchain
Blocks IP
Returns response
🖥️ Screens
🔐 Login Page

👉 Stylish UI with background & secure input

📝 Register Page

👉 New user onboarding system

💬 Chatbot UI

👉 Modern chat interface with message bubbles

📊 Example Use Cases

✔ Patient asks: “clinic timings” → gets answer
✔ User types: “fever” → triage starts
✔ User books appointment → step-by-step flow
✔ Hacker sends SQL injection → Smart Shield blocks
<h2 align="center">💬 Chatbot UI</h2>

<p align="center">
  <img src="screenshots/chatbot.png" width="500"/>
</p>

🚀 Future Improvements
🔐 Password hashing (bcrypt)
🌐 Deploy on Vercel / AWS
🤖 Integrate Gemini / OpenAI API
📊 Dashboard for analytics
📱 Mobile responsive UI
👨‍💻 Author

Sanjeevi Kumar
🎓 AI & Data Science Student
💡 Full Stack + AI Developer

⭐ Support

If you like this project:
👉 Star ⭐ the repo
👉 Fork 🍴 it
👉 Build your own version 🚀

⚠️ Disclaimer

This chatbot:

❌ Does NOT provide medical diagnosis
✅ Only gives general guidance
🚨 For emergencies → Call 108 (India)
