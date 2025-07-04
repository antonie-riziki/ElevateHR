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
import sqlite3
from typing import Dict, List, Optional
import schedule
import threading
import time
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
app = Flask(__name__)

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "whatsapp:+254758750620")  # Admin phone for notifications

# Initialize Twilio client
if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    logging.error("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set. Twilio functionality will be limited.")
    client = None
else:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Gemini AI with enhanced error handling
if not GEMINI_API_KEY:
    logging.error("GOOGLE_API_KEY not set. AI features will not work.")
    model = None
else:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
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
            logging.error("Failed to initialize any Gemini model.")
                
    except Exception as e:
        logging.error(f"Failed to configure Gemini API: {e}")
        model = None

# Enhanced data structures
@dataclass
class LeaveRequest:
    employee_id: str
    leave_type: str
    start_date: str
    end_date: str
    reason: str
    status: str = "pending"
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class Ticket:
    ticket_id: str
    employee_id: str
    category: str
    subject: str
    description: str
    priority: str = "medium"
    status: str = "open"
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Enhanced database setup
def init_database():
    """Initialize SQLite database for persistent storage."""
    conn = sqlite3.connect('hr_bot.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone_number TEXT PRIMARY KEY,
            employee_id TEXT,
            first_name TEXT,
            last_name TEXT,
            department TEXT,
            position TEXT,
            join_date TEXT,
            session_data TEXT,
            last_active TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Leave requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            leave_type TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Support tickets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            employee_id TEXT,
            category TEXT,
            subject TEXT,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            action TEXT,
            query TEXT,
            response_time REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

# Initialize database on startup
init_database()

# Enhanced user session management
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.timeout_minutes = 30
    
    def get_session(self, phone_number: str) -> Dict:
        """Get or create user session with database persistence."""
        now = datetime.now()
        
        # Check if session exists and is not expired
        if phone_number in self.sessions:
            session = self.sessions[phone_number]
            if (now - session['last_active']) <= timedelta(minutes=self.timeout_minutes):
                session['last_active'] = now
                return session
        
        # Create new session or restore from database
        session = self._load_session_from_db(phone_number)
        if not session:
            session = self._create_new_session(phone_number)
        
        session['last_active'] = now
        self.sessions[phone_number] = session
        return session
    
    def _load_session_from_db(self, phone_number: str) -> Optional[Dict]:
        """Load session data from database."""
        try:
            conn = sqlite3.connect('hr_bot.db')
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE phone_number = ?', (phone_number,))
            user_data = cursor.fetchone()
            conn.close()
            
            if user_data:
                return {
                    'state': 'initial',
                    'employee_id': user_data[1],
                    'first_name': user_data[2],
                    'last_name': user_data[3],
                    'department': user_data[4],
                    'position': user_data[5],
                    'conversation_history': [],
                    'current_form': {},
                    'last_active': datetime.now()
                }
        except Exception as e:
            logging.error(f"Error loading session from database: {e}")
        
        return None
    
    def _create_new_session(self, phone_number: str) -> Dict:
        """Create a new session."""
        return {
            'state': 'initial',
            'employee_id': None,
            'first_name': None,
            'last_name': None,
            'department': None,
            'position': None,
            'conversation_history': [],
            'current_form': {},
            'last_active': datetime.now()
        }
    
    def save_session_to_db(self, phone_number: str, session: Dict):
        """Save session data to database."""
        try:
            conn = sqlite3.connect('hr_bot.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (phone_number, employee_id, first_name, last_name, department, position, session_data, last_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                phone_number,
                session.get('employee_id'),
                session.get('first_name'),
                session.get('last_name'),
                session.get('department'),
                session.get('position'),
                json.dumps(session.get('current_form', {})),
                session['last_active'].isoformat()
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error saving session to database: {e}")

# Initialize session manager
session_manager = SessionManager()

# Enhanced HR Knowledge Base with more detailed information
HR_KNOWLEDGE_BASE = """
COMPANY HR POLICIES AND INFORMATION:

LEAVE POLICY:
- Annual Leave: 20 paid vacation days per year (prorated for new employees)
- Sick Leave: 10 sick leave days per year (with medical certificate for >3 days)
- National Holidays: 12 public holidays observed
- Maternity Leave: 16 weeks paid (can be extended unpaid)
- Paternity Leave: 4 weeks paid within 6 months of birth
- Bereavement Leave: 5 days paid for immediate family
- Study Leave: Available for approved courses
- Sabbatical: 6-12 months unpaid leave after 5 years service
- Leave applications must be submitted 2 weeks in advance (except sick leave)
- Emergency leave applications accepted with manager approval
- Portal: https://company-portal.com/leave-application

PAYROLL INFORMATION:
- Pay Schedule: 25th of each month (if weekend, then previous Friday)
- Pay Period: 1st to last day of the month
- Salary Components: Base salary + allowances + overtime + bonuses
- Deductions: Tax, insurance, pension, loans
- Overtime: 1.5x regular rate for hours over 40/week, 2x for weekends/holidays
- Bonuses: Quarterly performance (0-20% of salary) + Annual (1-3 months salary)
- Salary Review: Annual in January, mid-year adjustments possible
- Payslip Access: Employee portal, email notifications

WORKING ARRANGEMENTS:
- Standard Hours: 9:00 AM - 5:00 PM (40 hours/week)
- Flexible Hours: 8:00 AM - 6:00 PM window available
- Core Hours: 10:00 AM - 3:00 PM (mandatory presence)
- Lunch Break: 1 hour (flexible timing)
- Remote Work: Up to 3 days per week with approval
- Compressed Hours: 4-day weeks available (10 hours/day)
- Part-time: Available for certain roles

BENEFITS PACKAGE:
- Health Insurance: 100% employee + 50% family coverage
- Dental & Vision: Full coverage included
- Life Insurance: 3x annual salary
- Disability Insurance: Short and long-term coverage
- Retirement: 401(k) with 6% company match + pension plan
- Professional Development: $3000/year training budget
- Wellness: Gym membership, mental health support
- Transportation: Monthly transit pass or parking
- Meals: Subsidized cafeteria, meal vouchers
- Technology: Laptop, phone allowance
- Employee Discounts: Various retail and service partners

CONTACT INFORMATION:
- HR Department: hr@company.com | +1-555-0199
- Payroll Queries: payroll@company.com | +1-555-0177
- IT Support: it@company.com | +1-555-0188
- Emergency Line: +1-555-0911 (24/7)
- Office Hours: 8:30 AM - 5:30 PM, Monday-Friday
"""

# Enhanced form handlers
class FormHandler:
    @staticmethod
    def handle_leave_request(session: Dict, user_input: str) -> tuple[str, bool]:
        """Handle leave request form submission."""
        form = session.get('current_form', {})
        
        if 'step' not in form:
            form['step'] = 'leave_type'
            form['data'] = {}
        
        if form['step'] == 'leave_type':
            leave_types = ['annual', 'sick', 'maternity', 'paternity', 'bereavement', 'study']
            if user_input.lower() in leave_types:
                form['data']['leave_type'] = user_input.lower()
                form['step'] = 'start_date'
                session['current_form'] = form
                return "📅 Enter start date (YYYY-MM-DD format):", False
            else:
                return f"Please select a valid leave type: {', '.join(leave_types)}", False
        
        elif form['step'] == 'start_date':
            try:
                datetime.strptime(user_input, '%Y-%m-%d')
                form['data']['start_date'] = user_input
                form['step'] = 'end_date'
                session['current_form'] = form
                return "📅 Enter end date (YYYY-MM-DD format):", False
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD (e.g., 2024-03-15):", False
        
        elif form['step'] == 'end_date':
            try:
                datetime.strptime(user_input, '%Y-%m-%d')
                form['data']['end_date'] = user_input
                form['step'] = 'reason'
                session['current_form'] = form
                return "📝 Enter reason for leave (optional, type 'skip' to skip):", False
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD:", False
        
        elif form['step'] == 'reason':
            if user_input.lower() != 'skip':
                form['data']['reason'] = user_input
            else:
                form['data']['reason'] = ""
            
            # Submit leave request
            leave_request = LeaveRequest(
                employee_id=session.get('employee_id', 'UNKNOWN'),
                leave_type=form['data']['leave_type'],
                start_date=form['data']['start_date'],
                end_date=form['data']['end_date'],
                reason=form['data']['reason']
            )
            
            # Save to database
            FormHandler._save_leave_request(leave_request)
            
            # Clear form
            session['current_form'] = {}
            
            return f"✅ Leave request submitted successfully!\n\n" \
                   f"Type: {leave_request.leave_type.title()}\n" \
                   f"Dates: {leave_request.start_date} to {leave_request.end_date}\n" \
                   f"Status: Pending approval\n\n" \
                   f"You'll receive updates via WhatsApp. Type 'menu' for more options!", True
        
        return "Something went wrong. Please try again.", True
    
    @staticmethod
    def handle_support_ticket(session: Dict, user_input: str) -> tuple[str, bool]:
        """Handle support ticket form submission."""
        form = session.get('current_form', {})
        
        if 'step' not in form:
            form['step'] = 'category'
            form['data'] = {}
        
        if form['step'] == 'category':
            categories = ['it', 'hr', 'facilities', 'payroll', 'benefits', 'other']
            if user_input.lower() in categories:
                form['data']['category'] = user_input.lower()
                form['step'] = 'subject'
                session['current_form'] = form
                return "📝 Enter ticket subject/title:", False
            else:
                return f"Please select a valid category: {', '.join(categories)}", False
        
        elif form['step'] == 'subject':
            form['data']['subject'] = user_input
            form['step'] = 'description'
            session['current_form'] = form
            return "📄 Enter detailed description of your issue:", False
        
        elif form['step'] == 'description':
            form['data']['description'] = user_input
            form['step'] = 'priority'
            session['current_form'] = form
            return "⚡ Select priority level (low, medium, high, urgent):", False
        
        elif form['step'] == 'priority':
            priorities = ['low', 'medium', 'high', 'urgent']
            if user_input.lower() in priorities:
                form['data']['priority'] = user_input.lower()
                
                # Generate ticket ID
                ticket_id = f"TK{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create ticket
                ticket = Ticket(
                    ticket_id=ticket_id,
                    employee_id=session.get('employee_id', 'UNKNOWN'),
                    category=form['data']['category'],
                    subject=form['data']['subject'],
                    description=form['data']['description'],
                    priority=form['data']['priority']
                )
                
                # Save to database
                FormHandler._save_support_ticket(ticket)
                
                # Clear form
                session['current_form'] = {}
                
                return f"🎫 Support ticket created successfully!\n\n" \
                       f"Ticket ID: {ticket.ticket_id}\n" \
                       f"Category: {ticket.category.title()}\n" \
                       f"Priority: {ticket.priority.title()}\n" \
                       f"Status: Open\n\n" \
                       f"You'll receive updates via WhatsApp. Type 'menu' for more options!", True
            else:
                return f"Please select a valid priority: {', '.join(priorities)}", False
        
        return "Something went wrong. Please try again.", True
    
    @staticmethod
    def _save_leave_request(leave_request: LeaveRequest):
        """Save leave request to database."""
        try:
            conn = sqlite3.connect('hr_bot.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leave_requests 
                (employee_id, leave_type, start_date, end_date, reason, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                leave_request.employee_id,
                leave_request.leave_type,
                leave_request.start_date,
                leave_request.end_date,
                leave_request.reason,
                leave_request.status
            ))
            conn.commit()
            conn.close()
            logging.info(f"Leave request saved for employee {leave_request.employee_id}")
        except Exception as e:
            logging.error(f"Error saving leave request: {e}")
    
    @staticmethod
    def _save_support_ticket(ticket: Ticket):
        """Save support ticket to database."""
        try:
            conn = sqlite3.connect('hr_bot.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO support_tickets 
                (ticket_id, employee_id, category, subject, description, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket.ticket_id,
                ticket.employee_id,
                ticket.category,
                ticket.subject,
                ticket.description,
                ticket.priority,
                ticket.status
            ))
            conn.commit()
            conn.close()
            logging.info(f"Support ticket saved: {ticket.ticket_id}")
        except Exception as e:
            logging.error(f"Error saving support ticket: {e}")

# Enhanced AI response with context awareness
def get_enhanced_gemini_response(user_message: str, session: Dict) -> str:
    """Get enhanced, personalized response from Gemini AI with user context."""
    if model is None:
        return "AI is temporarily unavailable. Please contact HR directly at hr@company.com"

    # Build user context
    first_name = session.get('first_name', 'there')
    last_name = session.get('last_name', '')
    employee_id = session.get('employee_id', 'Not provided')
    department = session.get('department', 'Not specified')
    position = session.get('position', 'Not specified')
    recent_convo = chr(10).join([
        f"User: {conv['user']}, Bot: {conv['bot']}" 
        for conv in session.get('conversation_history', [])[-2:]
    ])

    prompt = f"""
You are an advanced HR Assistant Bot for WhatsApp. Always address the user by their first name ({first_name}) and personalize every response using their profile and recent conversation.

USER PROFILE:
- Name: {first_name} {last_name}
- Employee ID: {employee_id}
- Department: {department}
- Position: {position}

RECENT CONVERSATION:
{recent_convo}

COMPANY INFORMATION:
{HR_KNOWLEDGE_BASE}

USER QUESTION: {user_message}

INSTRUCTIONS:
1. Start your response with a greeting using the user's first name.
2. Reference their department, position, or previous actions if relevant.
3. Provide clear, concise, and actionable information.
4. Suggest a next step or menu option tailored to their context.
5. Use friendly, empathetic language and appropriate emojis.
6. Keep responses under 500 characters for WhatsApp.
7. If you need more info (like Employee ID), ask for it politely.

Respond now:
"""

    try:
        response = model.generate_content(prompt)
        if response.text and response.text.strip():
            return response.text.strip()
        else:
            return f"Sorry {first_name}, I'm having trouble generating a response. Please try again or contact HR directly."
    except Exception as e:
        logging.error(f"Enhanced Gemini response error: {e}")
        return f"Sorry {first_name}, I'm experiencing technical difficulties. Please try again or contact HR at hr@company.com for immediate assistance."

# Enhanced message processing
def process_message(phone_number: str, message: str) -> str:
    """Process incoming message with enhanced logic."""
    session = session_manager.get_session(phone_number)
    
    # Handle active forms
    if session.get('current_form') and session['current_form'].get('step'):
        if session['current_form'].get('type') == 'leave_request':
            response, is_complete = FormHandler.handle_leave_request(session, message)
            if is_complete:
                session['current_form'] = {}
            session_manager.save_session_to_db(phone_number, session)
            return response
        elif session['current_form'].get('type') == 'support_ticket':
            response, is_complete = FormHandler.handle_support_ticket(session, message)
            if is_complete:
                session['current_form'] = {}
            session_manager.save_session_to_db(phone_number, session)
            return response
    
    # Handle menu commands
    if message.lower() in ['menu', 'start', 'hi', 'hello', 'hey']:
        return get_main_menu_message()
    
    # Handle numbered menu options
    if message in ['1', '2', '3', '4', '5', '6', '7']:
        return handle_menu_selection(session, message)
    
    # Handle leave request initiation
    if any(keyword in message.lower() for keyword in ['apply for leave', 'request leave', 'leave application']):
        if not session.get('employee_id'):
            return "To apply for leave, please first provide your Employee ID. Type 'My Employee ID is [ID]'"
        session['current_form'] = {'type': 'leave_request', 'step': 'leave_type', 'data': {}}
        return "📋 **Leave Request Application**\n\nSelect leave type:\n• Annual\n• Sick\n• Maternity\n• Paternity\n• Bereavement\n• Study\n\nType the leave type:"
    
    # Handle support ticket initiation
    if any(keyword in message.lower() for keyword in ['create ticket', 'support ticket', 'new ticket']):
        if not session.get('employee_id'):
            return "To create a support ticket, please first provide your Employee ID. Type 'My Employee ID is [ID]'"
        session['current_form'] = {'type': 'support_ticket', 'step': 'category', 'data': {}}
        return "🎫 **Support Ticket Creation**\n\nSelect category:\n• IT\n• HR\n• Facilities\n• Payroll\n• Benefits\n• Other\n\nType the category:"
    
    # Handle status checks
    if 'leave status' in message.lower():
        return check_leave_status(session)
    
    if 'ticket status' in message.lower():
        return check_ticket_status(session)
    
    # Extract employee ID if provided
    if not session.get('employee_id'):
        emp_id = extract_employee_id(message)
        if emp_id:
            session['employee_id'] = emp_id
            session_manager.save_session_to_db(phone_number, session)
            return f"✅ Employee ID {emp_id} registered! I can now help with personalized queries. Type 'menu' for options."
    
    # Get AI response
    response = get_enhanced_gemini_response(message, session)
    
    # Add to conversation history
    session['conversation_history'].append({
        'user': message,
        'bot': response,
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only last 3 conversations
    if len(session['conversation_history']) > 3:
        session['conversation_history'] = session['conversation_history'][-3:]
    
    return response

def get_main_menu_message() -> str:
    """Generate enhanced main menu message."""
    return """🏢 **HR Assistant Bot** - Enhanced Version

Hello! I'm your AI-powered HR assistant with advanced capabilities:

🎯 **Quick Actions:**
1️⃣ 💰 Payroll & Benefits
2️⃣ 🏖️ Leave Management
3️⃣ 📋 Company Policies
4️⃣ 📄 Document Requests
5️⃣ 🎫 Support Tickets
6️⃣ 👥 Employee Directory
7️⃣ 📊 My Dashboard

💬 **Smart Features:**
• Natural language queries
• Personalized responses
• Form-guided applications
• Status tracking
• Emergency contacts

Just ask me anything or select a number!"""

def handle_menu_selection(session: Dict, selection: str) -> str:
    """Handle menu selection with enhanced options."""
    selections = {
        '1': "Here's your payroll information:\n💰 Next payday: 25th of this month\n📊 Access payslips at company-portal.com\n🏦 Direct deposit to your registered account\n\nNeed specific salary details? Please provide your Employee ID.\n\nType 'menu' for more options!",
        '2': "🏖️ **Leave Management**\n\nOptions:\n• Type 'apply for leave' to submit new request\n• Type 'leave status' to check pending requests\n• Type 'leave balance' to see remaining days\n\nLeave Types Available:\n✅ Annual (20 days)\n✅ Sick (10 days)\n✅ Maternity (16 weeks)\n✅ Paternity (4 weeks)\n\nWhat would you like to do?",
        '3': "📋 **Company Policies**\n\n🕘 Working Hours: 9 AM - 5 PM\n🏠 Remote Work: 3 days/week\n📱 Flexible Hours: 8 AM - 6 PM window\n🎯 Core Hours: 10 AM - 3 PM\n\nFor detailed policies, visit: company-portal.com\n\nType 'menu' for more options!",
        '4': "📄 **Document Requests**\n\n📜 Available Documents:\n• Salary Certificate (2-3 days)\n• Employment Letter (2-3 days)\n• Experience Certificate (3-5 days)\n• Tax Documents (instant)\n\nTo request: Email hr@company.com with your Employee ID\n\nType 'menu' for more options!",
        '5': "🎫 **Support Tickets**\n\nCreate tickets for:\n• IT Issues\n• HR Queries\n• Facility Problems\n• Benefits Questions\n\nTo create ticket: Type 'create ticket'\nTo check status: Type 'ticket status'\n\nType 'menu' for more options!",
        '6': "👥 **Employee Directory**\n\n🔍 Search by:\n• Name\n• Department\n• Position\n\nType 'search [name]' or 'search [department]'\n\nExample: 'search John' or 'search IT'\n\nType 'menu' for more options!",
        '7': f"📊 **My Dashboard**\n\n👤 Employee: {session.get('first_name', 'Not set')} {session.get('last_name', '')}\n🆔 ID: {session.get('employee_id', 'Not provided')}\n🏢 Department: {session.get('department', 'Not specified')}\n\n📈 Quick Stats:\n• Active since: {datetime.now().strftime('%B %Y')}\n• Last login: Today\n\nType 'menu' for more options!"
    }
    
    return selections.get(selection, "Invalid selection. Type 'menu' to see options.")

def check_leave_status(session: Dict) -> str:
    """Check leave request status for employee."""
    if not session.get('employee_id'):
        return "Please provide your Employee ID first to check leave status."
    
    try:
        conn = sqlite3.connect('hr_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT leave_type, start_date, end_date, status, created_at 
            FROM leave_requests 
            WHERE employee_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (session['employee_id'],))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "📋 No leave requests found for your Employee ID.\n\nType 'apply for leave' to submit a new request or 'menu' for options."
        
        status_message = "📋 **Your Leave Requests:**\n\n"
        for i, (leave_type, start_date, end_date, status, created_at) in enumerate(results, 1):
            status_emoji = "⏳" if status == "pending" else "✅" if status == "approved" else "❌"
            status_message += f"{i}. {status_emoji} {leave_type.title()}\n   📅 {start_date} to {end_date}\n   Status: {status.title()}\n\n"
        
        status_message += "Type 'menu' for more options!"
        return status_message
        
    except Exception as e:
        logging.error(f"Error checking leave status: {e}")
        return "❌ Error checking leave status. Please try again or contact HR."

def check_ticket_status(session: Dict) -> str:
    """Check support ticket status for employee."""
    if not session.get('employee_id'):
        return "Please provide your Employee ID first to check ticket status."
    
    try:
        conn = sqlite3.connect('hr_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ticket_id, category, subject, priority, status, created_at 
            FROM support_tickets 
            WHERE employee_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (session['employee_id'],))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "🎫 No support tickets found for your Employee ID.\n\nType 'create ticket' to submit a new ticket or 'menu' for options."
        
        status_message = "🎫 **Your Support Tickets:**\n\n"
        for i, (ticket_id, category, subject, priority, status, created_at) in enumerate(results, 1):
            status_emoji = "🔴" if status == "open" else "🟡" if status == "in_progress" else "🟢"
            priority_emoji = "🔥" if priority == "urgent" else "⚡" if priority == "high" else "📋"
            status_message += f"{i}. {status_emoji} {ticket_id}\n   {priority_emoji} {category.title()}: {subject[:30]}...\n   Status: {status.title()}\n\n"
        
        status_message += "Type 'menu' for more options!"
        return status_message
        
    except Exception as e:
        logging.error(f"Error checking ticket status: {e}")
        return "❌ Error checking ticket status. Please try again or contact HR."

def extract_employee_id(message: str) -> Optional[str]:
    """Extract employee ID from message."""
    # Patterns to match employee ID
    patterns = [
        r'employee id is (\w+)',
        r'emp id is (\w+)',
        r'id is (\w+)',
        r'my id (\w+)',
        r'employee id[:\s]+(\w+)',
        r'emp[:\s]+(\w+)',
        r'id[:\s]+(\w+)'
    ]
    
    message_lower = message.lower()
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            return match.group(1).upper()
    
    return None

def log_analytics(phone_number: str, action: str, query: str, response_time: float):
    """Log analytics data for improvements."""
    try:
        conn = sqlite3.connect('hr_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO analytics (phone_number, action, query, response_time)
            VALUES (?, ?, ?, ?)
        ''', (phone_number, action, query, response_time))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error logging analytics: {e}")

def send_notification(phone_number: str, message: str):
    """Send notification to user."""
    if client and TWILIO_WHATSAPP_NUMBER:
        try:
            client.messages.create(
                body=message,
                from_=TWILIO_WHATSAPP_NUMBER,
                to=phone_number
            )
            logging.info(f"Notification sent to {phone_number}")
        except Exception as e:
            logging.error(f"Error sending notification: {e}")

def periodic_tasks():
    """Run periodic background tasks."""
    logging.info("Running periodic tasks...")
    
    # Check for leave requests needing approval (after 24 hours)
    try:
        conn = sqlite3.connect('hr_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT employee_id, leave_type, start_date, end_date, created_at
            FROM leave_requests 
            WHERE status = 'pending' 
            AND datetime(created_at) < datetime('now', '-1 day')
        ''')
        pending_requests = cursor.fetchall()
        conn.close()
        
        for request in pending_requests:
            # Notify admin about pending requests
            admin_message = f"⏰ Leave request pending approval:\nEmployee: {request[0]}\nType: {request[1]}\nDates: {request[2]} to {request[3]}"
            send_notification(ADMIN_PHONE, admin_message)
            
    except Exception as e:
        logging.error(f"Error in periodic tasks: {e}")

# Schedule periodic tasks
schedule.every().day.at("09:00").do(periodic_tasks)
schedule.every().day.at("17:00").do(periodic_tasks)

def run_scheduler():
    """Run the scheduler in a separate thread."""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

# Start scheduler in background
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Enhanced webhook with better error handling and analytics."""
    start_time = time.time()
    
    try:
        incoming_msg = request.values.get('Body', '').strip()
        sender_number = request.values.get('From', '')
        
        if not incoming_msg or not sender_number:
            return str(MessagingResponse())
        
        logging.info(f"Received message from {sender_number}: {incoming_msg}")
        
        # Process the message
        response_text = process_message(sender_number, incoming_msg)
        
        # Log analytics
        response_time = time.time() - start_time
        log_analytics(sender_number, "message_processed", incoming_msg, response_time)
        
        # Create response
        resp = MessagingResponse()
        resp.message(response_text)
        
        logging.info(f"Sent response to {sender_number}: {response_text[:100]}...")
        return str(resp)
        
    except Exception as e:
        logging.error(f"Error in webhook: {e}")
        resp = MessagingResponse()
        resp.message("🚨 I'm experiencing technical difficulties. Please try again in a moment or contact HR directly at hr@company.com")
        return str(resp)

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Admin endpoint for bot statistics."""
    try:
        conn = sqlite3.connect('hr_bot.db')
        cursor = conn.cursor()
        
        # Get basic stats
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM leave_requests')
        total_leave_requests = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM support_tickets')
        total_tickets = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM analytics WHERE date(timestamp) = date("now")')
        messages_today = cursor.fetchone()[0]
        
        # Get recent activity
        cursor.execute('''
            SELECT phone_number, action, timestamp 
            FROM analytics 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        recent_activity = cursor.fetchall()
        
        conn.close()
        
        stats = {
            'total_users': total_users,
            'total_leave_requests': total_leave_requests,
            'total_tickets': total_tickets,
            'messages_today': messages_today,
            'recent_activity': recent_activity
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logging.error(f"Error getting admin stats: {e}")
        return jsonify({'error': 'Failed to get statistics'}), 500

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    """Admin endpoint for broadcasting messages."""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get all registered users
        conn = sqlite3.connect('hr_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT phone_number FROM users')
        users = cursor.fetchall()
        conn.close()
        
        sent_count = 0
        for user in users:
            try:
                send_notification(user[0], f"📢 **Company Announcement:**\n\n{message}")
                sent_count += 1
            except Exception as e:
                logging.error(f"Failed to send broadcast to {user[0]}: {e}")
        
        return jsonify({'sent_to': sent_count, 'total_users': len(users)})
        
    except Exception as e:
        logging.error(f"Error in broadcast: {e}")
        return jsonify({'error': 'Failed to send broadcast'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'twilio': bool(client),
            'gemini': bool(model),
            'database': True
        }
    })

@app.route('/', methods=['GET'])
def index():
    """Simple index page."""
    return """
    <html>
    <head><title>HR Bot</title></head>
    <body>
        <h1>🏢 HR Assistant Bot</h1>
        <p>Advanced WhatsApp HR Bot with AI capabilities</p>
        <h2>Features:</h2>
        <ul>
            <li>✅ AI-powered responses</li>
            <li>✅ Leave request management</li>
            <li>✅ Support ticket system</li>
            <li>✅ Employee data management</li>
            <li>✅ Analytics and reporting</li>
        </ul>
        <p>Bot is running and ready to receive messages!</p>
    </body>
    </html>
    """

@app.route('/whatsapp', methods=['POST'])
def whatsapp():
    return webhook()

if __name__ == '__main__':
    logging.info("Starting HR Bot...")
    logging.info(f"Twilio configured: {bool(client)}")
    logging.info(f"Gemini AI configured: {bool(model)}")
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)


