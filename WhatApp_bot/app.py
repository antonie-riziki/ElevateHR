import os
import json
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime, timedelta
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
app = Flask(__name__)

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize Twilio client
if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    logging.error("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set. Twilio functionality will be limited.")
    client = None
else:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Replace the Gemini model initialization section (around line 40-55) with this:

# Initialize Gemini AI
if not GEMINI_API_KEY:
    logging.error("GOOGLE_API_KEY not set. AI features will not work.")
    model = None
else:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        # Updated model name - try these in order of preference
        model_names = [
            'gemini-1.5-flash',
            'gemini-1.5-pro', 
            'gemini-1.0-pro',
            'gemini-pro'
        ]
        
        model = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )
                logging.info(f"Gemini AI model '{model_name}' initialized successfully.")
                break
            except Exception as e:
                logging.warning(f"Failed to initialize model '{model_name}': {e}")
                continue
        
        if model is None:
            logging.error("Failed to initialize any Gemini model. Listing available models...")
            try:
                available_models = genai.list_models()
                logging.info("Available models:")
                for m in available_models:
                    if 'generateContent' in m.supported_generation_methods:
                        logging.info(f"  - {m.name}")
            except Exception as e:
                logging.error(f"Could not list available models: {e}")
                
    except Exception as e:
        logging.error(f"Failed to configure Gemini API: {e}")
        model = None

# User session storage (WARNING: NOT PRODUCTION READY - use a database like Redis/PostgreSQL for persistence)
user_sessions = {}
SESSION_TIMEOUT_MINUTES = 30 # Session will expire after 30 minutes of inactivity

# HR Knowledge Base (kept as is, assume it's comprehensive enough for context)
HR_KNOWLEDGE_BASE = """
COMPANY HR POLICIES AND INFORMATION:

LEAVE POLICY:
- 20 paid vacation days per year
- 10 sick leave days per year
- 12 national holidays
- Maternity leave: 16 weeks paid
- Paternity leave: 4 weeks paid
- Bereavement leave: 5 days paid
- Leave applications must be submitted 2 weeks in advance (except sick leave)
- Portal link: https://company-portal.com/leave-application

PAYROLL INFORMATION:
- Pay date: 25th of each month
- Pay period: 1st to last day of the month
- Salary slips available in employee portal
- Tax deductions are processed automatically
- Overtime: 1.5x regular rate for hours over 40/week
- Bonus payments: Quarterly performance bonus + annual bonus

WORKING HOURS:
- Standard hours: 9:00 AM - 5:00 PM
- Flexible timing: 8:00 AM - 6:00 PM window
- Core hours: 10:00 AM - 3:00 PM (mandatory presence)
- Lunch break: 1 hour
- Weekly hours: 40 hours standard
- Remote work: 2 days per week with approval

HEALTH INSURANCE:
- Coverage: Employee + Family
- Premium split: 80% company, 20% employee
- Network hospitals: 500+ nationwide
- Annual health checkup included
- Dental and vision coverage included
- Maternity benefits available
- Insurance helpline: 1-800-555-0123

COMPANY BENEFITS:
- Health insurance (medical, dental, vision)
- Retirement 401(k) with 6% company match
- Life insurance (2x annual salary)
- Employee assistance program
- Professional development fund: $2000/year
- Gym membership reimbursement
- Transportation allowance
- Meal vouchers

DOCUMENT REQUESTS:
- Salary certificate: 2-3 business days
- Employment letter: 2-3 business days
- Experience certificate: 3-5 business days
- Tax documents: Available in portal
- All documents sent to registered email

CONTACT INFORMATION:
- HR Email: hr@company.com
- HR Phone: +1-555-0199
- Emergency contact: +1-555-0911
- Office hours: 9 AM - 5 PM, Monday-Friday

PERFORMANCE REVIEW:
- Annual performance reviews in December
- Mid-year check-ins in June
- 360-degree feedback process
- Goal setting and tracking quarterly
- Performance improvement plans when needed

TRAINING AND DEVELOPMENT:
- Onboarding program: 2 weeks
- Mandatory compliance training: Annual
- Leadership development programs
- Technical skills training budget
- Conference attendance support
- Mentorship programs available

CODE OF CONDUCT:
- Professional behavior expected at all times
- Zero tolerance for harassment or discrimination
- Confidentiality agreements must be maintained
- Dress code: Business casual
- Social media guidelines apply
- Conflict of interest policies
"""

def get_gemini_response(user_message, user_context=""):
    """Get response from Gemini AI with HR context."""
    if model is None:
        return "AI is not configured. Please check GOOGLE_API_KEY environment variable."

    prompt = f"""
    You are anElevateHR for our company. Use the following company information to answer employee questions accurately and professionally.

    COMPANY HR INFORMATION:
    {HR_KNOWLEDGE_BASE}

    ---
    USER CONTEXT (previous conversation or identified employee ID):
    {user_context}
    ---

    EMPLOYEE QUESTION: {user_message}

    INSTRUCTIONS:
    1. Answer strictly based on the "COMPANY HR INFORMATION" provided above. Do not make up information.
    2. Be helpful, professional, and concise. Keep responses under 320 characters for optimal WhatsApp display.
    3. If the "EMPLOYEE QUESTION" is about *personal employee data* (e.g., specific salary amount, personal leave balance, individual bonus details), and an "Employee ID" is *not* present in the USER CONTEXT, you MUST politely ask the user for their Employee ID. For example: "For personal details like your salary, please provide your Employee ID. Type 'My Employee ID is [YourID]'".
    4. If the information requested is not in the "COMPANY HR INFORMATION", politely state that you don't have that specific detail and direct them to contact HR directly at hr@company.com or call +1-555-0199.
    5. Avoid overly casual language or excessive emojis. Use them sparingly for readability (e.g., a checkmark for completion).
    6. Always end your response with "Type 'menu' for main options or ask me anything else!"
    7. Prioritize answering the question if the information is available, otherwise follow instruction 3 or 4.

    Provide a helpful response:
    """

    try:
        response = model.generate_content(prompt)
        # Check if the response is empty or contains problematic content
        if not response.text.strip():
            logging.warning("Gemini returned an empty response.")
            return "I'm sorry, I couldn't generate a response for that. Please try rephrasing your question. Type 'menu' for main options or ask me anything else!"
        return response.text.strip()
    except genai.types.BlockedPromptException as e:
        logging.warning(f"Gemini prompt blocked: {e}")
        return "I cannot respond to that query as it violates safety guidelines. Please ask a different question. Type 'menu' for main options or ask me anything else!"
    except Exception as e:
        logging.error(f"Error getting Gemini response: {e}")
        return "I'm having trouble processing your request right now. Please try again or contact HR directly at hr@company.com. Type 'menu' for main options or ask me anything else!"

def is_structured_command(message):
    """Check if message is a structured menu command or a greeting/menu trigger."""
    lower_msg = message.strip().lower()
    return lower_msg in ['1', '2', '3', '4', '5', 'menu', 'hi', 'hello', 'hey', 'start']

def extract_employee_id(message):
    """
    Extract employee ID from message.
    Looks for patterns like "EMP123", "Employee ID: 456", "My ID is 789", or standalone 3-6 digit numbers.
    """
    message_upper = message.upper()
    
    # Pattern 1: EMP followed by digits (e.g., EMP001, EMP1234)
    match = re.search(r'\bEMP\d{3,6}\b', message_upper)
    if match:
        return match.group()
    
    # Pattern 2: "ID is" or "my ID" followed by digits (e.g., "My ID is 123", "ID is 456")
    match = re.search(r'(?:ID IS|MY ID IS)\s*(\d{3,6})\b', message_upper)
    if match:
        return f"EMP{match.group(1)}"
    
    # Pattern 3: Standalone 3-6 digit numbers, but only if explicitly asked for or mentioned with "employee"
    # This is to reduce false positives from random numbers.
    # Refine this based on actual expected employee ID formats.
    # For a real system, you'd integrate with an SSO or employee database.
    if any(keyword in message_upper for keyword in ["EMPLOYEE", "EMP"]):
        match = re.search(r'\b\d{3,6}\b', message_upper)
        if match:
            return f"EMP{match.group()}"
            
    return None

def send_main_menu(to_number):
    """Send the main menu with interactive options."""
    if client is None:
        logging.error("Twilio client not initialized, cannot send menu.")
        return False

    try:
        message_body = (
            "🏢 *HR Assistant Bot*\n\n"
            "Hello! I'm your AI-powered HR assistant. You can:\n\n"
            "🎯 *Quick Options:*\n"
            "1️⃣ Payroll Inquiry\n"
            "2️⃣ Leave Request\n"
            "3️⃣ Company Policies\n"
            "4️⃣ Document Request\n"
            "5️⃣ Support & Feedback\n\n"
            "💬 *Or just ask me anything!* (e.g., \"When is payday?\", \"How many vacation days do I have?\")\n"
            "Type a number or ask your question!"
        )
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body=message_body
        )
        logging.info(f"Main menu sent to {to_number}")
        return True
    except TwilioRestException as e:
        logging.error(f"Twilio error sending main menu to {to_number}: {e}")
        return False
    except Exception as e:
        logging.error(f"Error sending main menu to {to_number}: {e}")
        return False

def get_user_session(phone_number):
    """Get or create user session, and manage session timeout."""
    now = datetime.now()
    if phone_number not in user_sessions or \
       (now - user_sessions[phone_number]['last_active']) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        logging.info(f"Initializing or resetting session for {phone_number}")
        user_sessions[phone_number] = {
            'state': 'initial', # 'initial', 'ai_mode', 'awaiting_employee_id', 'payroll_inquiry', etc.
            'last_action': None,
            'employee_id': None,
            'conversation_history': [],
            'last_active': now
        }
    user_sessions[phone_number]['last_active'] = now # Update last active timestamp
    return user_sessions[phone_number]

def update_user_session(phone_number, **kwargs):
    """Update user session with provided key-value pairs."""
    session = get_user_session(phone_number) # Ensures session exists and last_active is updated
    for key, value in kwargs.items():
        if key in session:
            session[key] = value
        else:
            logging.warning(f"Attempted to update non-existent session key: {key} for {phone_number}")

def add_to_conversation_history(phone_number, user_message, bot_response):
    """Add message to conversation history for context."""
    session = get_user_session(phone_number)
    session['conversation_history'].append({
        'user': user_message,
        'bot': bot_response,
        'timestamp': datetime.now().isoformat()
    })
    # Keep only last 3 conversations (user query + bot response pairs) for context to manage token limits
    if len(session['conversation_history']) > 3:
        session['conversation_history'] = session['conversation_history'][-3:]

def get_conversation_context(phone_number):
    """Generate a context string from the session history for the AI."""
    session = get_user_session(phone_number)
    context = ""
    
    if session['employee_id']:
        context += f"Employee ID: {session['employee_id']}\n"
    
    if session['conversation_history']:
        context += "Recent conversation history (user-bot exchanges):\n"
        for conv in session['conversation_history']:
            context += f"User: {conv['user']}\nBot: {conv['bot']}\n"
    
    return context

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    """Handle incoming WhatsApp messages with AI capabilities."""
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")
    
    logging.info(f"Received message from {from_number}: {incoming_msg}")
    
    # Get/update user session
    session = get_user_session(from_number)
    
    resp = MessagingResponse()
    
    # Clean up incoming message - remove common trailing phrases from WhatsApp quick replies
    if "Type a number or ask your question!" in incoming_msg:
        incoming_msg = incoming_msg.replace("Type a number or ask your question!", "").strip()

    # Handle greetings and explicit menu requests
    if incoming_msg.lower() in ["hi", "hello", "hey", "start", "menu"]:
        send_main_menu(from_number)
        update_user_session(from_number, state='ai_mode', last_action='sent_menu')
        return str(resp)

    # Process structured menu commands
    if incoming_msg in ['1', '2', '3', '4', '5']:
        user_query_for_ai = ""
        if incoming_msg == '1':
            user_query_for_ai = "Tell me about payroll information, including pay date and how to access salary slips."
            update_user_session(from_number, state='payroll_inquiry', last_action='payroll_menu_selected')
        elif incoming_msg == '2':
            user_query_for_ai = "Explain the leave policy, types of leave available, and how to apply for leave."
            update_user_session(from_number, state='leave_request', last_action='leave_menu_selected')
        elif incoming_msg == '3':
            user_query_for_ai = "Summarize the main company policies, like working hours and remote work."
            update_user_session(from_number, state='company_policies', last_action='policies_menu_selected')
        elif incoming_msg == '4':
            user_query_for_ai = "What is the process for requesting documents like salary certificates or employment letters?"
            update_user_session(from_number, state='document_request', last_action='documents_menu_selected')
        elif incoming_msg == '5':
            user_query_for_ai = "How can I provide feedback or get additional support from HR?"
            update_user_session(from_number, state='support_feedback', last_action='support_menu_selected')
        
        # Get AI response for the structured query
        context = get_conversation_context(from_number)
        if user_query_for_ai:
            ai_response = get_gemini_response(user_query_for_ai, context)
        else:
            ai_response = "Sorry, I couldn't understand your menu selection. Type 'menu' to see options."
        resp.message(ai_response)
        add_to_conversation_history(from_number, incoming_msg, ai_response)
        return str(resp)

    # Handle natural language queries and general AI mode
    else:
        # Attempt to extract employee ID from *any* incoming message if not already known
        if not session['employee_id']:
            emp_id = extract_employee_id(incoming_msg)
            if emp_id:
                update_user_session(from_number, employee_id=emp_id, state='ai_mode')
                logging.info(f"Employee ID '{emp_id}' identified for {from_number}")
        
        # Get AI response using current context
        context = get_conversation_context(from_number)
        ai_response = get_gemini_response(incoming_msg, context)
        
        resp.message(ai_response)
        add_to_conversation_history(from_number, incoming_msg, ai_response)

    return str(resp)

@app.route("/", methods=["GET"])
def home():
    """Health check endpoint."""
    return """
    <h1>AI-Powered HR WhatsApp Bot</h1>
    <p>Status: Running ✅</p>
    <p>Features:</p>
    <ul>
        <li>🤖 Google Gemini AI Integration</li>
        <li>💬 Natural Language Processing</li>
        <li>📋 Structured Menu Options</li>
        <li>📊 Session Management (In-memory, NOT production-ready)</li>
        <li>🔍 Basic Employee ID Recognition</li>
        <li>🛡️ Improved Error Handling</li>
    </ul>
    """

@app.route("/sessions", methods=["GET"])
def view_sessions():
    """
    WARNING: This endpoint exposes sensitive user session data and should be
    DISABLED or SECURED in a production environment. For debugging ONLY.
    """
    clean_sessions = {}
    for num, sess in user_sessions.items():
        # Convert datetime objects to string for JSON serialization
        clean_sessions[num] = {k: str(v) if isinstance(v, datetime) else v for k, v in sess.items()}
    
    return jsonify(clean_sessions)

if __name__ == "__main__":
    logging.info("🚀 Starting AI-Powered HR WhatsApp Bot...")
    logging.info("Required environment variables:")
    logging.info(f"✅ TWILIO_ACCOUNT_SID: {'Set' if TWILIO_ACCOUNT_SID else 'NOT SET'}")
    logging.info(f"✅ TWILIO_AUTH_TOKEN: {'Set' if TWILIO_AUTH_TOKEN else 'NOT SET'}") 
    logging.info(f"✅ TWILIO_WHATSAPP_NUMBER: {'Set' if TWILIO_WHATSAPP_NUMBER else 'NOT SET'}")
    logging.info(f"🆕 GOOGLE_API_KEY: {'Set' if GEMINI_API_KEY else 'NOT SET'}")
    logging.info("")
    
    if not GEMINI_API_KEY:
        logging.warning("⚠️ WARNING: GOOGLE_API_KEY not found. AI features will not work.")
    else:
        logging.info("🤖 Gemini AI: Attempting to initialize...")
    
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
        logging.warning("⚠️ WARNING: Twilio credentials not fully set. WhatsApp messaging may not work.")

    app.run(debug=True, port=5000)