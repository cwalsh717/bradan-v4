from fastapi import FastAPI

from app.routers import utility

app = FastAPI(title="Bradán v4", version="0.1.0")

app.include_router(utility.router)
