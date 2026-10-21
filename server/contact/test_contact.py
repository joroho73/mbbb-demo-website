import http.client
import json
import threading
import unittest
from unittest.mock import patch
import contact

CONFIG = dict(SMTP_HOST="example.invalid", SMTP_PORT="587", SMTP_USERNAME="demo",
              SMTP_PASSWORD="test-only", MAIL_FROM="mbbb@dcsmail.uk",
              MAIL_TO="mbbb@dcsmail.uk", MAIL_SUBJECT_PREFIX="MBBB Demo Enquiry",
              PUBLIC_ORIGIN="https://mbbb.dcsmail.uk")
DATA = {"first-name": "Test", "last-name": "Visitor", "email": "visitor@example.com",
        "message": "A test enquiry", "event-date": "2027-02-28"}


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.server = contact.create_server(CONFIG, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, data=None, origin=CONFIG["PUBLIC_ORIGIN"], body=None):
        client = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        client.request("POST", "/api/contact", body=body if body is not None else json.dumps(DATA if data is None else data),
                       headers={"Origin": origin, "Content-Type": "application/json"})
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    @patch("contact.smtplib.SMTP")
    def test_delivery_and_headers(self, smtp):
        smtp.return_value.__enter__.return_value.send_message.return_value = {}
        status, result = self.request()
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        connection = smtp.return_value.__enter__.return_value
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with("demo", "test-only")
        message = connection.send_message.call_args.args[0]
        self.assertEqual(message["To"], CONFIG["MAIL_TO"])
        self.assertEqual(message["From"], CONFIG["MAIL_FROM"])
        self.assertEqual(message["Reply-To"], DATA["email"])

    @patch("contact.send_email")
    def test_honeypot_does_not_send(self, send):
        self.assertEqual(self.request({**DATA, "website": "spam"})[0], 200)
        send.assert_not_called()

    @patch("contact.send_email")
    def test_invalid_data_and_origin(self, send):
        for change in ({"email": "visitor@example.com\r\nBcc: bad@example.com"},
                       {"event-date": "2027-02-30"}, {"message": ""}, {"message": "x" * 8001}):
            self.assertEqual(self.request({**DATA, **change})[0], 400)
        self.assertEqual(self.request(origin="https://other.example")[0], 403)
        send.assert_not_called()

    @patch("contact.send_email", side_effect=RuntimeError("secret value"))
    def test_smtp_failure_is_not_success(self, send):
        status, result = self.request()
        self.assertEqual(status, 502)
        self.assertFalse(result["ok"])
        self.assertNotIn("secret value", str(result))

    @patch("contact.send_email")
    def test_rate_limit(self, send):
        for _ in range(5):
            self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request()[0], 429)
        self.assertEqual(send.call_count, 5)

    def test_oversized_body(self):
        self.assertEqual(self.request(body="x" * 24001)[0], 413)


if __name__ == "__main__":
    unittest.main()
