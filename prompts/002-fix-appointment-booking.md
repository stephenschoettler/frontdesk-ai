<objective>
Fix two critical issues in the appointment booking system: the booking function parameter mismatch and the long time slot reading problem that overwhelms callers with too many options.
</objective>

<context>
From the frontdesk.log analysis, two issues are evident:

1. **Booking Function Error**: The `handle_book_appointment` function expects parameters named "start" and "end", but the LLM is providing "start_time" and "end_time", causing a KeyError.

2. **Long Time Slot Lists**: The AI reads out all 16 available 30-minute slots (9 AM - 5 PM), which takes too long and overwhelms callers. The system should ask for morning/afternoon preference first to reduce slots to 4-8 options.

The current flow shows the AI successfully saves the contact name, gets available slots, reads all 16 slots aloud, but then fails when trying to book the selected appointment.
</context>

<requirements>
1. **Fix Parameter Mismatch in Booking Function**:
   - Update `handle_book_appointment` in `services/llm_tools.py` to correctly access "start_time" and "end_time" instead of "start" and "end"
   - Ensure the function documentation matches the actual parameter names

2. **Implement Morning/Afternoon Filtering**:
   - Modify the appointment booking flow to ask for time preference (morning/afternoon) before showing available slots
   - Update the system prompt to include instructions for time preference filtering
   - Modify `get_available_slots` to accept an optional time range filter (morning: 9-12, afternoon: 12-5)
   - Reduce slot reading from 16 options to 4-8 options maximum

3. **Update System Prompt**:
   - Add instructions for asking morning/afternoon preference before showing slots
   - Ensure the flow remains conversational and efficient
</requirements>

<implementation>
**Fix 1: Parameter Names**
Change lines 76-77 in `services/llm_tools.py`:
```python
# Current (broken):
start_time = args["start"]
end_time = args["end"]

# Fixed:
start_time = args["start_time"]
end_time = args["end_time"]
```

**Fix 2: Time Filtering**
- Add time_range parameter to `get_available_slots` function
- Filter slots based on morning (9 AM - 12 PM) or afternoon (12 PM - 5 PM)
- Update system prompt to ask for time preference first

**Fix 3: System Prompt Updates**
Add to the Calendar Management section:
```
2. **Check Availability:**
   - Once you have a specific date, ask if they prefer morning or afternoon slots
   - Use `get_available_slots` with time_range filter ("morning" or "afternoon")
   - Only read 4-8 slots maximum instead of all 16
```
</implementation>

<output>
Create/modify files with relative paths:
- `./services/llm_tools.py` - Fix parameter access in handle_book_appointment and add time filtering to get_available_slots
- `./system_prompt.txt` - Add morning/afternoon preference instructions
</output>

<verification>
Before declaring complete, verify your work:
1. Run the application and simulate booking an appointment
2. Confirm the AI asks for morning/afternoon preference before showing slots
3. Verify booking completes successfully without KeyError
4. Check that only 4-8 slots are read aloud instead of 16
5. Confirm the appointment appears in Google Calendar

Run: `python main.py` and test the complete booking flow.
</verification>

<success_criteria>
- Appointment booking completes without parameter errors
- AI asks for morning/afternoon preference before showing time slots
- Maximum 8 time slots are read aloud per request
- Appointments are successfully created in Google Calendar
- Conversation flow remains natural and efficient
</success_criteria>