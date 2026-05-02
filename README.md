# 🩺 Patient Chatbot + Smart Shield Security System

🚀 A Full Stack AI-powered Patient Chatbot with Authentication and ML-based Security System.

---

## 📌 Features

### 💬 Chatbot

* Answer clinic FAQs (timings, location, insurance)
* Symptom-based triage (fever, cough, rash, etc.)
* Emergency red-flag detection 🚨
* Appointment booking system 📅

### 🔐 Authentication

* User Login & Register system
* Session-based authentication

### 🧠 AI Logic

* Intent detection using NLP techniques
* Rule-based + pattern matching chatbot
* Step-by-step triage system

### 🛡️ Smart Shield Security

* ML-based attack detection (SVM, Random Forest, Logistic Regression)
* Detects SQL Injection, XSS, Path Traversal
* Auto IP blocking 🚫
* Rate limiting
* Blockchain-style tamper-proof logs

---

## 🏗️ Project Structure

```
project-folder/
│
├── templates/
│   ├── chatbot.html
│   ├── login.html
│   └── register.html
│
├── static/
│   └── images/
│
├── screenshots/
│   ├── chatbot.png
│   ├── login.png
│   └── register.png
│
├── app.py
├── chatbot_logic.py
├── smart_shield.py
└── README.md
```

---

## ⚙️ Installation

### 1. Clone Repository

```
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Create Virtual Environment

```
python -m venv .venv
```

### 3. Activate Environment

**Windows:**

```
.venv\Scripts\activate
```

**Mac/Linux:**

```
source .venv/bin/activate
```

### 4. Install Dependencies

```
pip install flask scikit-learn pandas requests
```

---

## ▶️ Run the Project

### Start Chatbot

```
python app.py
```

Open browser:

```
http://127.0.0.1:5000
```

---

### Start Smart Shield

```
python smart_shield.py --demo
```

---
<h2 align="center">💬 Chatbot UI</h2>

<p align="center">
  <img src="screenshots/chatbot.png" width="500"/>
</p>

---

## 🧠 How It Works

1. User logs in
2. Sends message
3. Intent detection runs
4. Based on input:

   * FAQ → direct answer
   * Symptom → triage flow
   * Appointment → booking flow

---

## 📊 Example Use Cases

* Ask: “clinic timings” → get instant reply
* Type: “fever” → triage starts
* Book appointment → guided flow
* Attack request → Smart Shield blocks

---

## 🚀 Future Improvements

* Password hashing (bcrypt)
* Deploy to cloud (Vercel / AWS)
* AI integration (OpenAI / Gemini)
* Admin dashboard
* Mobile responsive UI

---

## 👨‍💻 Author

Sanjeevi Kumar
AI & Data Science Student
Full Stack + AI Developer

---

## ⚠️ Disclaimer

This chatbot:

* ❌ Does NOT provide medical diagnosis
* ✅ Only gives general guidance
* 🚨 For emergencies call **108 (India)**

---

## ⭐ Support

If you like this project:

* Star ⭐ the repo
* Fork 🍴 it
* Share 🚀

---
