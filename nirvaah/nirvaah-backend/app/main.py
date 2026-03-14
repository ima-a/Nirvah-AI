from fastapi import FastAPI
from app.webhook import router as webhook_router
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title='Nirvaah AI Backend')
app.include_router(webhook_router)

@app.get('/health')
async def health_check():
    return {'status': 'ok', 'service': 'nirvaah-ai'}
