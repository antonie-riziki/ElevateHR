import os
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()
app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    """Respond to incoming WhatsApp messages."""
    incoming_msg = request.values.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "hi" in incoming_msg or "hello" in incoming_msg:
        msg.body(
            "Hello! How can I assist you today? You can ask about:\n"
            "- Payroll\n"
            "- Leave Requests\n"
            "- Company Policies\n"
            "- Document Requests\n"
            "- Support & Feedback"
        )
    elif "payroll" in incoming_msg:
        msg.body(
            "To check your payroll status, please provide your employee ID.\n\n"
            "Our company payday is on the 25th of each month."
        )
    elif "leave" in incoming_msg:
        response_text = (
            "You can apply for leave via our company portal. Would you like the link?\n\n"
            "Our company's leave policy includes 20 paid leave days per year, plus national holidays."
        )
        msg.body(response_text)
    elif "policy" in incoming_msg or "policies" in incoming_msg:
        msg.body(
            "I can provide information on:\n"
            "- Working Hours\n"
            "- Remote Work Policy\n"
            "- Health Insurance\n"
            "Which policy would you like to know more about?"
        )
    elif "document" in incoming_msg:
        msg.body(
            "To request a document like a salary certificate or employment letter, "
            "please provide your employee ID and the name of the document. "
            "We will process your request and send it to your registered email."
        )
    elif "feedback" in incoming_msg or "support" in incoming_msg or "issue" in incoming_msg:
        msg.body(
            "Please describe the issue or feedback you would like to submit. "
            "Your message will be forwarded to the HR team confidentially."
        )
    else:
        msg.body(
            "I'm sorry, I didn't understand that. Please type 'Hi' to see the main menu."
        )

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
