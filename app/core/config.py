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
    API_TOKEN: str = os.getenv("API_TOKEN")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

settings = Settings()