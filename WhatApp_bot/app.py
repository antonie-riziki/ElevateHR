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
import gc  # For garbage collection

# Configure logging to be less verbose
logging.basicConfig(
    level=logging.WARNING,  # Change from INFO to WARNING
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Flask app configuration
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit payload size to 16MB

# Load environment variables
load_dotenv()

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "whatsapp:+1234567890")

# Session configuration
SESSION_TIMEOUT_MINUTES = 30
MAX_SESSIONS = 1000  # Limit maximum concurrent sessions
MAX_CONVERSATION_HISTORY = 3  # Limit conversation history size

# Database connection pool
def get_db_connection():
    conn = sqlite3.connect('hr_bot.db', timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

# Periodic cleanup function
def cleanup_old_sessions():
    """Remove expired sessions to free up memory."""
    try:
        current_time = datetime.now()
        expired_sessions = []
        
        for phone_number, session in user_sessions.items():
            if (current_time - session['last_active']) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                expired_sessions.append(phone_number)
        
        for phone_number in expired_sessions:
            del user_sessions[phone_number]
            
        # Force garbage collection
        gc.collect()
        
    except Exception as e:
        logging.error(f"Error in cleanup_old_sessions: {e}")

# Schedule periodic cleanup
def run_cleanup_scheduler():
    """Run cleanup tasks periodically."""
    while True:
        cleanup_old_sessions()
        time.sleep(300)  # Run every 5 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=run_cleanup_scheduler, daemon=True)
cleanup_thread.start()

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
class Employee:
    employee_id: str
    first_name: str
    last_name: str
    department: str
    position: str
    email: str
    phone_number: str
    join_date: str
    status: str = "active"
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

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

# Database initialization
def init_database():
    """Initialize SQLite database with enhanced schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            department TEXT,
            position TEXT,
            email TEXT UNIQUE,
            phone_number TEXT UNIQUE,
            join_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            phone_number TEXT PRIMARY KEY,
            session_data TEXT,
            last_active TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        )
    ''')
    
    # Leave requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            approver_id TEXT,
            approval_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id),
            FOREIGN KEY (approver_id) REFERENCES employees (employee_id)
        )
    ''')
    
    # Support tickets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            employee_id TEXT NOT NULL,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            resolution TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id),
            FOREIGN KEY (assigned_to) REFERENCES employees (employee_id)
        )
    ''')
    
    # Message history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            employee_id TEXT,
            message_type TEXT NOT NULL,
            message_content TEXT NOT NULL,
            response_content TEXT NOT NULL,
            response_time REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        )
    ''')
    
    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_data TEXT,
            phone_number TEXT,
            employee_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        )
    ''')
    
    # Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            scheduled_for TEXT,
            sent_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully with enhanced schema.")

# Initialize database on startup
init_database()

# Enhanced database operations
class DatabaseManager:
    def __init__(self):
        self.db_path = 'hr_bot.db'
    
    def get_connection(self):
        return get_db_connection()
    
    def save_employee(self, employee: Employee):
        """Save or update employee record."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO employees 
                (employee_id, first_name, last_name, department, position, email, phone_number, join_date, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                employee.employee_id,
                employee.first_name,
                employee.last_name,
                employee.department,
                employee.position,
                employee.email,
                employee.phone_number,
                employee.join_date,
                employee.status,
                employee.created_at
            ))
            conn.commit()
            conn.close()
            logging.info(f"Employee {employee.employee_id} saved successfully.")
            return True
        except Exception as e:
            logging.error(f"Error saving employee: {e}")
            return False
    
    def get_employee_by_id(self, employee_id: str) -> Optional[Employee]:
        """Get employee by ID."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM employees WHERE employee_id = ?', (employee_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return Employee(
                    employee_id=result[0],
                    first_name=result[1],
                    last_name=result[2],
                    department=result[3],
                    position=result[4],
                    email=result[5],
                    phone_number=result[6],
                    join_date=result[7],
                    status=result[8],
                    created_at=result[9]
                )
            return None
        except Exception as e:
            logging.error(f"Error getting employee: {e}")
            return None
    
    def get_employee_by_phone(self, phone_number: str) -> Optional[Employee]:
        """Get employee by phone number."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM employees WHERE phone_number = ?', (phone_number,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return Employee(
                    employee_id=result[0],
                    first_name=result[1],
                    last_name=result[2],
                    department=result[3],
                    position=result[4],
                    email=result[5],
                    phone_number=result[6],
                    join_date=result[7],
                    status=result[8],
                    created_at=result[9]
                )
            return None
        except Exception as e:
            logging.error(f"Error getting employee by phone: {e}")
            return None
    
    def save_leave_request(self, leave_request: LeaveRequest) -> bool:
        """Save leave request."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO leave_requests 
                (employee_id, leave_type, start_date, end_date, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                leave_request.employee_id,
                leave_request.leave_type,
                leave_request.start_date,
                leave_request.end_date,
                leave_request.reason,
                leave_request.status,
                leave_request.created_at
            ))
            conn.commit()
            conn.close()
            logging.info(f"Leave request saved for employee {leave_request.employee_id}")
            return True
        except Exception as e:
            logging.error(f"Error saving leave request: {e}")
            return False
    
    def save_ticket(self, ticket: Ticket) -> bool:
        """Save support ticket."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO support_tickets 
                (ticket_id, employee_id, category, subject, description, priority, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket.ticket_id,
                ticket.employee_id,
                ticket.category,
                ticket.subject,
                ticket.description,
                ticket.priority,
                ticket.status,
                ticket.created_at
            ))
            conn.commit()
            conn.close()
            logging.info(f"Support ticket {ticket.ticket_id} saved")
            return True
        except Exception as e:
            logging.error(f"Error saving support ticket: {e}")
            return False
    
    def log_message(self, phone_number: str, employee_id: Optional[str], message_type: str, 
                   message_content: str, response_content: str, response_time: float):
        """Log message history."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO message_history 
                (phone_number, employee_id, message_type, message_content, response_content, response_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                phone_number,
                employee_id,
                message_type,
                message_content,
                response_content,
                response_time
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error logging message: {e}")
    
    def log_analytics(self, event_type: str, event_data: dict, phone_number: str, employee_id: Optional[str]):
        """Log analytics event."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO analytics 
                (event_type, event_data, phone_number, employee_id)
                VALUES (?, ?, ?, ?)
            ''', (
                event_type,
                json.dumps(event_data),
                phone_number,
                employee_id
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error logging analytics: {e}")
    
    def schedule_notification(self, employee_id: str, notification_type: str, content: str, scheduled_for: str):
        """Schedule a notification."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notifications 
                (employee_id, notification_type, content, scheduled_for)
                VALUES (?, ?, ?, ?)
            ''', (
                employee_id,
                notification_type,
                content,
                scheduled_for
            ))
            conn.commit()
            conn.close()
            logging.info(f"Notification scheduled for employee {employee_id}")
            return True
        except Exception as e:
            logging.error(f"Error scheduling notification: {e}")
            return False

# Initialize database manager
db_manager = DatabaseManager()

# Enhanced session management
class SessionManager:
    def __init__(self):
        self.db_manager = db_manager
        self.timeout_minutes = 30
    
    def get_session(self, phone_number: str) -> Dict:
        """Get or create user session with database persistence."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_sessions WHERE phone_number = ?', (phone_number,))
            session_data = cursor.fetchone()
            
            now = datetime.now()
            
            if session_data:
                last_active = datetime.fromisoformat(session_data[3])
                if (now - last_active) <= timedelta(minutes=self.timeout_minutes):
                    # Update last active
                    cursor.execute('''
                        UPDATE user_sessions 
                        SET last_active = ? 
                        WHERE phone_number = ?
                    ''', (now.isoformat(), phone_number))
                    conn.commit()
                    
                    # Return session data
                    return json.loads(session_data[2])
            
            # Create new session
            new_session = {
                'state': 'initial',
                'employee_id': None,
                'conversation_history': [],
                'current_form': None,
                'last_action': None
            }
            
            cursor.execute('''
                INSERT OR REPLACE INTO user_sessions 
                (phone_number, session_data, last_active)
                VALUES (?, ?, ?)
            ''', (
                phone_number,
                json.dumps(new_session),
                now.isoformat()
            ))
            conn.commit()
            conn.close()
            
            return new_session
            
        except Exception as e:
            logging.error(f"Error getting session: {e}")
            return {
                'state': 'initial',
                'employee_id': None,
                'conversation_history': [],
                'current_form': None,
                'last_action': None
            }
    
    def update_session(self, phone_number: str, session_data: Dict):
        """Update session data in database."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_sessions 
                SET session_data = ?, last_active = ?
                WHERE phone_number = ?
            ''', (
                json.dumps(session_data),
                datetime.now().isoformat(),
                phone_number
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error updating session: {e}")
            return False
    
    def clear_session(self, phone_number: str):
        """Clear user session."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_sessions WHERE phone_number = ?', (phone_number,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error clearing session: {e}")
            return False

# Initialize session manager
session_manager = SessionManager()

# Enhanced form handling
class FormHandler:
    def __init__(self):
        self.db_manager = db_manager
        self.session_manager = session_manager
    
    def handle_leave_request(self, session: Dict, user_input: str) -> tuple[str, bool]:
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
                return "📅 Enter start date (YYYY-MM-DD format):", False
            else:
                return f"Please select a valid leave type: {', '.join(leave_types)}", False
        
        elif form['step'] == 'start_date':
            try:
                start_date = datetime.strptime(user_input, '%Y-%m-%d')
                if start_date.date() < datetime.now().date():
                    return "Start date cannot be in the past. Please enter a future date (YYYY-MM-DD):", False
                form['data']['start_date'] = user_input
                form['step'] = 'end_date'
                return "📅 Enter end date (YYYY-MM-DD format):", False
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD (e.g., 2024-03-15):", False
        
        elif form['step'] == 'end_date':
            try:
                end_date = datetime.strptime(user_input, '%Y-%m-%d')
                start_date = datetime.strptime(form['data']['start_date'], '%Y-%m-%d')
                if end_date <= start_date:
                    return "End date must be after start date. Please enter a valid end date:", False
                form['data']['end_date'] = user_input
                form['step'] = 'reason'
                return "📝 Enter reason for leave (optional, type 'skip' to skip):", False
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD:", False
        
        elif form['step'] == 'reason':
            if user_input.lower() != 'skip':
                form['data']['reason'] = user_input
            else:
                form['data']['reason'] = ""
            
            # Create and save leave request
            leave_request = LeaveRequest(
                employee_id=session.get('employee_id', 'UNKNOWN'),
                leave_type=form['data']['leave_type'],
                start_date=form['data']['start_date'],
                end_date=form['data']['end_date'],
                reason=form['data']['reason']
            )
            
            if self.db_manager.save_leave_request(leave_request):
                # Schedule notification for HR
                self.db_manager.schedule_notification(
                    employee_id='HR_ADMIN',  # Special ID for HR admin
                    notification_type='leave_request',
                    content=f"New leave request from {session.get('employee_id')}: {leave_request.leave_type} ({leave_request.start_date} to {leave_request.end_date})",
                    scheduled_for=datetime.now().isoformat()
                )
                
                return f"✅ Leave request submitted successfully!\n\n" \
                       f"Type: {leave_request.leave_type.title()}\n" \
                       f"Dates: {leave_request.start_date} to {leave_request.end_date}\n" \
                       f"Status: Pending approval\n\n" \
                       f"You'll receive updates via WhatsApp. Type 'menu' for more options!", True
            else:
                return "❌ Failed to submit leave request. Please try again or contact HR.", True
    
    def handle_support_ticket(self, session: Dict, user_input: str) -> tuple[str, bool]:
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
                return "📝 Enter ticket subject/title:", False
            else:
                return f"Please select a valid category: {', '.join(categories)}", False
        
        elif form['step'] == 'subject':
            if len(user_input) < 5:
                return "Subject is too short. Please provide a descriptive subject:", False
            form['data']['subject'] = user_input
            form['step'] = 'description'
            return "📄 Enter detailed description of your issue:", False
        
        elif form['step'] == 'description':
            if len(user_input) < 10:
                return "Please provide more details about your issue:", False
            form['data']['description'] = user_input
            form['step'] = 'priority'
            return "⚡ Select priority level (low, medium, high, urgent):", False
        
        elif form['step'] == 'priority':
            priorities = ['low', 'medium', 'high', 'urgent']
            if user_input.lower() in priorities:
                form['data']['priority'] = user_input.lower()
                
                # Generate ticket ID
                ticket_id = f"TK{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create and save ticket
                ticket = Ticket(
                    ticket_id=ticket_id,
                    employee_id=session.get('employee_id', 'UNKNOWN'),
                    category=form['data']['category'],
                    subject=form['data']['subject'],
                    description=form['data']['description'],
                    priority=form['data']['priority']
                )
                
                if self.db_manager.save_ticket(ticket):
                    # Schedule notification based on priority
                    notification_delay = {
                        'urgent': timedelta(minutes=5),
                        'high': timedelta(hours=1),
                        'medium': timedelta(hours=4),
                        'low': timedelta(hours=24)
                    }
                    
                    scheduled_time = datetime.now() + notification_delay[ticket.priority]
                    self.db_manager.schedule_notification(
                        employee_id='SUPPORT_TEAM',  # Special ID for support team
                        notification_type='support_ticket',
                        content=f"New {ticket.priority} priority ticket: {ticket.subject} ({ticket.ticket_id})",
                        scheduled_for=scheduled_time.isoformat()
                    )
                    
                    return f"🎫 Support ticket created successfully!\n\n" \
                           f"Ticket ID: {ticket.ticket_id}\n" \
                           f"Category: {ticket.category.title()}\n" \
                           f"Priority: {ticket.priority.title()}\n" \
                           f"Status: Open\n\n" \
                           f"Expected response time: {notification_delay[ticket.priority]}\n" \
                           f"You'll receive updates via WhatsApp. Type 'menu' for more options!", True
                else:
                    return "❌ Failed to create support ticket. Please try again or contact support directly.", True
            else:
                return f"Please select a valid priority: {', '.join(priorities)}", False
        
        return "Something went wrong. Please try again.", True

# Initialize form handler
form_handler = FormHandler()

# Enhanced message processing
# Initialize managers
db_manager = DatabaseManager()
session_manager = SessionManager()
menu_manager = MenuManager()
notification_prompt = NotificationPrompt(db_manager)

def process_message(phone_number: str, message: str) -> str:
    """Process incoming message with enhanced logic."""
    try:
        session = session_manager.get_session(phone_number)
        
        # Handle notification settings
        if message.lower() == 'notifications':
            if not session.get('employee_id'):
                return "Please provide your Employee ID first to manage notifications."
            session['state'] = 'notification_settings'
            return notification_prompt.get_settings_menu(session['employee_id'])
        
        # Handle notification setting updates
        if session.get('state') == 'notification_settings':
            if message in NotificationPrompt.NOTIFICATION_TYPES:
                setting_type = NotificationPrompt.NOTIFICATION_TYPES[message]
                settings = NotificationPrompt.NOTIFICATION_SETTINGS[setting_type]
                session['current_setting'] = setting_type
                session['state'] = 'notification_value'
                return f"*{settings['name']}*\n\n{settings['description']}\n\nChoose frequency:\n{', '.join(settings['frequency'])}"
            elif message.lower() == 'menu':
                session['state'] = 'main_menu'
                return menu_manager.get_menu_text("MAIN_MENU")
            return "Please select a valid option (1-5) or type 'menu' to go back."
        
        if session.get('state') == 'notification_value':
            setting_type = session.get('current_setting')
            if setting_type:
                response = notification_prompt.handle_setting_update(session['employee_id'], setting_type, message.lower())
                session['state'] = 'notification_settings'
                return response
        
        # Get employee info if available
        employee = db_manager.get_employee_by_phone(phone_number)
        employee_id = employee.employee_id if employee else None
        
        # Handle menu commands
        if message.lower() in ['menu', 'start', 'hi', 'hello', 'hey']:
            session['state'] = 'main_menu'
            return menu_manager.get_menu_text("MAIN_MENU")
        
        # Handle menu selections
        if session.get('state') == 'main_menu' and message.isdigit():
            response, updated_session = menu_manager.handle_menu_action(session, message)
            session.update(updated_session)
            return response
        
        # Log message and continue with existing logic
        db_manager.log_message(
            phone_number=phone_number,
            employee_id=employee_id,
            message_type="incoming",
            message_content=message,
            response_content="",
            response_time=0
        )
        
        # Continue with existing message processing...
        return "I'm processing your message..."
        
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        return "Sorry, I encountered an error. Please try again or contact support."

# User session storage (WARNING: NOT PRODUCTION READY - use a database like Redis/PostgreSQL for persistence)
user_sessions = {}

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
    4. If the information requested is not in the "COMPANY HR INFORMATION", politely state that you don't have that specific detail and direct them to contact HR directly at hr@elevatehr.com or call +1-555-0199.
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
        return "I'm having trouble processing your request right now. Please try again or contact HR directly at hr@elevatehr.com. Type 'menu' for main options or ask me anything else!"

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
            "🏢 *ElevateHR*\n\n"
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
    """Get or create user session with memory limits."""
    now = datetime.now()
    
    # Check session limit
    if phone_number not in user_sessions and len(user_sessions) >= MAX_SESSIONS:
        # Remove oldest session if limit reached
        oldest_number = min(user_sessions.keys(), key=lambda k: user_sessions[k]['last_active'])
        del user_sessions[oldest_number]
    
    if phone_number not in user_sessions or \
       (now - user_sessions[phone_number]['last_active']) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        user_sessions[phone_number] = {
            'state': 'initial',
            'last_action': None,
            'employee_id': None,
            'conversation_history': [],
            'last_active': now
        }
    
    user_sessions[phone_number]['last_active'] = now
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
    """Add message to conversation history with size limit."""
    session = get_user_session(phone_number)
    session['conversation_history'].append({
        'user': user_message[:500],  # Limit message size
        'bot': bot_response[:1000],  # Limit response size
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only recent conversations
    if len(session['conversation_history']) > MAX_CONVERSATION_HISTORY:
        session['conversation_history'] = session['conversation_history'][-MAX_CONVERSATION_HISTORY:]

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

class MenuManager:
    """Manages the menu system with submenus and navigation."""
    
    MAIN_MENU = {
        "1": {"name": "Employee Self-Service", "submenu": "EMPLOYEE_MENU"},
        "2": {"name": "Leave Management", "submenu": "LEAVE_MENU"},
        "3": {"name": "Support & Help", "submenu": "SUPPORT_MENU"},
        "4": {"name": "Reports & Analytics", "submenu": "REPORTS_MENU"},
        "5": {"name": "Profile & Settings", "submenu": "PROFILE_MENU"},
        "0": {"name": "Exit", "action": "exit"}
    }
    
    EMPLOYEE_MENU = {
        "1": {"name": "View Profile", "action": "view_profile"},
        "2": {"name": "Update Information", "action": "update_info"},
        "3": {"name": "View Payslips", "action": "view_payslips"},
        "4": {"name": "View Attendance", "action": "view_attendance"},
        "5": {"name": "View Benefits", "action": "view_benefits"},
        "9": {"name": "Back to Main Menu", "action": "main_menu"},
        "0": {"name": "Exit", "action": "exit"}
    }
    
    LEAVE_MENU = {
        "1": {"name": "Request Leave", "action": "request_leave"},
        "2": {"name": "View Leave Balance", "action": "view_leave_balance"},
        "3": {"name": "View Leave History", "action": "view_leave_history"},
        "4": {"name": "Cancel Leave Request", "action": "cancel_leave"},
        "9": {"name": "Back to Main Menu", "action": "main_menu"},
        "0": {"name": "Exit", "action": "exit"}
    }
    
    SUPPORT_MENU = {
        "1": {"name": "Create Support Ticket", "action": "create_ticket"},
        "2": {"name": "View My Tickets", "action": "view_tickets"},
        "3": {"name": "FAQs", "action": "view_faqs"},
        "4": {"name": "Chat with HR", "action": "chat_hr"},
        "9": {"name": "Back to Main Menu", "action": "main_menu"},
        "0": {"name": "Exit", "action": "exit"}
    }
    
    REPORTS_MENU = {
        "1": {"name": "Attendance Report", "action": "attendance_report"},
        "2": {"name": "Leave Report", "action": "leave_report"},
        "3": {"name": "Performance Report", "action": "performance_report"},
        "9": {"name": "Back to Main Menu", "action": "main_menu"},
        "0": {"name": "Exit", "action": "exit"}
    }
    
    PROFILE_MENU = {
        "1": {"name": "View Profile", "action": "view_profile"},
        "2": {"name": "Update Information", "action": "update_info"},
        "3": {"name": "Notification Settings", "action": "notification_settings"},
        "4": {"name": "Change Password", "action": "change_password"},
        "5": {"name": "Privacy Settings", "action": "privacy_settings"},
        "9": {"name": "Back to Main Menu", "action": "main_menu"},
        "0": {"name": "Exit", "action": "exit"}
    }
    
    def __init__(self):
        self.menus = {
            "MAIN_MENU": self.MAIN_MENU,
            "EMPLOYEE_MENU": self.EMPLOYEE_MENU,
            "LEAVE_MENU": self.LEAVE_MENU,
            "SUPPORT_MENU": self.SUPPORT_MENU,
            "REPORTS_MENU": self.REPORTS_MENU,
            "PROFILE_MENU": self.PROFILE_MENU
        }
    
    def get_menu_text(self, menu_name: str) -> str:
        """Generate formatted menu text for display."""
        if menu_name not in self.menus:
            return "Invalid menu"
            
        menu = self.menus[menu_name]
        menu_title = menu_name.replace("_", " ").title()
        
        menu_text = f"📱 *{menu_title}*\n\n"
        for key, item in menu.items():
            menu_text += f"{key}. {item['name']}\n"
        
        menu_text += "\nPlease reply with a number to select an option."
        return menu_text
    
    def get_action(self, menu_name: str, choice: str) -> tuple[str, Optional[str]]:
        """Get the action and submenu (if any) for a menu choice."""
        if menu_name not in self.menus or choice not in self.menus[menu_name]:
            return "invalid_choice", None
            
        menu_item = self.menus[menu_name][choice]
        if "submenu" in menu_item:
            return "show_menu", menu_item["submenu"]
        return menu_item["action"], None

    def handle_menu_action(self, session: Dict, choice: str) -> tuple[str, Dict]:
        """Handle menu selection and return appropriate response."""
        current_menu = session.get("current_menu", "MAIN_MENU")
        action, submenu = self.get_action(current_menu, choice)
        
        if action == "invalid_choice":
            return "⚠️ Invalid option. Please try again.", session
            
        if action == "show_menu":
            session["current_menu"] = submenu
            return self.get_menu_text(submenu), session
            
        if action == "main_menu":
            session["current_menu"] = "MAIN_MENU"
            return self.get_menu_text("MAIN_MENU"), session
            
        if action == "exit":
            session.clear()
            return "👋 Thank you for using ElevateHR Bot. Have a great day!", session
            
        # Update session with current action
        session["current_action"] = action
        return f"You selected: {action}", session

# Initialize menu manager
menu_manager = MenuManager()

class EmployeeService:
    """Handles employee self-service features."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def view_profile(self, employee_id: str) -> str:
        """Get formatted employee profile information."""
        employee = self.db.get_employee_by_id(employee_id)
        if not employee:
            return "⚠️ Employee not found."
        
        return (
            f"👤 *Employee Profile*\n\n"
            f"ID: {employee.employee_id}\n"
            f"Name: {employee.first_name} {employee.last_name}\n"
            f"Department: {employee.department}\n"
            f"Position: {employee.position}\n"
            f"Email: {employee.email}\n"
            f"Phone: {employee.phone_number}\n"
            f"Join Date: {employee.join_date}\n"
            f"Status: {employee.status.title()}"
        )
    
    def update_info(self, employee_id: str, field: str, value: str) -> str:
        """Update employee information."""
        employee = self.db.get_employee_by_id(employee_id)
        if not employee:
            return "⚠️ Employee not found."
            
        allowed_fields = ["email", "phone_number"]
        if field not in allowed_fields:
            return f"⚠️ Cannot update {field}. Only {', '.join(allowed_fields)} can be updated."
            
        # Validate input
        if field == "email" and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            return "⚠️ Invalid email format."
        if field == "phone_number" and not re.match(r"^\+\d{1,3}\d{10}$", value):
            return "⚠️ Invalid phone number format. Use international format (+XXX)."
            
        setattr(employee, field, value)
        if self.db.save_employee(employee):
            return f"✅ Successfully updated {field} to {value}."
        return "❌ Failed to update information. Please try again."
    
    def view_payslips(self, employee_id: str) -> str:
        """Get list of recent payslips."""
        # TODO: Implement payslip retrieval from database
        return (
            "🧾 *Recent Payslips*\n\n"
            "1. March 2024\n"
            "2. February 2024\n"
            "3. January 2024\n\n"
            "Reply with the number to view details."
        )
    
    def view_attendance(self, employee_id: str) -> str:
        """Get employee attendance summary."""
        # TODO: Implement attendance retrieval from database
        return (
            "📊 *Attendance Summary (March 2024)*\n\n"
            "Present: 18 days\n"
            "Absent: 2 days\n"
            "Late: 1 day\n"
            "Early Leave: 0 days\n\n"
            "Attendance Rate: 90%"
        )
    
    def view_benefits(self, employee_id: str) -> str:
        """Get employee benefits information."""
        # TODO: Implement benefits retrieval from database
        return (
            "🎁 *Your Benefits*\n\n"
            "Health Insurance:\n"
            "- Medical Coverage: $50,000\n"
            "- Dental Coverage: Basic Plan\n\n"
            "Leave Balance:\n"
            "- Annual Leave: 14 days\n"
            "- Sick Leave: 7 days\n"
            "- Personal Leave: 3 days\n\n"
            "Other Benefits:\n"
            "- Transportation Allowance\n"
            "- Meal Allowance\n"
            "- Professional Development"
        )
    
    def handle_action(self, action: str, employee_id: str, **kwargs) -> str:
        """Route and handle employee self-service actions."""
        action_handlers = {
            "view_profile": lambda: self.view_profile(employee_id),
            "update_info": lambda: self.update_info(employee_id, kwargs.get("field"), kwargs.get("value")),
            "view_payslips": lambda: self.view_payslips(employee_id),
            "view_attendance": lambda: self.view_attendance(employee_id),
            "view_benefits": lambda: self.view_benefits(employee_id)
        }
        
        handler = action_handlers.get(action)
        if not handler:
            return "⚠️ Invalid action requested."
        
        try:
            return handler()
        except Exception as e:
            logging.error(f"Error in EmployeeService.handle_action: {e}")
            return "❌ An error occurred. Please try again later."

# Initialize employee service
employee_service = EmployeeService(db_manager)

class ReportingService:
    """Handles analytics and reporting features."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_attendance_report(self, employee_id: str, month: Optional[str] = None) -> str:
        """Generate attendance report for an employee."""
        if not month:
            month = datetime.now().strftime("%B %Y")
            
        # TODO: Implement actual attendance data retrieval
        return (
            f"📊 *Attendance Report - {month}*\n\n"
            "Daily Summary:\n"
            "- Regular Days: 18\n"
            "- Weekends: 8\n"
            "- Holidays: 2\n"
            "- Leave Days: 2\n\n"
            "Time Analysis:\n"
            "- Average Check-in: 8:45 AM\n"
            "- Average Check-out: 5:15 PM\n"
            "- Total Work Hours: 160\n"
            "- Overtime Hours: 5\n\n"
            "Compliance:\n"
            "- Late Days: 2\n"
            "- Early Departures: 1\n"
            "- Missed Check-ins: 0\n"
            "- Attendance Rate: 90%"
        )
    
    def get_leave_report(self, employee_id: str, year: Optional[int] = None) -> str:
        """Generate leave report for an employee."""
        if not year:
            year = datetime.now().year
            
        # TODO: Implement actual leave data retrieval
        return (
            f"📅 *Leave Report - {year}*\n\n"
            "Leave Balance:\n"
            "- Annual Leave: 14 days remaining\n"
            "- Sick Leave: 7 days remaining\n"
            "- Personal Leave: 3 days remaining\n\n"
            "Leave History:\n"
            "1. Mar 15-16: Annual Leave (2 days)\n"
            "2. Feb 5: Sick Leave (1 day)\n"
            "3. Jan 22-24: Annual Leave (3 days)\n\n"
            "Pending Requests:\n"
            "- Apr 10-12: Annual Leave (Pending)\n\n"
            "Statistics:\n"
            "- Total Days Taken: 6\n"
            "- Planned Leave: 3\n"
            "- Emergency Leave: 1"
        )
    
    def get_performance_report(self, employee_id: str, period: Optional[str] = None) -> str:
        """Generate performance report for an employee."""
        if not period:
            period = f"Q{(datetime.now().month-1)//3 + 1} {datetime.now().year}"
            
        # TODO: Implement actual performance data retrieval
        return (
            f"⭐ *Performance Report - {period}*\n\n"
            "Key Performance Indicators:\n"
            "1. Task Completion: 95%\n"
            "2. Quality of Work: 4.5/5\n"
            "3. Timeliness: 4.2/5\n"
            "4. Team Collaboration: 4.8/5\n\n"
            "Goals Progress:\n"
            "- Complete Project X: 80%\n"
            "- Skills Development: On Track\n"
            "- Client Satisfaction: Exceeded\n\n"
            "Achievements:\n"
            "- Employee of the Month (Feb)\n"
            "- 3 Client Appreciations\n"
            "- 2 Innovation Ideas\n\n"
            "Areas for Development:\n"
            "- Time Management\n"
            "- Technical Documentation"
        )
    
    def handle_report_action(self, action: str, employee_id: str, **kwargs) -> str:
        """Route and handle reporting actions."""
        action_handlers = {
            "attendance_report": lambda: self.get_attendance_report(
                employee_id, 
                kwargs.get("month")
            ),
            "leave_report": lambda: self.get_leave_report(
                employee_id,
                kwargs.get("year")
            ),
            "performance_report": lambda: self.get_performance_report(
                employee_id,
                kwargs.get("period")
            )
        }
        
        handler = action_handlers.get(action)
        if not handler:
            return "⚠️ Invalid report type requested."
            
        try:
            return handler()
        except Exception as e:
            logging.error(f"Error in ReportingService.handle_report_action: {e}")
            return "❌ An error occurred while generating the report. Please try again later."

# Initialize reporting service
reporting_service = ReportingService(db_manager)

class NotificationPrompt:
    """Handles notification preferences and settings prompts."""
    
    NOTIFICATION_TYPES = {
        "1": "leave_updates",
        "2": "ticket_updates",
        "3": "daily_summary",
        "4": "reminders",
        "5": "announcements"
    }
    
    NOTIFICATION_SETTINGS = {
        "leave_updates": {
            "name": "Leave Request Updates",
            "description": "Updates about your leave requests status",
            "frequency": ["instant", "daily"],
            "default": "instant"
        },
        "ticket_updates": {
            "name": "Support Ticket Updates",
            "description": "Updates about your support tickets",
            "frequency": ["instant", "daily"],
            "default": "instant"
        },
        "daily_summary": {
            "name": "Daily Summary",
            "description": "Daily summary of your pending items and tasks",
            "frequency": ["morning", "evening", "both", "off"],
            "default": "evening"
        },
        "reminders": {
            "name": "Task Reminders",
            "description": "Reminders for pending tasks and deadlines",
            "frequency": ["1_day_before", "3_days_before", "1_week_before", "off"],
            "default": "1_day_before"
        },
        "announcements": {
            "name": "Company Announcements",
            "description": "Important company-wide announcements",
            "frequency": ["instant", "daily", "off"],
            "default": "instant"
        }
    }
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_settings_menu(self, employee_id: str) -> str:
        """Get notification settings menu."""
        current_settings = self._get_user_settings(employee_id)
        
        menu = "🔔 *Notification Settings*\n\n"
        menu += "Choose a notification type to configure:\n\n"
        
        for key, notif_type in self.NOTIFICATION_TYPES.items():
            settings = self.NOTIFICATION_SETTINGS[notif_type]
            current = current_settings.get(notif_type, settings['default'])
            menu += f"{key}. {settings['name']}\n"
            menu += f"   Current: {current}\n\n"
        
        menu += "\nType a number (1-5) to configure, or 'menu' to go back."
        return menu
    
    def handle_setting_update(self, employee_id: str, setting_type: str, new_value: str) -> str:
        """Handle notification setting update."""
        if setting_type not in self.NOTIFICATION_SETTINGS:
            return "❌ Invalid notification type. Please try again."
        
        settings = self.NOTIFICATION_SETTINGS[setting_type]
        if new_value not in settings['frequency']:
            return f"❌ Invalid value. Please choose from: {', '.join(settings['frequency'])}"
        
        self._update_user_settings(employee_id, setting_type, new_value)
        
        return f"✅ Updated {settings['name']} to: {new_value}\n\nType 'notifications' to see all settings."
    
    def _get_user_settings(self, employee_id: str) -> dict:
        """Get user's notification settings from database."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT notification_settings
                FROM user_sessions
                WHERE phone_number = ?
            ''', (employee_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return json.loads(result[0])
            return {}
            
        except Exception as e:
            logging.error(f"Error getting notification settings: {e}")
            return {}
    
    def _update_user_settings(self, employee_id: str, setting_type: str, value: str):
        """Update user's notification settings in database."""
        try:
            current_settings = self._get_user_settings(employee_id)
            current_settings[setting_type] = value
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_sessions
                SET session_data = ?
                WHERE phone_number = ?
            ''', (json.dumps(current_settings), employee_id))
            conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"Error updating notification settings: {e}")

# Initialize notification service
notification_service = NotificationService(db_manager, client)

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