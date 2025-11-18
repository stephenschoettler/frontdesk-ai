<objective>
Modify the appointment booking system to display only the start time of available appointments instead of showing 30-minute time ranges, making the interface cleaner and more user-friendly.
</objective>

<context>
Currently, the AI receptionist reads available time slots as ranges like:
"- 5:00 PM - 5:30 PM"
"- 5:30 PM - 6:00 PM"
"- 6:00 PM - 6:30 PM"

The user wants to simplify this to show only the start times:
"- 5:00 PM"
"- 5:30 PM"
"- 6:00 PM"

This will make the booking process faster and less verbose while still providing clear time options.
</context>

<requirements>
1. **Update System Prompt**: Modify the Calendar Management instructions to explicitly state that only start times should be displayed, not time ranges.

2. **Ensure Clarity**: Make sure the instructions are clear that appointments are still 30-minute slots, but only the start time is shown to the user.

3. **Maintain Functionality**: The booking process should still work exactly the same - the AI just presents cleaner time options.
</requirements>

<implementation>
Update the system prompt in the "Calendar Management" section, specifically the "Check Availability" subsection:

**Current:**
```
- Read available slots clearly (e.g., "I have 10:00 AM, 2:30 PM, and 4:00 PM").
```

**Updated:**
```
- Read available slots clearly, showing only the start time for each 30-minute appointment slot (e.g., "I have 10:00 AM, 2:30 PM, and 4:00 PM available").
- Do NOT show time ranges like "10:00 AM - 10:30 AM" - only show the start time.
```
</implementation>

<output>
Create/modify files with relative paths:
- `./system_prompt.txt` - Update Calendar Management instructions to show only start times
</output>

<verification>
Before declaring complete, verify your work:
1. Run the application and simulate an appointment booking
2. Confirm the AI shows time slots as single start times (e.g., "5:00 PM") instead of ranges (e.g., "5:00 PM - 5:30 PM")
3. Verify the booking process still works correctly when a start time is selected
4. Check that the conversation remains natural and clear

Run: `python main.py` and test the booking flow to confirm cleaner time slot presentation.
</verification>

<success_criteria>
- Time slots are displayed as single start times only (e.g., "5:00 PM, 5:30 PM, 6:00 PM")
- No time ranges are shown (no "5:00 PM - 5:30 PM" format)
- Appointment booking functionality remains unchanged
- User experience is cleaner and less verbose
</success_criteria>