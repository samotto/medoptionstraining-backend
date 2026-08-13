import html
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import get_settings


settings = get_settings()


class EmailDeliveryError(RuntimeError):
    pass


def build_verification_url(token: str) -> str:
    separator = "&" if "?" in settings.frontend_url else "?"
    return f"{settings.frontend_url.rstrip('/')}{separator}{urlencode({'verify_token': token})}"


def send_verification_email(email: str, token: str) -> None:
    if not settings.resend_api_key:
        raise EmailDeliveryError("RESEND_API_KEY is not configured")

    verification_url = build_verification_url(token)
    safe_url = html.escape(verification_url, quote=True)
    payload = {
        "from": settings.email_from,
        "to": [email],
        "subject": "Confirm your Med Options Training account",
        "html": (
            "<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto'>"
            "<h2>Med Options Training</h2>"
            "<p>Confirm your email address to finish creating your account.</p>"
            f"<p><a href='{safe_url}' style='display:inline-block;padding:12px 20px;"
            "background:#3f51b5;color:#fff;text-decoration:none;border-radius:6px'>"
            "Confirm email and log in</a></p>"
            f"<p>This link expires in {settings.email_verification_minutes} minutes.</p>"
            "<p>If you did not create this account, you can ignore this email.</p>"
            "</div>"
        ),
    }
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "medoptionstraining-backend/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise EmailDeliveryError(f"Resend returned HTTP {response.status}")
    except HTTPError as exc:
        raise EmailDeliveryError(f"Resend rejected the email with HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise EmailDeliveryError("Could not connect to Resend") from exc
