from flask import Flask, request, jsonify
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

# tweaked chat version that takes user input as arg for post requests
def chat(user_input):    
    # Add user message to history
    msg_history.append({"role": "user", "content": user_input})
    
    # Agent loop
    calling_tool = True
    called_a_tool = False
    
    while calling_tool:
        # agent response
        completion = client.chat.completions.create(
            model="gpt-5.1",
            messages=msg_history,
            tools=TOOLS,
            tool_choice="auto"
        )
        msg = completion.choices[0].message
        
        # case 1: Just a text response, no tool call
        if not called_a_tool and msg.content is not None and msg.tool_calls is None:
            msg_history.append({"role": "assistant", "content": msg.content})
            return msg.content
        
        # case 2: Previously called tool(s), now returning summary
        elif called_a_tool and msg.content is not None and msg.tool_calls is None:
            break
        
        # case 3: Tool call
        elif msg.tool_calls is not None:
            called_a_tool = True
            tool = msg.tool_calls[0]
            msg_history.append({"role": "assistant", "tool_calls": msg.tool_calls, "content": msg.content or ""}) 
            
            # execute tool
            function_name = tool.function.name
            function_args = json.loads(tool.function.arguments)
            result = tool_call(function_name, function_args)
            
            # add tool result to history
            msg_history.append({"role": "tool", "tool_call_id": msg.tool_calls[0].id, "content": result or ""})
    
    # get tool call(s) summary
    if called_a_tool:
        msg_history.append({"role": "system", "content": summary_prompt})
        tool_summary = client.chat.completions.create(
            model="gpt-5.1",
            messages=msg_history,
        )
        final_msg = tool_summary.choices[0].message
        msg_history.append({"role": "assistant", "content": final_msg.content})
        return final_msg.content
    
    return "uhhhh ummm"

@app.route('/chat', methods=['POST'])
def chat_route():
  # the yap 
  data = request.json
  user_message = data.get('message', '')
    
  # Process message and get response
  response = chat(user_message)
    
  return jsonify({'response': response})

if __name__ == '__main__':
  app.run(debug=True)
