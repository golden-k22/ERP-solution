from twilio.rest import Client
import os



def send_whatsapp_msg(to_address, message):
    try:
        # Twilio credentials
        account_sid = os.getenv("WHATSAPP_SID") # 'your_account_sid'
        auth_token = os.getenv("WHATSAPP_AUTH_TOKEN") # 'your_auth_token'
        from_address=os.getenv('WHATSAPP_FROM') # Twilio's sandbox number for WhatsApp
        client = Client(account_sid, auth_token)

        # Sending message
        message = client.messages.create(
            from_=from_address,  
            body=message,
            to=f"+65{to_address}"  # Recipient's WhatsApp number
        )

        # print(f"Message sent with SID: {message.sid}")
    except Exception as e:
        print(f"An error occurred in whatsApp messaging: {e}")
