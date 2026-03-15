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


@app.get('/audit/verify')
async def audit_verify():
    """
    Verifies the full SHA-256 audit chain integrity.
    Called by the supervisor dashboard's AuditChain component.
    Returns {valid: true} or a list of tamper alerts.
    """
    from app.verify_integrity import verify_full_chain
    from app.database import supabase, log_access
    log_access('supervisor', 'SUPERVISOR', 'READ', 'audit_log')
    try:
        entries = supabase.table('audit_log') \
            .select('*') \
            .order('id') \
            .execute().data
        result = verify_full_chain(entries)
        return {'valid': result, 'total_entries': len(entries)}
    except Exception as e:
        return {'valid': False, 'error': str(e)}

