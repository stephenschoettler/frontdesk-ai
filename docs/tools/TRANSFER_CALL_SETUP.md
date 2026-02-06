# Transfer Call Tool - Setup Guide

## Overview

The `transfer_call` tool allows the AI assistant to transfer live calls to human agents. When the caller requests to speak with a human or encounters an issue the AI cannot handle, the call is seamlessly transferred to a configured phone number.

## How It Works

1. **LLM Decision**: The AI determines a transfer is needed and calls the `transfer_call` tool
2. **Validation**: The tool checks that a transfer number is configured for the client
3. **Signaling**: A transfer request is stored in the global `transfer_requests` dictionary
4. **Stream Closure**: The websocket handler detects the transfer request and closes the audio stream
5. **Call Update**: Twilio's REST API updates the active call with new TwiML containing a `<Dial>` verb
6. **Transfer**: Twilio connects the caller to the transfer number
7. **Callback**: If the transfer fails, the callback endpoint handles the failure gracefully

## Configuration

### 1. Add Transfer Number to Client Config

Each client must have a `transfer_phone_number` field in their Supabase `clients` table:

```sql
-- Add the column if it doesn't exist
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS transfer_phone_number TEXT;

-- Set the transfer number for your client
UPDATE clients
SET transfer_phone_number = '+14155551234'
WHERE id = 'your-client-id';
```

**Format**: Must be in E.164 format (e.g., `+14155551234`)

### 2. Enable the Tool

Add `transfer_call` to the client's `enabled_tools` array:

```sql
UPDATE clients
SET enabled_tools =
  CASE
    WHEN enabled_tools IS NULL THEN '["transfer_call"]'::jsonb
    ELSE enabled_tools || '["transfer_call"]'::jsonb
  END
WHERE id = 'your-client-id';
```

### 3. Update System Prompt (Optional)

You may want to add guidance to your system prompt about when to transfer calls:

```
If the caller requests to speak with a human or if their issue is too complex for you to handle, use the transfer_call tool to connect them with a team member. Always be polite and set expectations before transferring.
```

## Testing

### 1. Test Configuration

```python
# Verify transfer number is set
import asyncio
from services.supabase_client import get_client_config

async def test_transfer_config():
    config = await get_client_config("your-client-id")
    transfer_number = config.get("transfer_phone_number")
    print(f"Transfer Number: {transfer_number}")

    enabled_tools = config.get("enabled_tools", [])
    print(f"Transfer tool enabled: {'transfer_call' in enabled_tools}")

asyncio.run(test_transfer_config())
```

### 2. Test the Transfer Flow

1. Call your Frontdesk number
2. Say "I'd like to speak with a human" or "Can I talk to someone?"
3. The AI should acknowledge and initiate the transfer
4. Your call should be connected to the transfer number
5. Check logs for transfer events

### 3. Check Logs

Look for these log entries:

```
[TRANSFER] Transfer request registered for client_id:+1234567890 -> +14155551234
[TRANSFER] Initiating transfer for client_id:+1234567890 to +14155551234
[TRANSFER] Call CA1234... successfully transferred to +14155551234
```

## Behavior

### When Transfer Succeeds

- Caller hears: "Please hold while I transfer you"
- Call connects to the transfer number
- Transfer number receives the call
- Original AI conversation ends

### When Transfer Fails

The transfer can fail if:
- Transfer number is busy
- Transfer number doesn't answer (after 30 seconds)
- Transfer number is invalid or unreachable

In these cases:
- Caller hears: "I'm sorry, but the transfer could not be completed. Please try calling back later. Goodbye."
- Call ends gracefully
- Event is logged for review

### When Transfer Number Not Configured

- Tool returns error to AI
- AI should say something like: "I apologize, but I'm unable to transfer you at the moment. Can I help you with something else or take a message?"

## LLM Prompt Engineering

The AI will use the transfer tool based on its training and system prompt. You can guide behavior by adding rules like:

```
Transfer Guidelines:
1. Always ask if they'd like to be transferred before using the tool
2. Use transfer_call for: complex complaints, sales inquiries, technical issues
3. Do NOT transfer for: simple questions, scheduling, availability checks
4. Always be warm and reassuring when transferring
```

## Security Considerations

1. **Phone Number Validation**: Transfer numbers should be validated to prevent toll fraud
2. **Rate Limiting**: Consider limiting transfer frequency per caller
3. **Audit Trail**: All transfer attempts are logged with timestamps
4. **Configuration Access**: Only authorized admins should modify transfer numbers

## Troubleshooting

### Transfer Not Working

1. **Check Configuration**:
   ```sql
   SELECT id, transfer_phone_number, enabled_tools
   FROM clients
   WHERE id = 'your-client-id';
   ```

2. **Check Logs**:
   ```bash
   tail -f frontdesk.log | grep TRANSFER
   ```

3. **Verify Phone Format**: Must be E.164 format with country code

4. **Test Twilio Credentials**: Ensure `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are valid

### AI Not Using the Tool

1. Check system prompt includes transfer guidance
2. Verify tool is in `enabled_tools` list
3. Try explicit requests: "Transfer me to a human"
4. Check LLM model has function calling capability

### Transfer Immediately Fails

1. Verify transfer number is correct and reachable
2. Check Twilio account has outbound calling enabled
3. Verify caller ID is set correctly
4. Test the transfer number manually with Twilio console

## Cost Considerations

- Each transfer counts as Twilio voice usage
- Transfer duration is separate from AI conversation duration
- Failed transfers still incur connection fees
- Monitor usage in Twilio console

## Future Enhancements

Potential improvements to consider:

1. **Multiple Transfer Targets**: Support for departments (sales, support, etc.)
2. **Voicemail Fallback**: Leave voicemail if transfer fails
3. **Queue Support**: Transfer to Twilio queue for agent pickup
4. **Context Sharing**: SMS or whisper message to agent with conversation summary
5. **Return to AI**: Allow caller to return to AI if transfer fails
6. **Transfer Analytics**: Track transfer rates, success rates, and reasons

## Related Files

- **Tool Handler**: `services/llm_tools.py` - `handle_transfer_call()`
- **Main App**: `main.py` - Websocket handler and transfer callback
- **Tool Schema**: `docs/tools/transfer_call_schema.json`
