import httpx
from services.supabase_client import get_supabase_client
import logging

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-3-haiku",
    "google/gemini-2.5-flash-lite",
    "x-ai/grok-4-fast",
]


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
        if model["id"] not in SUPPORTED_MODELS:
            continue

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

    # Optional: Delete entries not in SUPPORTED_MODELS to clean up
    # Using neq to 'placeholder' is a common pattern to select all rows for deletion if no where clause is strict
    # However, to be safe and precise, we can delete where id is NOT in our list, if the client supports it easily.
    # For now, per instructions, we stick to the required filtering for upsert.
    # If we wanted to clean up:
    # try:
    #     supabase.table('model_prices').delete().not_.in_('id', SUPPORTED_MODELS).execute()
    # except Exception as e:
    #     logger.warning(f"Could not clean up old models: {e}")

    result = supabase.table("model_prices").upsert(records).execute()
    logger.info(f"Synced {len(records)} model prices")
    return result


async def get_model_price(model_id):
    """
    Retrieves pricing information for a specific model from the database.
    Returns a dict with input, output, per_request, image prices or None if not found.
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Failed to get Supabase client")
        return None

    result = supabase.table("model_prices").select("*").eq("id", model_id).execute()
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
