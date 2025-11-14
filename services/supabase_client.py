import os
from typing import Any
from supabase import create_client, Client

def get_supabase_client() -> Client:
    supabase_url: str = os.environ.get("SUPABASE_URL")
    supabase_key: str = os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError("Supabase URL and Key must be set in environment variables")
    return create_client(supabase_url, supabase_key)

async def log_call(client_id: str, caller_phone: str, transcript: Any):
    supabase = get_supabase_client()
    data_to_insert = {
        "client_id": client_id,
        "phone": caller_phone,
        "transcript": transcript,
    }
    response = await supabase.table('bookings').insert(data_to_insert).execute()
    return response
