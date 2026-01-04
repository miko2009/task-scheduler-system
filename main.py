import uvicorn
from fastapi import FastAPI
from app.api import auth, task
from app.core.config import settings

app = FastAPI(title="Task Scheduler API", version="1.0")

# 注册路由
app.include_router(auth.router, prefix="/auth", tags=["认证"])
app.include_router(task.router, prefix="/api/task", tags=["任务管理"])

@app.get("/")
async def root():
    return {"msg": "Task Scheduler API is running"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )