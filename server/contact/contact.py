#!/usr/bin/env python3
"""Small, loopback-only MBBB contact endpoint; run behind Caddy."""
import json
import logging
import os
import smtplib
import ssl
import threading
import time
from collections import OrderedDict
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re

LOG = logging.getLogger("mbbb-contact")
MAX_BODY = 24000
LIMITS = {"first-name": 100, "last-name": 100, "email": 254,
          "event-date": 10, "event-type": 100, "message": 8000, "website": 200}
REQUIRED = ("first-name", "last-name", "email", "message")
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}$")


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Please check your form details.")
    clean = {}
    for field, limit in LIMITS.items():
        value = data.get(field, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("A field is too long or contains invalid data.")
        clean[field] = value.strip()
    if any(not clean[key] for key in REQUIRED):
        raise ValueError("Please complete your name, email address and message.")
    if not EMAIL.fullmatch(clean["email"]):
        raise ValueError("Please enter a valid email address.")
    if clean["event-date"]:
        from datetime import date
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", clean["event-date"]):
                raise ValueError
            date.fromisoformat(clean["event-date"])
        except ValueError:
            raise ValueError("Please enter a valid event date.") from None
    return clean


class RateLimiter:
    """At most 5 attempts per IP per 15 minutes; bounded in-memory storage."""
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self.lock:
            hits = [t for t in self.entries.pop(key, []) if now - t < 900]
            allowed = len(hits) < 5
            if allowed:
                hits.append(now)
            self.entries[key] = hits
            while len(self.entries) > 10000:
                self.entries.popitem(last=False)
            return allowed


def send_email(data, config):
    message = EmailMessage()
    message["From"] = config["MAIL_FROM"]
    message["To"] = config["MAIL_TO"]
    message["Reply-To"] = data["email"]
    name = " ".join(
        f"{data['first-name']} {data['last-name']}".split()
    )
    message["Subject"] = f"{config['MAIL_SUBJECT_PREFIX']} {name}"
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()
    message.set_content("\n".join([
        "New website enquiry", "",
        f"Name: {data['first-name']} {data['last-name']}",
        f"Email: {data['email']}",
        f"Event date: {data['event-date'] or 'Not supplied'}",
        f"Event type: {data['event-type'] or 'Not supplied'}",
        "", "Message:", data["message"],
    ]))
    with smtplib.SMTP(config["SMTP_HOST"], int(config["SMTP_PORT"]), timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPException("Recipient refused")


class Handler(BaseHTTPRequestHandler):
    server_version = "Contact"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        # Do not log visitor details or request bodies.
        pass

    def reply(self, status, message):
        payload = json.dumps({"ok": status == 200, "message": message}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        if status == 429:
            self.send_header("Retry-After", "900")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.reply(405 if self.path == "/api/contact" else 404, "Not available.")

    def do_POST(self):
        if self.path != "/api/contact":
            return self.reply(404, "Not found.")
        if self.headers.get("Origin") != self.server.config["PUBLIC_ORIGIN"]:
            return self.reply(403, "Please submit the form from our website.")
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, "Unsupported submission format.")
        # Caddy overwrites this header; never expose this service publicly.
        client = self.headers.get("X-Contact-IP", self.client_address[0])
        if not self.server.limiter.allow(client):
            return self.reply(429, "Too many attempts. Please wait 15 minutes or email us directly.")
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.reply(413, "The message is too large or empty.")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError
            data = validate(json.loads(raw))
        except (ValueError, UnicodeError):
            return self.reply(400, "Please check the required fields, email address, date and message length.")
        except (TimeoutError, OSError):
            return self.reply(408, "The request timed out. Please try again.")
        if data["website"]:
            return self.reply(200, "Thank you. Your enquiry has been sent.")
        if not self.server.mail_slots.acquire(blocking=False):
            return self.reply(503, "We are busy at the moment. Please try again shortly.")
        try:
            send_email(data, self.server.config)
        except Exception as error:
            LOG.error("Email submission failed (%s)", type(error).__name__)
            return self.reply(502, "Your enquiry could not be confirmed as sent. Please try again or email us directly.")
        finally:
            self.server.mail_slots.release()
        LOG.info("SMTP accepted an enquiry")
        self.reply(200, "Thank you. Your enquiry has been sent.")


def create_server(config, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.config = config
    server.limiter = RateLimiter()
    server.mail_slots = threading.BoundedSemaphore(3)
    return server


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    keys = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
            "MAIL_FROM", "MAIL_TO", "MAIL_SUBJECT_PREFIX", "PUBLIC_ORIGIN")
    config = {key: os.environ.get(key, "") for key in keys}
    if not all(config.values()):
        raise SystemExit("Missing required contact configuration.")
    if not all(EMAIL.fullmatch(config[key]) for key in ("MAIL_FROM", "MAIL_TO")):
        raise SystemExit("MAIL_FROM and MAIL_TO must each be one email address.")
    server = create_server(config, int(os.environ.get("CONTACT_PORT", "8011")))
    LOG.info("Contact handler started on loopback")
    server.serve_forever()


if __name__ == "__main__":
    main()
