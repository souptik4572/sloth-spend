"""The emails SlothSpend sends, in the app's calm voice. Plain text first; the HTML part is the same words.

Every link points at SLOTH_PUBLIC_URL with its token in the query string; the web app removes the token from the
address bar as soon as it reads it, and every page is served with Referrer-Policy: no-referrer.
"""

from html import escape
from urllib.parse import quote

from .config import web
from .mailer import build

SIGN_OFF = "— Sloth, from SlothSpend\n\nSlothSpend informs, never acts. It never cancels anything or contacts anyone for you."


def _html(paragraphs: list[str], button: tuple[str, str] | None = None) -> str:
    body = "".join(f'<p style="margin:0 0 16px">{escape(p)}</p>' for p in paragraphs)
    if button:
        label, url = button
        body += (f'<p style="margin:24px 0"><a href="{escape(url)}" style="display:inline-block;padding:14px 22px;'
                 f'border-radius:9999px;background:#0B051D;color:#F9F8F5;text-decoration:none;font-weight:500">'
                 f'{escape(label)}</a></p><p style="margin:0 0 16px;color:#504F5F;font-size:14px">'
                 f'Or paste this link into your browser: {escape(url)}</p>')
    return (f'<div style="font-family:Inter,-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:16px;'
            f'line-height:1.5;color:#0B051D;max-width:520px">{body}'
            f'<p style="margin:24px 0 0;color:#504F5F;font-size:14px">{escape(SIGN_OFF).replace(chr(10), "<br>")}</p></div>')


def _link(path: str, token: str) -> str:
    return web.link(f"{path}?token={quote(token)}")


def verify(to: str, name: str, token: str):
    url = _link("/verify/confirm", token)
    lines = [f"Hi {name},", "Confirm your email to finish setting up SlothSpend. The link works for 24 hours.",
             "If you didn't create an account, ignore this email — nothing happens."]
    text = f"{lines[0]}\n\n{lines[1]}\n\n{url}\n\n{lines[2]}\n\n{SIGN_OFF}\n"
    return build(to, "Confirm your email for SlothSpend", text, _html(lines, ("Confirm my email", url)))


def account_exists(to: str, name: str):
    login, forgot = web.link("/login"), web.link("/forgot")
    lines = [f"Hi {name},", "Someone (hopefully you) tried to create a SlothSpend account with this email. "
             "You already have one, so nothing changed.", f"Log in: {login}",
             f"Forgot your password? Choose a new one: {forgot}", "If this wasn't you, you can ignore this email."]
    return build(to, "You already have a SlothSpend account", "\n\n".join(lines) + f"\n\n{SIGN_OFF}\n", _html(lines))


def reset(to: str, name: str, token: str):
    url = _link("/reset", token)
    lines = [f"Hi {name},", "Here's the link to choose a new SlothSpend password. It works for one hour, once.",
             "Saving a new password logs you out on your other devices. If you didn't ask for this, ignore this "
             "email — your password stays the same."]
    text = f"{lines[0]}\n\n{lines[1]}\n\n{url}\n\n{lines[2]}\n\n{SIGN_OFF}\n"
    return build(to, "Choose a new SlothSpend password", text, _html(lines, ("Choose a new password", url)))


def sign_in(to: str, name: str, token: str):
    url = _link("/login/link", token)
    lines = [f"Hi {name},", "Here's your sign-in link for SlothSpend. It works for 15 minutes, once.",
             "If you didn't ask for it, ignore this email — nobody can use it without this inbox."]
    text = f"{lines[0]}\n\n{lines[1]}\n\n{url}\n\n{lines[2]}\n\n{SIGN_OFF}\n"
    return build(to, "Your SlothSpend sign-in link", text, _html(lines, ("Log in to SlothSpend", url)))


def password_changed(to: str, name: str):
    forgot = web.link("/forgot")
    lines = [f"Hi {name},", "Your SlothSpend password was just changed, and your other devices were logged out.",
             f"If this wasn't you, choose a new password now: {forgot}"]
    return build(to, "Your SlothSpend password was changed", "\n\n".join(lines) + f"\n\n{SIGN_OFF}\n", _html(lines))
