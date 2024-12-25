import sys

from django.core.mail import EmailMultiAlternatives
from django.template import RequestContext, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.conf import settings
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import os


def send_active_mail(subject, email_template_name,
              context, to_email, html_email_template_name=None, request=None, from_email=None):
    """
    Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
    """
    
    ctx_dict = {}
    if request is not None:
        ctx_dict = RequestContext(request, ctx_dict)
    if context:
        ctx_dict.update(context)
    

    # Email subject *must not* contain newlines
    from_email = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL')
    if email_template_name:
        
        message_txt = render_to_string(email_template_name,
                                       ctx_dict)

        email_message = EmailMultiAlternatives(subject, message_txt,
                                               from_email, to_email)
    else:
        try:
            message_html = render_to_string(
                html_email_template_name, ctx_dict)
            email_message = EmailMultiAlternatives(subject, message_html,
                                                    from_email, to_email)
            email_message.content_subtype = 'html'

        
        except TemplateDoesNotExist:
            pass

    try:
        email_message.send()
    except:
        if settings.DEBUG:
            print('Inside')
            print(sys.exc_info())


def send_mail(to_email, subject, message):
    try:
        
        sg = sendgrid.SendGridAPIClient(api_key=getattr(settings, 'EMAIL_HOST_PASSWORD'))
        from_email = Email(getattr(settings, 'DEFAULT_FROM_EMAIL'))  # Change to your verified sender
        to_email = To(to_email)  # Change to your recipient
        subject = subject
        content = Content("text/html", message)
        mail = Mail(from_email, to_email, subject, content)

        # Get a JSON-ready representation of the Mail object
        mail_json = mail.get()
        # Send an HTTP POST request to /mail/send
        response = sg.client.mail.send.post(request_body=mail_json)
    except Exception as e:
        print(f"An error occurred: {e}")
