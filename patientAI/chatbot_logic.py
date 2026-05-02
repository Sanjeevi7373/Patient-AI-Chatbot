# chatbot_logic.py

import re
import uuid
from typing import List, Dict, Union, Callable, Any

# -----------------------------------------------------------------------------
# Knowledge Base (FAQ)

FAQ_KB = [
    {"intents": ["timings", "hours", "open", "closing", "working hours"],
     "answer": "⏰ Our clinic is open Mon–Sat, 8:00 AM – 6:00 PM. Sundays and public holidays: emergency only."},
    {"intents": ["hii", "hello", "hi"],
     "answer": "👋 Hello! How can I help you today? You can ask about appointments, clinic hours, insurance, or start a symptom check by mentioning 'fever', 'cough', 'rash', 'stomach pain', or 'dizziness'."},
    {"intents": ["appointment", "book", "reschedule", "cancel"],
     "answer": "📅 To book or reschedule an appointment, share your preferred date/time and doctor. We will confirm availability or suggest the next slot."},
    {"intents": ["location", "address", "where"],
     "answer": "📍 We are located at 123 Health Park Road,T.nagar,chennai. Landmark: opposite Central Bus Stand. Parking available."},
    {"intents": ["insurance", "cashless", "coverage", "claims"],
     "answer": "💳 We support major insurers (ABC, XYZ, MediCare+). Bring your insurance card and a valid ID. For cashless, pre-authorization may be required."},
    {"intents": ["reports", "lab results", "test results"],
     "answer": "🧪 Lab reports are usually ready within 24–48 hours. You can access them via the patient portal or at the Lab Helpdesk with your patient ID."},
    {"intents": ["prescription", "refill", "medicines"],
     "answer": "💊 For prescription refills, please share your patient ID and last visit date. A clinician will review within 1 working day."},
    {"intents": ["contact", "phone", "call"],
     "answer": "☎ Front desk: 7373869283 (8 AM–6 PM). Emergency: 108 (India) or your local emergency number."},
    {"intents": ["billing", "payment", "fees", "charges"],
     "answer": "💰 Billing desk is open Mon–Sat, 8 AM – 6 PM. We accept cash, cards, and UPI. Detailed invoices are provided."},
    {"intents": ["vaccination", "immunization"],
     "answer": "💉 We provide all major vaccinations (child & adult). Please bring your vaccination card. Walk-ins available for flu shots."},
    {"intents": ["diet", "nutrition", "food"],
     "answer": "🥗 For a balanced diet: eat fresh fruits, vegetables, lean proteins, whole grains, and hydrate well. Reduce sugar and fried foods."},
    {"intents": ["exercise", "fitness", "workout"],
     "answer": "🏃 30 minutes of daily exercise improves immunity and heart health. Walking, yoga, or gym workouts are recommended."},
    {"intents": ["pediatrics", "child", "kids doctor"],
     "answer": "👶 Our pediatric clinic runs Mon–Sat, 9 AM – 4 PM. Specialists are available for vaccinations, growth monitoring, and child care."},
    {"intents": ["geriatrics", "elderly", "senior citizen"],
     "answer": "👵 Elderly care services include physiotherapy, chronic disease management, and counseling. Home visit services are also available."},
    {"intents": ["mental health", "psychiatrist", "psychologist", "counseling"],
     "answer": "🧠 Our mental health department offers counseling, therapy, and psychiatry services. Appointments can be scheduled confidentially."},
]

# -----------------------------------------------------------------------------
# Synonyms (expanded)
SYNONYMS = {
    "appointment": ["appointment", "book", "booking", "slot", "reschedule", "cancel"],
    "hours": ["timings", "hours", "open", "closing", "working hours"],
    "location": ["location", "address", "where"],
    "insurance": ["insurance", "cashless", "coverage", "claim", "claims"],
    "reports": ["report", "reports", "lab results", "test results", "labs"],
    "prescription": ["prescription", "refill", "medicines", "medicine"],
    "contact": ["contact", "phone", "call", "number"],
    "billing": ["billing", "fees", "charges", "payment"],
    "vaccination": ["vaccination", "immunization", "flu shot"],
    "diet": ["diet", "nutrition", "food", "meal"],
    "exercise": ["exercise", "fitness", "workout", "gym"],
    "pediatrics": ["pediatrics", "kids", "child", "baby"],
    "geriatrics": ["geriatrics", "elderly", "senior"],
    "mental": ["mental", "psychologist", "psychiatrist", "counseling"],
}

# -----------------------------------------------------------------------------
# Emergency Red Flags (expanded)
RED_FLAGS = [
    "chest pain", "severe bleeding", "shortness of breath", "loss of consciousness",
    "confusion", "severe headache", "sudden weakness", "high fever",
    "persistent vomiting", "seizure", "pregnancy bleeding", "severe abdominal pain",
    "dizziness fainting", "stroke", "heart attack",
]

# -----------------------------------------------------------------------------
# Triage patterns
TRIAGE_PATTERNS = [
    {"key": "fever", "regex": re.compile(r"\b(fever|temperature)\b", re.I)},
    {"key": "cough", "regex": re.compile(r"\b(cough|cold|throat)\b", re.I)},
    {"key": "stomach", "regex": re.compile(r"\b(stomach|abdominal|tummy)\b", re.I)},
    {"key": "rash", "regex": re.compile(r"\b(rash|skin|itchy)\b", re.I)},
    {"key": "dizzy", "regex": re.compile(r"\b(dizzy|vertigo|faint)\b", re.I)},
]

# -----------------------------------------------------------------------------
# Triage rules (simplified for non-interactive backend)

def get_fever_advice(answers: Dict[str, str]):
    t = float(answers.get("What's your temperature (°C)?", "0"))
    days = float(answers.get("How long has it lasted (days)?", "0"))
    severe = answers.get("Any severe headache, neck stiffness, or rash? (yes/no)", "no").lower()

    if t >= 39.5 or "yes" in severe:
        return {"level": "urgent", "message": "High fever or red-flag features. Seek urgent evaluation today."}
    if t >= 38 or days >= 3:
        return {"level": "clinic", "message": "Consider a clinic visit for assessment and tests."}
    return {"level": "self-care", "message": "Hydration, rest, and paracetamol as directed. Monitor for 24–48 hours."}

def get_cough_advice(answers: Dict[str, str]):
    sob = answers.get("Is there shortness of breath or chest pain? (yes/no)", "no").lower()
    fever = answers.get("Any fever? (yes/no)", "no").lower()
    dur = float(answers.get("Duration in days?", "0"))

    if "yes" in sob: return {"level": "urgent", "message": "Breathing issues/chest pain → seek urgent care now."}
    if "yes" in fever or dur >= 10: return {"level": "clinic", "message": "Clinic review recommended for persistent cough or fever."}
    return {"level": "self-care", "message": "Fluids, rest, honey/lozenges, and monitor. See a doctor if it worsens."}

def get_stomach_advice(answers: Dict[str, str]):
    vomit = answers.get("Any vomiting or blood in stool? (yes/no)", "no").lower()
    if "yes" in vomit: return {"level": "urgent", "message": "Severe abdominal pain with vomiting → urgent evaluation required."}
    return {"level": "clinic", "message": "Clinic visit advised for abdominal pain. Could be gastritis, infection, or other causes."}

def get_rash_advice(answers: Dict[str, str]):
    fever = answers.get("Any fever or breathing difficulty? (yes/no)", "no").lower()
    if "yes" in fever: return {"level": "urgent", "message": "Rash with fever/breathing issues → possible allergy/infection, urgent care."}
    return {"level": "self-care", "message": "Mild rash → keep skin clean, avoid scratching, use soothing lotion. If worsening, visit clinic."}

def get_dizzy_advice(answers: Dict[str, str]):
    faint = answers.get("Did you faint or lose consciousness? (yes/no)", "no").lower()
    if "yes" in faint: return {"level": "urgent", "message": "Fainting with dizziness → urgent evaluation required."}
    return {"level": "clinic", "message": "Dizziness may be due to dehydration, low BP, or inner ear issues. Clinic check-up recommended."}


TRIAGE_RULES: List[Dict[str, Union[str, List[str], Callable[[Dict[str, str]], Dict[str, str]]]]] = [
    {"key": "fever", "questions": ["What's your temperature (°C)?", "How long has it lasted (days)?", "Any severe headache, neck stiffness, or rash? (yes/no)"], "advice": get_fever_advice},
    {"key": "cough", "questions": ["Is there shortness of breath or chest pain? (yes/no)", "Any fever? (yes/no)", "Duration in days?"], "advice": get_cough_advice},
    {"key": "stomach", "questions": ["Where is the pain located (upper/lower abdomen)?", "Duration in hours?", "Any vomiting or blood in stool? (yes/no)"], "advice": get_stomach_advice},
    {"key": "rash", "questions": ["What type of rash? (red spots, blisters, itching, swelling)", "Duration in days?", "Any fever or breathing difficulty? (yes/no)"], "advice": get_rash_advice},
    {"key": "dizzy", "questions": ["Did you faint or lose consciousness? (yes/no)", "Any chest pain, weakness, or vision changes? (yes/no)", "Duration in hours?"], "advice": get_dizzy_advice},
]
# Type for mypy, not used at runtime, but helpful for clarity
TriageRuleType = Dict[str, Union[str, List[str], Callable[[Dict[str, str]], Dict[str, str]]]]
TRIAGE_RULES_MAPPED: Dict[str, TriageRuleType] = {rule['key']: rule for rule in TRIAGE_RULES}


# -----------------------------------------------------------------------------
# Utils

def normalize(text: str) -> str:
    """Normalizes text for comparison."""
    # Remove non-alphanumeric characters except spaces
    return re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()

def contains_synonym(text: str, synonyms: List[str]) -> bool:
    """Checks if the text contains any of the synonyms as a whole word."""
    return any(re.search(r'\b' + re.escape(word) + r'\b', text, re.I) for word in synonyms)

def detect_intent(user_text: str) -> Dict[str, Any]:
    """Detects the primary intent from the user's text."""
    t = normalize(user_text)

    # 1. Red Flags
    for rf in RED_FLAGS:
        if rf in t:
            return {"type": "redflag", "match": rf}

    # 2. Triage Patterns
    for pattern in TRIAGE_PATTERNS:
        if pattern["regex"].search(user_text):
            return {"type": "triage", "key": pattern["key"]}

    # 3. FAQ Intents (Direct Match)
    for entry in FAQ_KB:
        if any(re.search(r'\b' + re.escape(k) + r'\b', t, re.I) for k in entry["intents"]):
            return {"type": "faq", "answer": entry["answer"], "intent": entry["intents"][0]}

    # 4. FAQ Synonyms
    for canonical, synonyms in SYNONYMS.items():
        if contains_synonym(t, synonyms):
            entry = next((e for e in FAQ_KB if canonical in e["intents"]), None)
            if entry:
                return {"type": "faq", "answer": entry["answer"], "intent": canonical}

    # 5. Unknown
    return {"type": "unknown"}

# chatbot_logic.py (Modified run_triage_step function)
# ... (rest of imports and definitions) ...

# patientAI/chatbot_logic.py (REPLACEMENT for run_triage_step function)

def run_triage_step(key: str, answers: Dict[str, str], current_answer: str) -> Dict[str, Any]:
    """
    Handles a single step of the triage process.
    The `answers` dictionary is modified in place.
    """
    rule = TRIAGE_RULES_MAPPED.get(key)
    if not rule:
        return {"next_step": -1, "response": "Error: Triage flow not found."}

    questions = rule['questions'] # type: ignore
    
    # 1. Determine which question the user is answering.
    # The step number stored in the session is 1-indexed. The index we need is len(answers).
    question_index_to_answer = len(answers)
    
    # 2. Store the current_answer against the previous question.
    if question_index_to_answer < len(questions): 
        # The question to answer is at this index.
        prev_question = questions[question_index_to_answer] # type: ignore
        answers[prev_question] = current_answer # Store the answer

    # 3. Check for Red Flags in the latest answer (Emergency Override)
    if any(rf in normalize(current_answer) for rf in RED_FLAGS):
        return {
            "next_step": -1,
            "response": "⚠ You mentioned a possible red flag. Please seek urgent medical care now.",
            "meta": {"level": "urgent"}
        }
        
    # 4. Determine the next step index and question to ask.
    next_question_index = len(answers) # Since we just added an answer, this is the index of the next question.

    if next_question_index < len(questions): # type: ignore
        # Ask the next question
        next_question = questions[next_question_index] # type: ignore
        return {
            "next_step": next_question_index + 1, # Return 1-indexed step number
            "response": next_question
        }
    else:
        # Triage completed, provide advice (All questions have been answered)
        advice_func = rule['advice'] # type: ignore
        advice = advice_func(answers)
        return {
            "next_step": -1, # End of flow
            "response": f"✅ Triage result: {advice['message']}",
            "meta": advice
        }

# ... (rest of chatbot_logic.py) ...

def start_appointment_flow():
    """Starts the appointment booking flow."""
    return {
        "next_step": 1,
        "response": "📅 Sure! What date would you prefer?",
        "data": {}
    }

def run_appointment_step(step: int, data: Dict[str, str], user_input: str) -> Dict[str, Any]:
    """Handles a single step in the appointment flow."""
    step_map = {
        1: ("date", "⏰ Great! At what time?"),
        2: ("time", "👨‍⚕️ Which doctor would you like to see?"),
        3: ("doctor", "✅ Appointment booked!\n- Doctor: {doctor}\n- Date: {date}\n- Time: {time}\n📍 Location: 123 Health Park Road, T.nagar,Chennai"),
    }

    if step not in step_map:
        return {"next_step": -1, "response": "Appointment error. Please start over."}

    field, next_prompt = step_map[step]
    
    # Store the user's input for the current step's field
    if step < 3:
        data[field] = user_input
    
    next_step = step + 1

    if next_step <= 3:
        # Move to the next step
        return {"next_step": next_step, "response": next_prompt, "data": data}
    else:
        # Final step (Confirmation)
        data['doctor'] = user_input # Store the final piece of data (doctor name)
        final_message = next_prompt.format(**data)
        return {"next_step": -1, "response": final_message, "data": data}