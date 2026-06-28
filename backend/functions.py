from openai import OpenAI

import os.path
from dateutil import parser

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


from dotenv import load_dotenv
from pathlib import Path
import os

from vars import msg_history

# for requests
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# for openai api key
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(env_path)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key= OPENAI_API_KEY)


def get_service():
  creds = None
 

  # The file token.json stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time
  if os.path.exists("../token.json"):
    creds = Credentials.from_authorized_user_file("../token.json", SCOPES)
  
  # If there are no (valid) credentials available, make the user log in
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    
    else:
      flow = InstalledAppFlow.from_client_secrets_file("../credentials.json", SCOPES)
      creds = flow.run_local_server(port=0)
    
    with open("../token.json", "w") as token:
      token.write(creds.to_json())
  
  return build("calendar", "v3", credentials=creds)

def create(summary, location, description, start, end, timezone):
  print("---TOOL CALL: CREATE EVENT---")
  service = get_service()
  
  # Event body 
  event = {
        'summary': summary, # title of event
        'location': location,
        'description': description,
        'start': {
            'dateTime': start,
            'timeZone': timezone,
            },
        'end': {
            'dateTime': end,
            'timeZone': timezone,
        }       
        }
  
  # Put request
  try:
    event = service.events().insert(calendarId='primary', body=event).execute()
    return f"Event created: {event.get('htmlLink')}"

  except HttpError as error:
    msg_history.append({"role": "system", "content": f"An error occurred: {error}"})
    print(f"An error occurred: {error}")

def create_recurring(
    summary,
    location,
    description,
    start,
    end,
    timezone,
    frequency,                 # DAILY, WEEKLY, MONTHLY, YEARLY
    interval=1,                # every N units
    weekdays=None,             # ["MO","WE","FR"]
    monthday=None,             # e.g. 15 for 15th of each month
    nth_weekday=None,          # {"weekday": "TU", "nth": 1}
    until=None,                # "YYYYMMDDT000000Z"
    count=None,                # integer
    exception_dates=None       # ["20250110T090000Z", ...]
):
    print("---TOOL CALL: CREATE RECURRING EVENT---")
    service = get_service()

  
    # Build RRULE 
    rrule_parts = [f"FREQ={frequency.upper()}"]

    if interval:
        rrule_parts.append(f"INTERVAL={interval}")

    # Weekly patterns: BYDAY=MO,WE,FR
    if weekdays:
        byday = ",".join(weekdays)
        rrule_parts.append(f"BYDAY={byday}")

    # Simple monthly: BYMONTHDAY=15
    if monthday:
        rrule_parts.append(f"BYMONTHDAY={monthday}")

    # Advanced monthly: BYDAY=1TU (1st Tue), -1MO (last Mon)
    if nth_weekday:
        nth = nth_weekday.get("nth")
        weekday = nth_weekday.get("weekday")
        rrule_parts.append(f"BYDAY={nth}{weekday}")

    if until:
        rrule_parts.append(f"UNTIL={until}")

    if count:
        rrule_parts.append(f"COUNT={count}")

    rrule_string = ";".join(rrule_parts)
    print(f'---RRULE STRING: {rrule_string}---')

    
    # Build EXDATE list (if any)
    exdate_block = None
    if exception_dates:
        # Google wants: "EXDATE:20250110T090000Z,20250115T090000Z"
        exdate_block = ",".join(exception_dates)

    # Build Event Body
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start,
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end,
            'timeZone': timezone,
        },
        'recurrence': [
            f"RRULE:{rrule_string}"
        ]
    }

    if exdate_block:
        event["recurrence"].append(f"EXDATE:{exdate_block}")


    # Put request
    try:
      event = service.events().insert(calendarId='primary', body=event).execute()
      return f"Recurring event created: {event.get('htmlLink')}"

    except HttpError as error:
      msg_history.append({"role": "system", "content": f"An error occurred: {error}"})
      print(f"An error occurred: {error}")
      
def readEvents(num_events, starttime, endtime):
  print("---TOOL CALL: READ EVENTS - START: " + starttime + " END: " + endtime + "---")
  try:
    service = get_service()

    # Call the Calendar API
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=starttime,  # start of search windo
            timeMax=endtime, # end of search window
            maxResults=num_events,
            singleEvents=True, # does not return series masters, only instances
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
      msg_history.append({"role": "system", "content": "No upcoming events found."})
      return

    
    try:
      # make a string of events to return to Agent 
      msg = " "
      for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        msg += f"{start} to {end}:  {event['summary']}\n"
      
      return "Retrieved events: \n" + msg
    
    except HttpError as error:
      msg_history.append({"role": "system", "content": f"Error processing events: {error}"})
      print(f"Error processing events: {error}")



  except HttpError as error:
    print(f"An error occurred: {error}")

def delete_event(title, starttime, endtime):
  print("---TOOL CALL: DELETE EVENT---")
  
  try:
    service = get_service()

    events_result = (
      service.events()
      .list(
        calendarId="primary",
        timeMin=starttime, # start of search window
        timeMax=endtime, # end of search window
        maxResults=999,
        singleEvents=True, # get instances, not series masters
        orderBy="startTime",
      )
      .execute()
    )
    events = events_result.get("items", [])
    
    if not events:
      msg_history.append({"role": "tool", "content": "No events found."})
      return
      
    # CRAZY HACk: Build a title --> id list of tuples for chat to read; it picks the id of the event that matches the title argument
    name_id_list = []
    for event in events:
      name_id_list.append((event["summary"], event["id"]))

    # Convert the list of tuples to a string format that OpenAI can understand
    event_list_str = "\n".join([f"{name}: (id: {id})" for name, id in name_id_list])
    completion = client.chat.completions.create(
      model="gpt-5.1",
      store=True,
      messages=[
          {"role": "system", "content": """Given a list of event names and their corresponding IDs, find the ID of the event that matches 
          the provided title and return ONLY the ID."""},
          {"role": "user", "content": f"Event to delete: {title}\nAvailable events:\n{event_list_str}"}
      ]
    )

    id = completion.choices[0].message.content
  

    # delete request with chosen id 
    try:
      service.events().delete(calendarId='primary', eventId=id).execute()
      return f"Deleted event with ID: {id}, title: {title}"
    
    except HttpError as error:
      msg_history.append({"role": "system", "content": f"Failed to delete event with ID: {id}, title: {title}. Error: {error}"})
      print(f"Failed to delete event with ID: {id}, title: {title}. Error: {error}")
      return
 


  except HttpError as error:
    msg_history.append({"role": "system", "content": f"An error occurred: {error}"})
    print(f"An error occurred: {error}")

def delete_recurring(title, starttime, endtime):

  print("---TOOL CALL: DELETE RECURRING SERIES---")

  try:
    service = get_service()

    # Retrieve recurring masters (singleEvents=False)
    events_result = (
      service.events()
      .list(
        calendarId="primary",
        timeMin=starttime,
        timeMax=endtime,
        maxResults=999,
        singleEvents=False, # <--- key: get series masters (stems for recurring evs)
        )
        .execute()
      )

    events = events_result.get("items", [])

    # Filter to only recurring series masters
    recurring_masters = [event for event in events if event.get("recurrence") and not event.get("recurringEventId")]

    if not recurring_masters:
      msg_history.append({"role": "tool", "content": "No recurring series found."})
      return


    # Build summary -> id list for GPT selection, same crazy Hack as delete_event
    name_id_list = []
    for event in recurring_masters:
      summary = event["summary"]
      event_id = event["id"]
      name_id_list.append((summary, event_id))

    event_list_str = "\n".join([
      f"{name}: (id: {id})"
      for name, id in name_id_list
    ])

    completion = client.chat.completions.create(
      model="gpt-5.1",
      store=True,
      messages=[
        {"role": "system", "content": """Given a list of recurring event series names and their IDs, return ONLY the ID of the series 
        that best matches the provided title. Return ONLY the ID."""},
        {"role": "user", "content": f"Recurring series to delete: {title} \nAvailable series:\n{event_list_str}"}
      ]
    )

    chosen_id = completion.choices[0].message.content

    # delete request with chat's chosen id
    try:
      service.events().delete(
      calendarId="primary",
      eventId=chosen_id
    ).execute()

      return f"Deleted recurring series with ID: {chosen_id}, title: {title}"
    
    except HttpError as error:
      msg_history.append({"role": "system", "content": f"Failed to delete recurring series with ID: {chosen_id}, title: {title}. Error: {error}"})
      print(f"Failed to delete recurring series with ID: {chosen_id}, title: {title}. Error: {error}")
      return

  except HttpError as error:
    msg_history.append({"role": "system", "content": f"An error occurred: {error}"})
    print(f"An error occurred: {error}")

def patch_event(title, starttime, endtime, patch_body, modify_series):
  print(f'---TOOL CALL: PATCH EVENT | MODIFY SERIES = {modify_series}---')

  try:
    service = get_service()

    events_result = service.events().list(
      calendarId="primary",
      timeMin=starttime, # just get like every event 
      timeMax=endtime,
      maxResults=999,
      singleEvents=not modify_series, # if modify series is true, we don't want single events. but if its false we do
    ).execute()

    events = events_result.get("items", [])
    if not events:
      return "No events found to patch."

    # same hack as always
    name_id_list = []
    for event in events:
      name_id_list.append((event["summary"], event["id"]))

    # Convert the list of tuples to a string format that OpenAI can understand
    event_list_str = "\n".join([f"{name}: (id: {id})" for name, id in name_id_list])
    completion = client.chat.completions.create(
      model="gpt-5.1",
      store=True,
      messages=[
          {"role": "system", "content": """Given a list of event names and their corresponding IDs, find the ID of the event that matches 
          the provided title and return ONLY the ID."""},
          {"role": "user", "content": f"Event to delete: {title}\nAvailable events:\n{event_list_str}"}
      ]
    )
    # id of the instance event we found
    target_id = completion.choices[0].message.content

    # Determine whether this event is part of a series
    event_obj = service.events().get(calendarId="primary", eventId=target_id).execute()

    # if we're changing a recurring series' rules, get the id of the master event
    if modify_series and "recurringEventId" in event_obj:
      patch_id = event_obj["recurringEventId"]        
    
    # if not, continue with the same id from mr. gpt
    else:
      patch_id = target_id

    # retrieve said master event to get its start/end time so we can modify
    # it with just its day so it doesn't screw up the recurring events in the series
    if modify_series:
      master = service.events().get(calendarId="primary", eventId=patch_id).execute()

      # normalize start/end if user provided them | keep date of the master event, use time from the instance event the agent returned
      # (since the agent will want to change the series with the date of the instance it pulled, which messes stuff up)
      if "start" in patch_body:
        patch_body["start"] = {
          "dateTime": master["start"]["dateTime"][:10] + "T" +
                      patch_body["start"]["dateTime"].split("T")[1],
          "timeZone": master["start"]["timeZone"]
        }

      if "end" in patch_body:
        patch_body["end"] = {
          "dateTime": master["end"]["dateTime"][:10] + "T" +
                      patch_body["end"]["dateTime"].split("T")[1],
          "timeZone": master["end"]["timeZone"]
        }

    
    # try the patch. channel the spirit of the flex tape. (?)
    service.events().patch(calendarId="primary", eventId=patch_id, body=patch_body).execute()

    if not patch_body:
      return "Patch body was empty. No changes applied."

    return f"Patched event '{title}' (id:{patch_id}) with: {patch_body}"

  except Exception as error:
    print("Patch failed:", error)
    return f"Patch failed: {error}"