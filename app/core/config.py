import os
from dotenv import load_dotenv

# load .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=dotenv_path)


class Settings():
    # MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER: str = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD")
    MYSQL_DB: str = os.getenv("MYSQL_DB")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_LOCK_EXPIRE: int = int(os.getenv("REDIS_LOCK_EXPIRE", 60))

    # queue and task keys
    TASK_QUEUE_VERIFY: str = os.getenv("TASK_QUEUE_VERIFY")
    TASK_QUEUE_COLLECT: str = os.getenv("TASK_QUEUE_COLLECT")
    TASK_QUEUE_ANALYZE: str = os.getenv("TASK_QUEUE_ANALYZE")
    TASK_QUEUE_RETRY: str = os.getenv("TASK_QUEUE_RETRY")
    TASK_STATUS_KEY: str = os.getenv("TASK_STATUS_KEY")
    TASK_LOCK_KEY: str = os.getenv("TASK_LOCK_KEY")
    TASK_QUEUE_EMAIL_SEND: str = os.getenv("TASK_QUEUE_EMAIL_SEND")

    # Worker settings
    WORKER_VERIFY_NUM: int = int(os.getenv("WORKER_VERIFY_NUM", 4))
    WORKER_ANALYZE_NUM: int = int(os.getenv("WORKER_ANALYZE_NUM", 4))
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", 10))
    REGION_WHITELIST: list = eval(os.getenv("REGION_WHITELIST", '["CN"]'))
    COLLECT_PAGE_SIZE: int = int(os.getenv("COLLECT_PAGE_SIZE", 20))

    # API settings
    REGION_VERIFY_API_URL: str = os.getenv("REGION_VERIFY_API_URL")
    BROWSE_COLLECT_API_URL: str = os.getenv("BROWSE_COLLECT_API_URL")
    BROWSE_ANALYSIS_API_URL: str = os.getenv("BROWSE_ANALYSIS_API_URL")
    FINALIZE_WATCH_HISTORY_API_URL: str = os.getenv("FINALIZE_WATCH_HISTORY_API_URL")
    ARCHIVE_BASE_URL: str = os.getenv("ARCHIVE_BASE_URL", "")
    API_TOKEN: str = os.getenv("API_TOKEN")
    ARCHIVE_API_KEY: str = os.getenv("ARCHIVE_API_KEY") 
    ARCHIVE_AUTH_START_PATH: str = os.getenv("ARCHIVE_AUTH_START_PATH", "/archive/xordi/start-auth")
    ARCHIVE_AUTHENTICATE_PATH: str = os.getenv("ARCHIVE_AUTHENTICATE_PATH", "/archive/xordi/get-authorization-code")
    ARCHIVE_FINALIZE_PATH: str = os.getenv("ARCHIVE_FINALIZE_PATH", "/archive/xordi/finalize-auth")
    ARCHIVE_REDIRECT_PATH: str = os.getenv("ARCHIVE_REDIRECT_PATH", "/archive/xordi/get-redirect")
    ARCHIVE_WATCH_HISTORY_PATH: str = os.getenv("ARCHIVE_WATCH_HISTORY_PATH", "/archive/watch-history/get")
    ARCHIVE_WATCH_HISTORY_START_PATH: str = os.getenv("ARCHIVE_WATCH_HISTORY_START_PATH", "/archive/watch-history/start")
    ARCHIVE_WATCH_HISTORY_FINALIZE_PATH: str = os.getenv("ARCHIVE_WATCH_HISTORY_FINALIZE_PATH", "/archive/xordi/watch-history/finalize")

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    SESSION_TTL_DAYS: int = int(os.getenv("SESSION_TTL_DAYS", 30))
    SESSION_TTL_KEY: str = os.getenv("SESSION_TTL_KEYS", "abcdefghijklmnopqrstuvwxyz")

    # OpenRouter
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL")
    OPENROUTER_URL: str = os.getenv("OPENROUTER_URL")


    #email settings
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_ACCESS_KEY_SECRET: str = os.getenv("AWS_ACCESS_KEY_SECRET")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_EMAIL: str = os.getenv("AWS_EMAIL", "admin")

settings = Settings()