from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS

from vars import msg_history, summary_prompt, TOOLS

from openai import OpenAI
import json

from dotenv import load_dotenv
from pathlib import Path
import os

from main import tool_call


app = Flask(__name__)
# let frontend access backend
CORS(app)


env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(env_path)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key= OPENAI_API_KEY)

# labels shown in the frontend "tool running" visualizer
TOOL_LABELS = {
    "create": "Creating event",
    "create_recurring": "Creating recurring event",
    "readEvents": "Checking your calendar",
    "delete_event": "Deleting event",
    "delete_recurring": "Deleting recurring series",
    "patch_event": "Updating event",
}


# Streaming chat: runs the agent loop and yields events as they happen so the
# frontend can render tokens live and visualize tool calls
#
# event shapes:
#   {"type": "token", "content": "..."} append to assistant text
#   {"type": "tool", "status": "start"|"end", "name", "label"} tool-call visualizer
#   {"type": "done"} turn finished
#   {"type": "error", "message": "..."} something blew up
def stream_chat(user_input):
    # Add user message to history
    msg_history.append({"role": "user", "content": user_input})

    called_a_tool = False

    # Agent loop
    while True:
        stream = client.chat.completions.create(
            model="gpt-5.1",
            messages=msg_history,
            tools=TOOLS,
            tool_choice="auto",
            stream=True,
        )

        content = ""
        # index -> {"id", "name", "arguments"} accumulated across deltas
        tool_calls_acc = {}
        # only stream tokens to the user on a pre-tool turn; post-tool text is
        # discarded in favor of the dedicated summary pass below
        stream_live = not called_a_tool

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # text tokens
            if delta.content:
                content += delta.content
                if stream_live:
                    yield {"type": "token", "content": delta.content}

            # tool-call deltas arrive piecemeal and must be stitched together
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = tool_calls_acc.setdefault(
                        tc.index, {"id": None, "name": "", "arguments": ""}
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments

        # case 1 & 2: no tool call this turn -> it's a text response
        if not tool_calls_acc:
            if not called_a_tool:
                # plain chat answer (already streamed live above)
                msg_history.append({"role": "assistant", "content": content})
                yield {"type": "done"}
                return
            # finished using tools -> fall through to the summary pass
            break

        # case 3: tool call(s) -> record the assistant turn and run each tool
        called_a_tool = True
        ordered = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
        msg_history.append({
            "role": "assistant",
            "content": content or "",
            "tool_calls": [
                {
                    "id": c["id"],
                    "type": "function",
                    "function": {"name": c["name"], "arguments": c["arguments"]},
                }
                for c in ordered
            ],
        })

        for c in ordered:
            name = c["name"]
            yield {
                "type": "tool",
                "status": "start",
                "name": name,
                "label": TOOL_LABELS.get(name, name),
            }

            try:
                args = json.loads(c["arguments"]) if c["arguments"] else {}
                result = tool_call(name, args)
            except Exception as error:
                result = f"Tool error: {error}"

            yield {"type": "tool", "status": "end", "name": name}
            msg_history.append({
                "role": "tool",
                "tool_call_id": c["id"],
                "content": result or "",
            })

    # Summary pass: turn the tool result(s) into a nice streamed message
    msg_history.append({"role": "system", "content": summary_prompt})
    summary = ""
    summary_stream = client.chat.completions.create(
        model="gpt-5.1",
        messages=msg_history,
        stream=True,
    )
    for chunk in summary_stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            summary += delta.content
            yield {"type": "token", "content": delta.content}

    msg_history.append({"role": "assistant", "content": summary})
    yield {"type": "done"}


@app.route('/chat', methods=['POST'])
def chat_route():
    # the yap
    data = request.json
    user_message = data.get('message', '')

    # Stream the agent's work back as newline-delimited JSON events
    def generate():
        try:
            for event in stream_chat(user_message):
                yield json.dumps(event) + "\n"
        except Exception as error:
            yield json.dumps({"type": "error", "message": str(error)}) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

if __name__ == '__main__':
  app.run(debug=True, threaded=True)
