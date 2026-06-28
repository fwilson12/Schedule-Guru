from datetime import datetime


# current init system prompt 
system_prompt = """
You are a Google Calendar automation assistant. Your job is to interpret the user's intent
and call the correct tool ONLY when needed. You must be concise, professional, and accurate.

---GENERAL RULES---
- Use line breaks in your response when concluding a point/message to enhance readability.
- NEVER call a tool if you have the information you need in the chat history to answer the user's question. Always check the chat history before calling a tool.
- If the user asks to make an event around their schedule, and you have their schedule 
- You may either return TEXT or a TOOL CALL. Never both.
- Only call a tool if required to fulfill the user's request.
- Before calling a tool, confirm you have all required fields.
- If scheduling an event, ALWAYS confirm the user-specified time does not conflict with existing events in their calendar.
- If there is a conflict, or if the time is unspecified, suggest alternative time(s) based on their existing events.
- If a user asks a question that can be answered using information already in the chat history,
  answer directly without calling any tool.
- Always use America/Chicago timezone for events unless told otherwise.
- Use ISO 8601 datetime format for any tool call:
  '2025-05-24T09:00:00-05:00'

---RECURRING EVENTS---
Use create_recurring() ONLY when the user explicitly asks for repeated events:
Examples: "every Monday", "first Tuesday each month", "MWF", "repeat until June".
If recurrence details are insufficient, ask follow-up questions. Conform to standard RRULE conventions
i.e. A valid RRULE string would look like this: RRULE:FREQ=WEEKLY;BYDAY=TU,TH;UNTIL=20260509T045959Z

---DELETION---
Use:
- delete_event() for one-time events
- delete_recurring() ONLY when the user clearly indicates a repeating series

---PATCHING EXISTING EVENTS---
- Use patch_event() to change event time, location, recurrence, etc.
- NEVER just change the description of an event like (event is updated). Always directly update the fields requested.
- patch_body must be constructed dynamically with json event resource values from the user request.
- Map user intents to the correct Google Calendar fields within patch_body:
    - Change start time -> {"start": {"dateTime": "..."}}
    - Change end time -> {"end": {"dateTime": "..."}}
    - Change title -> {"summary": "..."}
    - Change location -> {"location": "..."}
    - Change recurrence -> {"recurrence": ["RRULE:..."]}
- Use modify_series=True to update the entire series of a recurring event.
- Always include patch_body, never leave empty.
- The starttime and endtime fields in patch_event() define the search window
  for events to patch, not the new event times themselves.

---READING EVENTS---
Use readEvents() when the user:
- Wants their upcoming events
- Wants free time
- Wants availability analysis
- Wants events in a specific week/month/day range
If a time window is specified, set num_events = 999.

---SUMMARIZATION AFTER TOOL OUTPUT---
Your follow-up message after a tool result should:
- Summarize ONLY the most recent tool's result
- Never reveal parameters or internal logic
- Present date-times in conversational English
- Include weekday once for the first date mentioned

---STYLE---
Be brief. Be practical. Do not over-explain.
"""

# prompt for summarizing tool results
summary_prompt = """
You are generating a natural-language summary of the recent tool call(s) only, or making a follow up tool call if demmed necessary.
You have the ability to call as many tools as needed, evaluate recent messages/tool calls to make your decision.

IF YOU DEEM ANOTHER TOOL CALL IS NECESSARY:
i.e., the user requested to make/delete/update an event and you had to check their schedule first:
Call the appropriate tool now that you have their events. OR if the user requested for multiple events to be created/deleted/patched etc..

OTHERWISE:
Your job:
- Interpret ONLY the tool output text.
- Turn it into a short, clear message for the user.
- Never repeat parameters.
- Never rewrite the tool call.
- Convert ISO datetimes into conversational English (e.g., May 24th, 2025 at 9:00 AM).
- Include weekday names.
- For lists of events, format them cleanly and concisely.
- If there was an error, explain what went wrong and how to fix it.

Keep it short and professional.
"""

# tells the agent the current date and time, plus weekday for extra reference
now = datetime.now().isoformat()
weekday = datetime.now().strftime("%A")

# updated after every user message, assistant chat response/tool summary, tool call, and system error message
msg_history = [
    {
        "role": "system",
        "content": f"The current date and time is {weekday}, {now}"
    },
    {
        "role": "system",
        "content": system_prompt
    }
]

# function specifications for tools the agent has access to
function_spec = [
    {
        "name": "create",
        "description": "Create a one-time Google Calendar event.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "location": {"type": "string"},
                "description": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "timezone": {"type": "string"},
            },
            "required": ["summary", "description", "start", "end", "timezone"],
        },
    },

    {
        "name": "create_recurring",
        "description": "Create a recurring Google Calendar event (RRULE-based).",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "location": {"type": "string"},
                "description": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "timezone": {"type": "string"},
                "frequency": {"type": "string"},
                "interval": {"type": "integer", "default": 1},
                "weekdays": {"type": "array", "items": {"type": "string"}},
                "monthday": {"type": "integer"},
                "nth_weekday": {
                    "type": "object",
                    "properties": {
                        "weekday": {"type": "string"},
                        "nth": {"type": "integer"}
                    }
                },
                "until": {"type": "string", "description": "YYYYMMDDT000000Z"},
                "count": {"type": "integer"},
                "exception_dates": {"type": "array", "items": {"type": "string"}}
            },
            "required": [
                "summary", "description", "start",
                "end", "timezone", "frequency"
            ]
        }
    },

    {
        "name": "readEvents",
        "description": "Fetch events in a given window or the next N events.",
        "parameters": {
            "type": "object",
            "properties": {
                "num_events": {"type": "integer"},
                "starttime": {"type": "string"},
                "endtime": {"type": "string"}
            },
            "required": ["num_events", "starttime", "endtime"]
        }
    },

    {
        "name": "delete_event",
        "description": "Delete a single event that matches the title inside the given time window.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "starttime": {"type": "string", "description": "Start time of the time window to search for the event to delete."},
                "endtime": {"type": "string", "description": "End time of the time window to search for the event to delete."}
            }
        }
    },

    {
        "name": "delete_recurring",
        "description": "Delete a recurring event series that matches the given title.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "starttime": {"type": "string", "description": "Start time of the time window to search for the recurring event series to delete."},
                "endtime": {"type": "string", "description": "End time of the time window to search for the recurring event series to delete."}
            }
        }
    },

    {
        "name": "patch_event",
        "description": """Patch an existing event or event series with updated fields. patch_body must contain the fields the user wants to update
                          in json format with their new values e.g. 'end': '2025...'""",
        "parameters": {
            "type": "object",
            "properties": {
               "title": {"type": "string"},
               "starttime": {"type": "string", "description": "Start time of the time window to search for events to patch."},
               "endtime": {"type": "string", "description": "End time of the time window to search for events to pach."},
               "patch_body": {
                    "type": "object",
                    "properties": {
                      "summary": {"type": "string"},
                      "location": {"type": "string"},
                      "description": {"type": "string"},
                      "start": {"type": "object"},  # {"dateTime": "..."}
                      "end": {"type": "object"},    # {"dateTime": "..."}
                      "recurrence": {"type": "array", "items": {"type": "string"},"description": "Contains RRULE string of updated recurrence rules."}
                    },
                    "description": "Fields to be updated at the user's request.",
                  },
                "modify_series": {
                    "type": "boolean",
                    "description": "true = modify entire series, false = modify only this instance"
               }
            },
            "required": ["title", "starttime", "endtime", "modify_series"]
        }
    }
]

# tools list for openai client argument
TOOLS = [{"type": "function", "function": spec} for spec in function_spec]