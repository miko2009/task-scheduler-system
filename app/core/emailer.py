import os
import time
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.core.config import Settings

class Emailer:
    def __init__(self) -> None:
        self.sender = Settings.AWS_EMAIL
        region = Settings.AWS_REGION
        if not self.sender or not region:
            raise RuntimeError("AWS_EMAIL and AWS_REGION are required for email sending")
        self.client = boto3.client(
            "ses",
            region_name=region,
            aws_access_key_id=Settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Settings.AWS_ACCESS_KEY_SECRET,
        )

    def format_wrapped_email(self, app_user_id: str, frontend_url: Optional[str]) -> tuple[str, str, str]:
        link = f"{frontend_url.rstrip('/')}/wrapped/{app_user_id}" if frontend_url else f"/wrapped/{app_user_id}"
        subject = "Your 2025 TikTok Wrapped is ready"
        text_body = f"Your wrapped is ready.\n\nView it here: {link}\n\nThanks for trying TikTok Wrapped!"
        html_body = f"""
        <html>
        <body>
            <p>Your wrapped is ready.</p>
            <p><a href="{link}">View it here</a></p>
            <p>Thanks for trying TikTok Wrapped!</p>
        </body>
        </html>
        """
        return subject, text_body.strip(), html_body.strip()

    def send_email(self, to_address: str, subject: str, text_body: str, html_body: str) -> Optional[dict]:
        if not to_address:
            return None
        attempts = 0
        backoff = 1.0
        while attempts < 3:
            attempts += 1
            try:
                resp = self.client.send_email(
                    Source=self.sender,
                    Destination={"ToAddresses": [to_address]},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {
                            "Text": {"Data": text_body},
                            "Html": {"Data": html_body},
                        },
                    },
                )
                return resp
            except (BotoCoreError, ClientError):
                print(ClientError)
                print(BotoCoreError)
                if attempts >= 3:
                    return None
                time.sleep(backoff)
                backoff = min(backoff * 2, 4.0)
