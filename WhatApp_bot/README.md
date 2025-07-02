# WhatsApp HR Bot

This is a simple WhatsApp HR Bot built with Python, Flask, and Twilio.

## Setup

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Environment Variables:**
    Create a `.env` file in the root directory by copying the `.env.example` file:
    ```bash
    cp .env.example .env
    ```
    Open the `.env` file and add your Twilio Account SID, Auth Token, and Twilio WhatsApp number. You can find these in your [Twilio Console](https://www.twilio.com/console).

3.  **Run the Flask Server:**
    ```bash
    python app.py
    ```
    The server will start on `http://127.0.0.1:5000`.

4.  **Expose your Local Server to the Internet:**
    To allow Twilio to send messages to your local server, you need to expose it to the public internet. We recommend using `ngrok`.
    ```bash
    ngrok http 5000
    ```
    `ngrok` will provide you with a public `https Forwarding` URL (e.g., `https://xxxx-xxxx.ngrok.io`).

5.  **Configure Twilio Webhook:**
    - Go to your Twilio Sandbox for WhatsApp settings in the console.
    - Find the "When a message comes in" field.
    - Enter the `ngrok` forwarding URL followed by `/whatsapp` (e.g., `https://xxxx-xxxx.ngrok.io/whatsapp`).
    - Make sure the method is set to `HTTP POST`.
    - Save the configuration.

6.  **Test the Bot:**
    - Send a message from your sandboxed WhatsApp number to the Twilio number.
    - You should receive a reply from the bot.
