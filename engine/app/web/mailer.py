"""Outgoing email (WEB-IMPL W2): SMTP in production, a local outbox in development and tests.

SLOTH_SMTP_URL set: `smtp://user:pass@host:587` uses STARTTLS (required unless the host is local), `smtps://…:465`
uses TLS from the first byte. Unset: every message is written to <SLOTH_DATA_DIR>/outbox/ as an .eml file and its
links are logged, so local sign-up works with no mail server. Delivery runs in the background: a request answers
in the same time whether or not an email went out (no account probing by timing).
"""

import asyncio
import logging
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import make_msgid
from urllib.parse import unquote, urlparse

from ..config import settings
from .config import web

log = logging.getLogger(__name__)

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SENT: list[EmailMessage] = []  # outbox mode only: the latest messages, newest last (tests read it)
_tasks: set[asyncio.Task] = set()


def build(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = web.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="slothspend")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _smtp(msg: EmailMessage) -> None:
    url = urlparse(web.smtp_url)
    host = url.hostname or "localhost"
    user, password = unquote(url.username or ""), unquote(url.password or "")
    context = ssl.create_default_context()
    if url.scheme == "smtps":
        with smtplib.SMTP_SSL(host, url.port or 465, timeout=15, context=context) as client:
            if user:
                client.login(user, password)
            client.send_message(msg)
        return
    with smtplib.SMTP(host, url.port or 587, timeout=15) as client:
        client.ehlo()
        if client.has_extn("starttls"):
            client.starttls(context=context)
            client.ehlo()
        elif host not in LOCAL_HOSTS:
            raise RuntimeError(f"{host} does not offer STARTTLS; refusing to send credentials in clear text")
        if user:
            client.login(user, password)
        client.send_message(msg)


def _outbox(msg: EmailMessage) -> None:
    folder = settings.data_dir / "outbox"
    folder.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", str(msg["Subject"]).lower()).strip("-")[:40]
    (folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 10**6:06d}-{slug}.eml").write_bytes(msg.as_bytes())
    SENT.append(msg)
    del SENT[:-50]
    links = re.findall(r"https?://\S+", msg.get_body(("plain",)).get_content())
    log.warning("outbox: email to %s — %s%s", msg["To"], msg["Subject"], "".join(f"\n    {u}" for u in links))


def send_now(msg: EmailMessage) -> None:
    try:
        (_smtp if web.smtp_url else _outbox)(msg)
    except Exception:  # noqa: BLE001 — a mail outage must never break sign-in screens
        log.exception("email to %s failed", msg["To"])


def send_later(msg: EmailMessage) -> None:
    task = asyncio.get_running_loop().create_task(asyncio.to_thread(send_now, msg))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
