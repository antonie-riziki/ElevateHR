import os
import json
import requests
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

load_dotenv()
app = Flask(__name__)

# Environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# User session storage (in production, use a database)
user_sessions = {}

def send_main_menu(to_number):
    """Send the main menu with interactive buttons."""
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body="🏢 *HR Assistant Bot*\n\nHello! How can I assist you today? Please choose an option by typing the number:\n\n1️⃣ Payroll Inquiry\n2️⃣ Leave Request\n3️⃣ Company Policies\n4️⃣ Document Request\n5️⃣ Support & Feedback\n\n_Type the number of your choice (1-5)_"
        )
        return True
    except Exception as e:
        print(f"Error sending main menu: {e}")
        return False

def send_leave_options(to_number):
    """Send leave request options."""
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body="🏖️ *Leave Request*\n\nYou can apply for leave via our company portal. Our company's leave policy includes:\n\n✅ 20 paid leave days per year\n✅ National holidays\n✅ Sick leave provisions\n\nWould you like the portal link?\n\n1️⃣ Yes, send me the link\n2️⃣ No, thanks\n3️⃣ Back to main menu"
        )
        return True
    except Exception as e:
        print(f"Error sending leave options: {e}")
        return False

def send_policy_options(to_number):
    """Send company policy options."""
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body="📋 *Company Policies*\n\nWhich policy would you like to know more about?\n\n1️⃣ Working Hours\n2️⃣ Remote Work Policy\n3️⃣ Health Insurance\n4️⃣ Code of Conduct\n5️⃣ Back to main menu\n\n_Type the number of your choice_"
        )
        return True
    except Exception as e:
        print(f"Error sending policy options: {e}")
        return False

def get_user_session(phone_number):
    """Get or create user session."""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'state': 'main_menu',
            'last_action': None
        }
    return user_sessions[phone_number]

def update_user_session(phone_number, state, last_action=None):
    """Update user session."""
    user_sessions[phone_number] = {
        'state': state,
        'last_action': last_action
    }

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    """Handle incoming WhatsApp messages."""
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")
    
    # Get user session
    session = get_user_session(from_number)
    
    resp = MessagingResponse()
    
    # Handle greetings and menu requests
    if any(greeting in incoming_msg.lower() for greeting in ["hi", "hello", "hey", "start", "menu"]):
        send_main_menu(from_number)
        update_user_session(from_number, 'main_menu')
        return str(resp)
    
    # Handle main menu selections
    if session['state'] == 'main_menu' or incoming_msg in ['1', '2', '3', '4', '5']:
        if incoming_msg == '1':
            resp.message("💰 *Payroll Inquiry*\n\nTo check your payroll status, please provide your employee ID.\n\n📅 Our company payday is on the 25th of each month.\n💳 Salary slips are available in the employee portal.\n\nPlease share your Employee ID to proceed, or type 'menu' to return to main menu.")
            update_user_session(from_number, 'payroll_inquiry')
            
        elif incoming_msg == '2':
            send_leave_options(from_number)
            update_user_session(from_number, 'leave_request')
            
        elif incoming_msg == '3':
            send_policy_options(from_number)
            update_user_session(from_number, 'company_policies')
            
        elif incoming_msg == '4':
            resp.message("📄 *Document Request*\n\nI can help you request the following documents:\n\n• Salary Certificate\n• Employment Letter\n• Experience Certificate\n• Tax Documents\n\nPlease provide:\n1️⃣ Your Employee ID\n2️⃣ Document type needed\n\nExample: 'EMP001 - Salary Certificate'\n\nOr type 'menu' to return to main menu.")
            update_user_session(from_number, 'document_request')
            
        elif incoming_msg == '5':
            resp.message("🎧 *Support & Feedback*\n\nPlease describe your issue or feedback below. Your message will be forwarded to the HR team confidentially.\n\n📧 You can also reach us at: hr@company.com\n📞 Phone: +1-XXX-XXX-XXXX\n\nType your message or 'menu' to return to main menu.")
            update_user_session(from_number, 'support_feedback')
            
        else:
            resp.message("Please select a valid option (1-5) or type 'menu' to see all options.")
    
    # Handle leave request flow
    elif session['state'] == 'leave_request':
        if incoming_msg == '1':
            resp.message("🔗 *Leave Portal Link*\n\nHere is the link to apply for leave:\n👉 https://company-portal.com/leave-application\n\n📋 Required documents:\n• Medical certificate (for sick leave)\n• Travel itinerary (for vacation)\n\n⏰ Apply at least 2 weeks in advance for planned leave.\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
            
        elif incoming_msg == '2':
            resp.message("No problem! If you need any other assistance, type 'menu' to see all options.")
            update_user_session(from_number, 'main_menu')
            
        elif incoming_msg == '3':
            send_main_menu(from_number)
            update_user_session(from_number, 'main_menu')
            
        else:
            resp.message("Please select 1, 2, or 3. Type 'menu' to return to main menu.")
    
    # Handle company policies flow
    elif session['state'] == 'company_policies':
        if incoming_msg == '1':
            resp.message("🕐 *Working Hours Policy*\n\n• Standard hours: 9:00 AM - 5:00 PM\n• Flexible timing: 8:00 AM - 6:00 PM window\n• Core hours: 10:00 AM - 3:00 PM (mandatory)\n• Lunch break: 1 hour\n• Weekly hours: 40 hours\n\n📱 Use the time tracking app for check-in/out.\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
            
        elif incoming_msg == '2':
            resp.message("🏠 *Remote Work Policy*\n\n• Available 2 days per week\n• Prior approval required\n• Productivity metrics maintained\n• Core team hours: 10 AM - 3 PM\n• Stable internet connection mandatory\n\n📋 Submit remote work request via portal.\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
            
        elif incoming_msg == '3':
            resp.message("🏥 *Health Insurance Policy*\n\n• Coverage: Employee + Family\n• Premium: 80% company, 20% employee\n• Network hospitals: 500+\n• Annual health checkup included\n• Maternity benefits available\n\n📞 Insurance helpline: 1-800-XXX-XXXX\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
            
        elif incoming_msg == '4':
            resp.message("📜 *Code of Conduct*\n\n• Professional behavior expected\n• Zero tolerance for harassment\n• Confidentiality agreements\n• Dress code: Business casual\n• Social media guidelines apply\n\n📖 Full document available in employee handbook.\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
            
        elif incoming_msg == '5':
            send_main_menu(from_number)
            update_user_session(from_number, 'main_menu')
            
        else:
            resp.message("Please select 1-5. Type 'menu' to return to main menu.")
    
    # Handle payroll inquiry flow
    elif session['state'] == 'payroll_inquiry':
        if incoming_msg.upper().startswith('EMP') or incoming_msg.isdigit():
            resp.message(f"✅ *Payroll Status for ID: {incoming_msg}*\n\n📊 Current Status: Processed\n💰 Last Payment: $X,XXX (25th of last month)\n📅 Next Payment: 25th of this month\n🎯 YTD Earnings: $XX,XXX\n\n📧 Detailed payslip sent to your registered email.\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
        else:
            resp.message("Please provide a valid Employee ID (e.g., EMP001) or type 'menu' to return to main menu.")
    
    # Handle document request flow
    elif session['state'] == 'document_request':
        if '-' in incoming_msg and any(doc in incoming_msg.lower() for doc in ['salary', 'employment', 'experience', 'tax']):
            resp.message(f"✅ *Document Request Submitted*\n\n📋 Request: {incoming_msg}\n⏰ Processing time: 2-3 business days\n📧 Document will be sent to your registered email\n📞 Contact HR if urgent\n\n🎫 Reference ID: DOC{hash(incoming_msg) % 10000}\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
        else:
            resp.message("Please provide your request in format: 'Employee ID - Document Type'\n\nExample: 'EMP001 - Salary Certificate'\n\nOr type 'menu' to return to main menu.")
    
    # Handle support feedback flow
    elif session['state'] == 'support_feedback':
        if len(incoming_msg) > 10:
            resp.message("✅ *Feedback Submitted*\n\nThank you for your feedback! Your message has been forwarded to the HR team.\n\n📧 You'll receive a response within 24-48 hours\n🎫 Reference ID: SUP" + str(hash(incoming_msg) % 10000) + "\n\nType 'menu' to return to main menu.")
            update_user_session(from_number, 'main_menu')
        else:
            resp.message("Please provide more details about your feedback or issue. Type 'menu' to return to main menu.")
    
    # Default response
    else:
        resp.message("I'm sorry, I didn't understand that. Please type 'menu' to see all available options.")
        update_user_session(from_number, 'main_menu')

    return str(resp)

@app.route("/", methods=["GET"])
def home():
    """Health check endpoint."""
    return "HR WhatsApp Bot is running!"

if __name__ == "__main__":
    print("Starting HR WhatsApp Bot...")
    print("Make sure to set your environment variables:")
    print("- TWILIO_ACCOUNT_SID")
    print("- TWILIO_AUTH_TOKEN") 
    print("- TWILIO_WHATSAPP_NUMBER")
    app.run(debug=True, port=5000)