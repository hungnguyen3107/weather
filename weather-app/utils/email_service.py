import os
from flask_mail import Mail, Message
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EmailService:
    def __init__(self, app):
        self.mail = Mail(app)

    def send_email(self, subject, recipients, body):
        try:
            msg = Message(subject, recipients=recipients)
            msg.body = body
            self.mail.send(msg)
            logging.info(f"Email sent to {recipients}")
        except ConnectionRefusedError as e:
            logging.error(f"Failed to connect to the mail server: {str(e)}")
        except TimeoutError as e:
            logging.error(f"Timeout occurred while sending email to {recipients}: {str(e)}")
        except Exception as e:
            logging.error(f"Failed to send email to {recipients}: {str(e)}")
