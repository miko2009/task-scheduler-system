import pymysql
import redis
import os
import sys
from app.core.config import settings
from redis.lock import Lock
from dbutils.pooled_db import PooledDB 
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


POOL_CONFIG = {
    "host": settings.MYSQL_HOST,
    "port": settings.MYSQL_PORT,
    "user": settings.MYSQL_USER,
    "password": settings.MYSQL_PASSWORD,
    "database": settings.MYSQL_DB,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "maxconnections": 20,  # pool max connections
    "mincached": 5,        # initial pool connections
    "maxcached": 10,       # max cached connections
    "maxshared": 5,        # max shared connections
    "blocking": True,      # block if no connection available
    "setsession": [],     # session commands
}
# create MySQL connection pool
mysql_pool = PooledDB(
    creator=pymysql,
    **POOL_CONFIG
)
# get MySQL connection from pool
def get_mysql_conn():
    conn = mysql_pool.connection()
    return conn

# create Redis client
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True
)

# get distributed lock for a task
def get_task_lock(task_id):
    lock_key = settings.TASK_LOCK_KEY.format(task_id=task_id)
    return Lock(redis_client, lock_key, timeout=settings.REDIS_LOCK_EXPIRE)