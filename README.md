# Schedule Guru

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-gpt--5.1-412991?logo=openai&logoColor=white)
![Google Calendar](https://img.shields.io/badge/Google%20Calendar-API%20v3-4285F4?logo=googlecalendar&logoColor=white)
![Status](https://img.shields.io/badge/status-in%20development-orange)

An AI chat interface that allows you to manage your Google Calendar via natural language.

Ask it to schedule a meeting, move an appointment, set up a recurring event, or clear your afternoon in plain English; it tranforms your requests into Google Calendar API calls and reports back conversationally.

## Demo

Demo of the current version:

[![current version demo](https://img.youtube.com/vi/qWKtCeK2vFg/0.jpg)](https://www.youtube.com/watch?v=qWKtCeK2vFg)

## Features

- Dynamic natural-language scheduling: create, read, update, and delete events through conversation that are custom-fit to your schedule
- Recurring events via RRULEs (`create_recurring`, `delete_recurring`)
- Fuzzy event matching: refer to events by description ("move my dentist appointment") instead of IDs
- Conversational summaries of what changed, rather than raw API responses

**Calendar tools:** `create` · `create_recurring` · `readEvents` · `patch_event` · `delete_event` · `delete_recurring`

## Architecture

<p align="center">
  <img src="assets/schedule-guru-architecture1.png" alt="Schedule Guru system architecture" width="900">
</p>

A React frontend talks to a Flask backend that runs an OpenAI `gpt-5.1` agent loop. The model acts as a planner: it either replies directly or selects one of six calendar tools. Tool results are fed through a second `gpt-5.1` summarizer pass that turns raw API output into plain English (and can chain further tool calls). For `delete` and `patch` flows, a small `gpt-5.1` helper performs fuzzy title → `eventId` matching, resolving a spoken event name against the actual events on your calendar. All calendar operations go through the Google Calendar API v3, authorized via OAuth 2.0.

## Tech stack

| Layer    | Stack                                               |
| -------- | --------------------------------------------------- |
| Frontend | React 19, Vite                                      |
| Backend  | Python, Flask-CORS                                  |
| LLM      | OpenAI `gpt-5.1` (function calling)                 |
| Calendar | Google Calendar API v3 (`google-api-python-client`) |
| Auth     | OAuth 2.0 (`google-auth-oauthlib`)                  |

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI API key
- A Google Cloud project with the Google Calendar API enabled and an OAuth 2.0 **Desktop** client (or just trust my project perms)

### Backend

```bash
cd backend
pip install flask flask-cors openai python-dotenv \
  google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```

Create `backend/.env` with your OpenAI key:

```env
OPENAI_API_KEY=your_key_here
```

Download your OAuth client file from the Google Cloud Console, rename it to `credentials.json`, and place it in the project root. On first run you'll be prompted to authorize calendar access in the browser, and a `token.json` will be created automatically.

> **Note:** keep `credentials.json` and `token.json` out of version control — they hold your OAuth client secret and a live access token. Make sure both are listed in `.gitignore`.

Run the server:

```bash
python app.py        # http://localhost:5000  (POST /chat)
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```
