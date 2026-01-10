import asyncio
from typing import Any, Dict, List, Optional
import os
import sys
import json
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
from app.core.emailer import Emailer
from app.models.user import get_user
from app.core.config import Settings
from app.models.task import update_task_email_status
from app.core.database import redis_client

async def email_worker() -> bool:
    email_send_queue = Settings.TASK_QUEUE_EMAIL_SEND

    while True:
        queue_data = redis_client.brpop([email_send_queue], timeout=5)
        if not queue_data:
             continue
        queue_name, task_data_str = queue_data
        print(task_data_str)
        task_data = json.loads(task_data_str)
        user_id = task_data.get("user_id")
        user = get_user(user_id)
        if not user or not user.get('email'):
            return True
        frontend = Settings.FRONTEND_URL.rstrip("/")
        email = user.get('email')
        subject, text_body, html_body = Emailer().format_wrapped_email(user_id, frontend)

        print('subject', subject)
        print('text_body', text_body)
        print('email', email)
        print('html_body', html_body)
        Emailer().send_email(email, subject, text_body, html_body)
        update_task_email_status(
            task_data.get("task_id"),
            "sent"
        )
if __name__ == "__main__":
      asyncio.run(email_worker())