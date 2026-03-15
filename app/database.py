import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def log_access(user_id: str, role: str, action: str, resource_id: str):
    """Writes a LOG-05 access event to the Supabase access_log table."""
    from app.middleware import create_access_log
    entry = create_access_log(user_id, role, action, resource_id)
    try:
        supabase.table('access_log').insert({
            'user_id_hash':  entry['user_id_hash'],
            'user_role':     entry['user_role'],
            'action':        entry['action'],
            'resource_id':   entry['resource_id'],
            'timestamp':     entry['timestamp'],
        }).execute()
    except Exception as e:
        print(f"[ACCESS_LOG] Write failed: {e}")

