import os
import json
import requests
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import google.generativeai as genai
from datetime import datetime
import re

load_dotenv()
app = Flask(__name__)

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# User session storage (in production, use a database)
user_sessions = {}

# HR Knowledge Base
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
- HR Email: hr@elevatehr.com
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
    try:
        prompt = f"""
        You are anElevateHR for our company. Use the following company information to answer employee questions accurately and professionally.

        COMPANY HR INFORMATION:
        {HR_KNOWLEDGE_BASE}

        USER CONTEXT: {user_context}

        EMPLOYEE QUESTION: {user_message}

        INSTRUCTIONS:
        1. Answer based on the company information provided above
        2. Be helpful, professional, and concise
        3. If you don't have specific information, direct them to contact HR directly
        4. Use emojis sparingly for better readability
        5. Keep responses under 1000 characters for WhatsApp
        6. If the question is about personal employee data (salary, personal leave balance, etc.), ask for employee ID
        7. Always end with "Type 'menu' for main options or ask me anything else!"

        Provide a helpful response:
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        print(f"Error getting Gemini response: {e}")
        return "I'm having trouble processing your request right now. Please try again or contact HR directly at hr@elevatehr.com"

def is_structured_command(message):
    """Check if message is a structured menu command."""
    return message.strip() in ['1', '2', '3', '4', '5'] or any(
        cmd in message.lower() for cmd in ['menu', 'hi', 'hello', 'hey', 'start']
    )

def extract_employee_id(message):
    """Extract employee ID from message."""
    # Look for patterns like EMP001, EMP123, or just numbers
    emp_pattern = r'EMP\d+'
    match = re.search(emp_pattern, message.upper())
    if match:
        return match.group()
    
    # Look for standalone numbers that might be employee IDs
    num_pattern = r'\b\d{3,6}\b'
    match = re.search(num_pattern, message)
    if match:
        return f"EMP{match.group()}"
    
    return None

def send_main_menu(to_number):
    """Send the main menu with interactive buttons."""
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body="🏢 *HR Assistant Bot*\n\nHello! I'm your AI-powered HR assistant. You can:\n\n🎯 *Quick Options:*\n1️⃣ Payroll Inquiry\n2️⃣ Leave Request\n3️⃣ Company Policies\n4️⃣ Document Request\n5️⃣ Support & Feedback\n\n💬 *Or just ask me anything!*\n_\"When is payday?\"_\n_\"How many vacation days do I have?\"_\n_\"What's the remote work policy?\"_\n\nType a number or ask your question!"
        )
        return True
    except Exception as e:
        print(f"Error sending main menu: {e}")
        return False

def get_user_session(phone_number):
    """Get or create user session."""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'state': 'ai_mode',
            'last_action': None,
            'employee_id': None,
            'conversation_history': []
        }
    return user_sessions[phone_number]

def update_user_session(phone_number, state=None, last_action=None, employee_id=None):
    """Update user session."""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'state': 'ai_mode',
            'last_action': None,
            'employee_id': None,
            'conversation_history': []
        }
    
    if state:
        user_sessions[phone_number]['state'] = state
    if last_action:
        user_sessions[phone_number]['last_action'] = last_action
    if employee_id:
        user_sessions[phone_number]['employee_id'] = employee_id

def add_to_conversation_history(phone_number, message, response):
    """Add message to conversation history."""
    if phone_number not in user_sessions:
        get_user_session(phone_number)
    
    user_sessions[phone_number]['conversation_history'].append({
        'user': message,
        'bot': response,
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only last 5 conversations to manage memory
    if len(user_sessions[phone_number]['conversation_history']) > 5:
        user_sessions[phone_number]['conversation_history'] = user_sessions[phone_number]['conversation_history'][-5:]

def get_conversation_context(phone_number):
    """Get conversation context for better AI responses."""
    session = get_user_session(phone_number)
    context = ""
    
    if session['employee_id']:
        context += f"Employee ID: {session['employee_id']}\n"
    
    if session['conversation_history']:
        context += "Recent conversation:\n"
        for conv in session['conversation_history'][-2:]:  # Last 2 exchanges
            context += f"User: {conv['user']}\nBot: {conv['bot'][:100]}...\n"
    
    return context

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    """Handle incoming WhatsApp messages with AI capabilities."""
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")
    
    # Get user session
    session = get_user_session(from_number)
    
    resp = MessagingResponse()
    
    # Handle greetings and menu requests
    if any(greeting in incoming_msg.lower() for greeting in ["hi", "hello", "hey", "start", "menu"]):
        send_main_menu(from_number)
        update_user_session(from_number, 'ai_mode')
        return str(resp)
    
    # Handle structured menu commands
    if is_structured_command(incoming_msg):
        if incoming_msg == '1':
            ai_response = get_gemini_response(
                "I want to inquire about my payroll status. What information do you need from me?",
                get_conversation_context(from_number)
            )
            resp.message(ai_response)
            update_user_session(from_number, 'payroll_inquiry')
            
        elif incoming_msg == '2':
            ai_response = get_gemini_response(
                "I want to request leave. Can you help me with the process and requirements?",
                get_conversation_context(from_number)
            )
            resp.message(ai_response)
            update_user_session(from_number, 'leave_request')
            
        elif incoming_msg == '3':
            ai_response = get_gemini_response(
                "I want to know about company policies. What policies can you tell me about?",
                get_conversation_context(from_number)
            )
            resp.message(ai_response)
            update_user_session(from_number, 'company_policies')
            
        elif incoming_msg == '4':
            ai_response = get_gemini_response(
                "I need to request a document from HR. What's the process?",
                get_conversation_context(from_number)
            )
            resp.message(ai_response)
            update_user_session(from_number, 'document_request')
            
        elif incoming_msg == '5':
            ai_response = get_gemini_response(
                "I want to provide feedback or get support. How can I do this?",
                get_conversation_context(from_number)
            )
            resp.message(ai_response)
            update_user_session(from_number, 'support_feedback')
    
    else:
        # Handle natural language queries with AI
        
        # Extract employee ID if present
        emp_id = extract_employee_id(incoming_msg)
        if emp_id:
            update_user_session(from_number, employee_id=emp_id)
        
        # Get AI response with context
        context = get_conversation_context(from_number)
        ai_response = get_gemini_response(incoming_msg, context)
        
        # Add some intelligence for common patterns
        if any(word in incoming_msg.lower() for word in ['salary', 'pay', 'payroll', 'wages']):
            update_user_session(from_number, 'payroll_inquiry')
        elif any(word in incoming_msg.lower() for word in ['leave', 'vacation', 'holiday', 'time off']):
            update_user_session(from_number, 'leave_request')
        elif any(word in incoming_msg.lower() for word in ['policy', 'policies', 'rules', 'guidelines']):
            update_user_session(from_number, 'company_policies')
        elif any(word in incoming_msg.lower() for word in ['document', 'certificate', 'letter']):
            update_user_session(from_number, 'document_request')
        
        resp.message(ai_response)
        
        # Add to conversation history
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
        <li>📊 Session Management</li>
        <li>🔍 Employee ID Recognition</li>
    </ul>
    """

@app.route("/sessions", methods=["GET"])
def view_sessions():
    """View active user sessions (for debugging)."""
    return json.dumps(user_sessions, indent=2, default=str)

if __name__ == "__main__":
    print("🚀 Starting AI-Powered HR WhatsApp Bot...")
    print("Required environment variables:")
    print("✅ TWILIO_ACCOUNT_SID")
    print("✅ TWILIO_AUTH_TOKEN") 
    print("✅ TWILIO_WHATSAPP_NUMBER")
    print("🆕 GOOGLE_API_KEY")
    print("")
    
    if not GEMINI_API_KEY:
        print("⚠️  WARNING: GOOGLE_API_KEY not found. AI features will not work.")
    else:
        print("🤖 Gemini AI: Ready")
    
    app.run(debug=True, port=5000)