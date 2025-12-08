import httpx
from services.supabase_client import get_supabase_client
import logging

logger = logging.getLogger(__name__)


async def sync_openrouter_prices():
    """
    Fetches live model pricing from OpenRouter API and syncs to model_prices table.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
        data = response.json()

    models = data.get("data", [])
    records = []
    for model in models:
        pricing = model.get("pricing", {})
        record = {
            "id": model["id"],
            "input_price": pricing.get("prompt", 0),
            "output_price": pricing.get("completion", 0),
            "per_request_price": pricing.get("request", 0),
            "image_price": pricing.get("image", 0),
        }
        records.append(record)

    supabase = get_supabase_client()
    if not supabase:
        logger.error("Failed to get Supabase client")
        return None

    result = supabase.table('model_prices').upsert(records).execute()
    logger.info(f"Synced {len(records)} model prices")
    return result


def get_model_price(model_id):
    """
    Retrieves pricing information for a specific model from the database.
    Returns a dict with input, output, per_request, image prices or None if not found.
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Failed to get Supabase client")
        return None

    result = supabase.table('model_prices').select('*').eq('id', model_id).execute()
    if result.data and len(result.data) > 0:
        row = result.data[0]
        if isinstance(row, dict):
            return {
                "input": row.get("input_price", 0),
                "output": row.get("output_price", 0),
                "per_request": row.get("per_request_price", 0),
                "image": row.get("image_price", 0),
            }
    return None