import os
from dotenv import load_dotenv
from twilio.rest import Client
import sqlite3
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Twilio setup
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ADMIN_PHONE = os.getenv("ADMIN_PHONE")

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def test_send_notification():
    """Test sending a basic notification."""
    try:
        message = client.messages.create(
            body="🔔 Test notification from HR Bot!\n\nThis is a test message to verify notifications are working.",
            from_=TWILIO_WHATSAPP_NUMBER,
            to=ADMIN_PHONE
        )
        print(f"✅ Test notification sent successfully! SID: {message.sid}")
    except Exception as e:
        print(f"❌ Error sending test notification: {e}")

def test_leave_reminder():
    """Test leave request reminder notification."""
    try:
        message = client.messages.create(
            body="🏖️ Leave Request Reminder\n\nYou have a pending leave request:\nType: Annual Leave\nDates: 2024-04-01 to 2024-04-05\nStatus: Pending Approval\n\nPlease check your dashboard for updates.",
            from_=TWILIO_WHATSAPP_NUMBER,
            to=ADMIN_PHONE
        )
        print(f"✅ Leave reminder sent successfully! SID: {message.sid}")
    except Exception as e:
        print(f"❌ Error sending leave reminder: {e}")

def test_ticket_update():
    """Test support ticket update notification."""
    try:
        message = client.messages.create(
            body="🎫 Support Ticket Update\n\nTicket #TK123456\nStatus: In Progress\nCategory: IT Support\nUpdate: Your request is being processed by our IT team.\n\nReply with 'ticket status' to check latest updates.",
            from_=TWILIO_WHATSAPP_NUMBER,
            to=ADMIN_PHONE
        )
        print(f"✅ Ticket update sent successfully! SID: {message.sid}")
    except Exception as e:
        print(f"❌ Error sending ticket update: {e}")

def test_daily_summary():
    """Test daily summary notification."""
    try:
        message = client.messages.create(
            body="📊 Daily Summary Report\n\nPending Items:\n- 2 Leave Requests\n- 3 Support Tickets\n- 1 Document Request\n\nUpcoming Events:\n- Team Meeting (Tomorrow, 10 AM)\n- Monthly Review (Next Week)\n\nType 'menu' for more options.",
            from_=TWILIO_WHATSAPP_NUMBER,
            to=ADMIN_PHONE
        )
        print(f"✅ Daily summary sent successfully! SID: {message.sid}")
    except Exception as e:
        print(f"❌ Error sending daily summary: {e}")

if __name__ == "__main__":
    print("🚀 Starting notification tests...")
    
    # Check environment variables
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, ADMIN_PHONE]):
        print("❌ Error: Missing required environment variables!")
        print(f"TWILIO_ACCOUNT_SID: {'✅' if TWILIO_ACCOUNT_SID else '❌'}")
        print(f"TWILIO_AUTH_TOKEN: {'✅' if TWILIO_AUTH_TOKEN else '❌'}")
        print(f"TWILIO_WHATSAPP_NUMBER: {'✅' if TWILIO_WHATSAPP_NUMBER else '❌'}")
        print(f"ADMIN_PHONE: {'✅' if ADMIN_PHONE else '❌'}")
        exit(1)
    
    # Run tests
    print("\n1️⃣ Testing basic notification...")
    test_send_notification()
    
    print("\n2️⃣ Testing leave reminder...")
    test_leave_reminder()
    
    print("\n3️⃣ Testing ticket update...")
    test_ticket_update()
    
    print("\n4️⃣ Testing daily summary...")
    test_daily_summary()
    
    print("\n✨ Notification tests completed!") 