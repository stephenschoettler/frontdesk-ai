<objective>
Analyze the frontdesk.log file to identify and fix a critical bug in the save_contact_name function that's causing a KeyError during phone call processing.
</objective>

<context>
This is a voice AI receptionist system built with Pipecat. The log shows a complete call flow where the AI asks for the caller's name, receives "Steven" as input, but fails when trying to save the contact name due to a parameter parsing error.

The system uses:
- Twilio for telephony
- Deepgram for speech-to-text
- OpenRouter/OpenAI for LLM processing
- ElevenLabs for text-to-speech
- Supabase for data storage
- Google Calendar for appointment booking

@frontdesk.log contains the complete error trace and call flow.
</context>

<requirements>
1. **Analyze the log file** to understand the call flow and identify where the error occurs
2. **Identify the root cause** of the KeyError: 'phone_number' in handle_save_contact_name function
3. **Examine the function call arguments** - note how parameters are structured (nested under 'kwargs')
4. **Review the relevant code** in services/llm_tools.py to understand the current implementation
5. **Propose a fix** to correctly extract phone_number and name from the function arguments
6. **Test the fix** by running the application and verifying the contact saving works
</requirements>

<implementation>
The bug appears to be in how function call arguments are parsed. The LLM is passing arguments in this structure:
```
{'kwargs': {'phone_number': '+15594743709', 'name': 'Steven'}}
```

But the code is trying to access them directly as:
```
params.arguments["phone_number"]
```

Instead, it should access them as:
```
params.arguments["kwargs"]["phone_number"]
```

Update the handle_save_contact_name function in services/llm_tools.py to correctly unpack the nested arguments.
</implementation>

<output>
Create/modify files with relative paths:
- `./services/llm_tools.py` - Fix the parameter extraction in handle_save_contact_name function
</output>

<verification>
Before declaring complete, verify your work:
1. Run the application in test mode and simulate a call where a name is provided
2. Check that the contact is successfully saved to Supabase without KeyError
3. Verify the conversation continues normally after name saving
4. Confirm no errors appear in the logs during the save_contact_name operation

Run: `python main.py` and monitor the logs for successful contact saving.
</verification>

<success_criteria>
- The KeyError: 'phone_number' no longer occurs when saving contact names
- Contact information is successfully stored in Supabase database
- The conversation flow continues normally after name collection
- No function call errors appear in the logs
</success_criteria>