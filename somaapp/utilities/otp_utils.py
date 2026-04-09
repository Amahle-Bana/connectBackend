import random
import string
import os
import requests
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from ..models import OTP, User
from django.utils import timezone


def generate_otp():
    """Generate a 6-digit OTP"""
    return "".join(random.choices(string.digits, k=6))


def send_otp_email(email, otp_code):
    """
    Send OTP email to user.

    Args:
        email (str): The user's email address
        otp_code (str): The OTP code to send

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Verify Your SOMA Account"

    html_message = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8" />
            <title>Verify Your SOMA Account</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center;">
                    <img src="{settings.FRONTEND_URL}/public/somapng.png" alt="Soma AI" style="width: 100px; height: auto; margin-bottom: 8px;" />
                    <h1 style="font-weight: bold; font-size: 18px; color: rgb(2, 8, 23); margin-bottom: 16px;">Soma AI</h1>
                </div>
                <h2 style="color: rgb(2, 8, 23);">Verify Your Account</h2>
                <p style="color: rgb(2, 8, 23);">
                    Welcome to SOMA! To complete your account verification, please use the following One-Time Password (OTP):
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background-color: rgb(2, 8, 23); color: white; padding: 20px; border-radius: 12px; display: inline-block;">
                        <h3 style="margin: 0; font-size: 24px; letter-spacing: 8px;">{otp_code}</h3>
                    </div>
                </div>
                <p style="color: rgb(2, 8, 23);">
                    This OTP will expire in 10 minutes. Please enter it in the verification page to complete your account setup.
                </p>
                <p style="color: rgb(2, 8, 23);">
                    If you didn't request this verification, please ignore this email.
                </p>
                <p style="color: rgb(2, 8, 23);">Best regards,<br>The SOMA Team</p>
                <hr style="border: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">
                    If the OTP above doesn't work, please contact our support team.
                </p>
            </div>
        </body>
    </html>
    """

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
        print(f"[OTP_EMAIL] Error sending OTP email to {email}: {str(e)}")
        return False


def create_and_send_otp(email):
    """
    Create a new OTP for the given email and send it.

    Args:
        email (str): The user's email address

    Returns:
        tuple: (success: bool, otp_object: OTP or None, message: str)
    """
    try:
        # Invalidate any existing OTPs for this email
        OTP.objects.filter(email=email, is_used=False).update(is_used=True)

        # Generate new OTP
        otp_code = generate_otp()

        # Create OTP record
        otp = OTP.objects.create(
            email=email,
            otp_code=otp_code
        )

        # Send OTP email
        if send_otp_email(email, otp_code):
            return True, otp, "OTP sent successfully"
        else:
            # If email sending fails, mark OTP as used and return error
            otp.is_used = True
            otp.save()
            return False, None, "Failed to send OTP email"

    except Exception as e:
        print(f"Error creating OTP: {str(e)}")
        return False, None, f"Error creating OTP: {str(e)}"


def verify_otp(email, otp_code):
    """
    Verify the OTP for the given email.

    Args:
        email (str): The user's email address
        otp_code (str): The OTP code to verify

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Find the most recent unused OTP for this email
        otp = OTP.objects.filter(
            email=email,
            otp_code=otp_code,
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            return False, "Invalid OTP"

        if otp.is_expired():
            return False, "OTP has expired"

        # Mark OTP as used
        otp.is_used = True
        otp.save()

        return True, "OTP verified successfully"

    except Exception as e:
        print(f"Error verifying OTP: {str(e)}")
        return False, f"Error verifying OTP: {str(e)}"


def _send_via_resend(api_key, from_email, to_email, subject, html_message, plain_message):
    """
    Internal helper to send OTP email via Resend API.
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
