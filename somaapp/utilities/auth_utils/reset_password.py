from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
import os
import requests


SOMA_LOGO_URL = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/public/somapng.png"


def send_password_reset_email(email, reset_token):
    """
    Send a password reset email to the user.

    This function prefers using the Resend API when RESEND_API_KEY is configured.
    If Resend is not configured, it falls back to Django's SMTP email backend.

    Args:
        email (str): The user's email address
        reset_token (str): The JWT token for password reset

    Returns:
        bool: True if email sent successfully, False otherwise
    """

    # Create the reset link
    reset_link = f"{settings.FRONTEND_URL}/authentication/changepassword?token={reset_token}"

    # Email subject
    subject = "Reset Your BOX Password"

    # Email message (HTML)
    html_message = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8" />
            <title>Reset Your SOMA Password</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center;">
                    <h1 style="font-weight: bold; font-size: 18px; color: rgb(2, 8, 23); margin-bottom: 16px;">BOX</h1>
                </div>
                <h2 style="color: rgb(2, 8, 23);">Password Reset Request</h2>
                <p style="color: rgb(2, 8, 23);">Hello,</p>
                <p style="color: rgb(2, 8, 23);">
                    We received a request to reset your password for your BOX account.
                    Click the button below to reset your password:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}"
                       style="background-color: rgb(2, 8, 23); color: white; padding: 12px 24px; text-decoration: none; border-radius: 12px; display: inline-block;">
                        Reset Password
                    </a>
                </div>
                <p style="color: rgb(2, 8, 23);">
                    If you didn't request this password reset, you can safely ignore this email.
                </p>
                <p style="color: rgb(2, 8, 23);">This link will expire in 1 hour.</p>
                <p style="color: rgb(2, 8, 23);">Best regards,<br>The BOX Team</p>
                <hr style="border: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">
                    If the button above doesn't work, copy and paste this link into your browser:<br>
                    <span style="color: #2c3e50; word-break: break-all;">{reset_link}</span>
                </p>
            </div>
        </body>
    </html>
    """

    # Plain text version of the message
    plain_message = strip_tags(html_message)

    try:
        resend_api_key = os.getenv("RESEND_API_KEY")
        resend_from_email = os.getenv(
            "RESEND_FROM_EMAIL", getattr(settings, "DEFAULT_FROM_EMAIL", "onboarding@resend.dev")
        )

        # Prefer Resend if configured
        if resend_api_key:
            _send_via_resend(
                api_key=resend_api_key,
                from_email=resend_from_email,
                to_email=email,
                subject=subject,
                html_message=html_message,
                plain_message=plain_message,
            )
            return True

        # Fallback to SMTP using Django's email backend
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        # Log and return False so the calling view can return a proper error response
        print(f"[RESET_PASSWORD_EMAIL] Error sending email to {email}: {str(e)}")
        return False


def _send_via_resend(api_key, from_email, to_email, subject, html_message, plain_message):
    """
    Internal helper to send email via Resend API.
    """
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_message,
        "text": plain_message,
    }

    response = requests.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code not in (200, 202):
        try:
            error_data = response.json()
            error_msg = error_data.get("message", f"HTTP {response.status_code}")
        except Exception:
            error_msg = f"HTTP {response.status_code}"
        raise Exception(f"Resend API error: {error_msg}")