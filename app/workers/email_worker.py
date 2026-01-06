import asyncio
from typing import Any, Dict, List, Optional
import os
import sys
import json
from app.core.emailer import Emailer
from app.models.user import get_user
from app.core.config import Settings
from app.models.task import update_task_email_status

async def email_worker(task_data) -> bool:

    user_id = task_data.get("user_id")
    user = get_user(user_id)
    if not user or not user.email:
        return True
    frontend = Settings.FRONTEND_URL.rstrip("/")
    email = user.email
    subject, text_body, html_body = Emailer().format_wrapped_email(user_id, frontend)
    Emailer().send_email(email, subject, text_body, html_body)
    update_task_email_status(
        task_data.get("task_id"),
        "completed",
        email_status="sent"
    )
    return True
if __name__ == "__main__":
      asyncio.run(email_worker())