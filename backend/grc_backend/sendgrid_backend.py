"""
SendGrid Email Backend for Django.
Production-ready email sending via SendGrid API.
"""

import os
from django.core.mail.backends.base import BaseEmailBackend
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class SendgridBackend(BaseEmailBackend):
    """
    Django email backend using SendGrid API.
    Provides reliable email delivery with tracking and retries.
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.client = SendGridAPIClient(self.api_key) if self.api_key else None
    
    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """
        if not self.client or not self.api_key:
            if not self.fail_silently:
                raise ValueError("SENDGRID_API_KEY not configured")
            return 0
        
        num_sent = 0
        for message in email_messages:
            try:
                mail = self._build_mail(message)
                self.client.send(mail)
                num_sent += 1
            except Exception as e:
                if not self.fail_silently:
                    raise
        
        return num_sent
    
    def _build_mail(self, message):
        """Build a SendGrid Mail object from Django EmailMessage."""
        mail = Mail(
            from_email=Email(message.from_email),
            to_emails=[To(recipient) for recipient in message.to],
            subject=message.subject,
            html_content=message.body if message.content_subtype == 'html' else None,
            plain_text_content=message.body if message.content_subtype == 'plain' else None,
        )
        
        # Add CC recipients
        if message.cc:
            for cc_recipient in message.cc:
                mail.add_cc(Email(cc_recipient))
        
        # Add BCC recipients
        if message.bcc:
            for bcc_recipient in message.bcc:
                mail.add_bcc(Email(bcc_recipient))
        
        # Add reply-to
        if message.reply_to:
            mail.reply_to = Email(message.reply_to[0])
        
        return mail
