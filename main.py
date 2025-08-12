import os
import json
import uuid
import requests
import telebot
import toml

# --- CONFIG ---
CONFIG = toml.load("config.toml")
TELEGRAM_BOT_TOKEN = CONFIG["telegram"]["token"]
OPENROUTER_API_KEY = CONFIG["openrouter"]["api"]
TODOIST_API_TOKEN = CONFIG["todoist"]["api"]

if not all([TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, TODOIST_API_TOKEN]):
    raise ValueError("Missing required environment variables: TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, TODOIST_API_TOKEN")

# --- TELEGRAM ---
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- TOOLS DEFINITION ---
try:
    with open('tools.json', 'r') as f:
        tools_definition = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError("The 'tools.json' file was not found. Please create it and add your OpenAI Tools Definition JSON.")
except json.JSONDecodeError:
    raise ValueError("The 'tools.json' file is not valid JSON.")

# --- STATE ---
conversation_histories = {}

# --- TODOIST REST v2 BASE ---
TODOIST_BASE = "https://api.todoist.com/rest/v2"
JSON_HEADERS = {
    "Authorization": f"Bearer {TODOIST_API_TOKEN}",
    "Content-Type": "application/json",
}
AUTH_HEADERS = {
    "Authorization": f"Bearer {TODOIST_API_TOKEN}",
}

def _safe_json(r):
    try:
        return r.json()
    except ValueError:
        return {"_non_json_body": r.text}

# --- TODOIST HELPERS (REST v2) ---

def create_task(content, **kwargs):
    """Create task. Accepts: content, description, project_id, section_id, parent_id, order,
       labels (list[str]), priority (1-4), due_string, due_date, due_datetime, due_lang."""
    try:
        api_url = f"{TODOIST_BASE}/tasks"
        headers = {**JSON_HEADERS, "X-Request-Id": str(uuid.uuid4())}
        payload = {"content": content}
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        r = requests.post(api_url, headers=headers, json=payload, timeout=(5, 20))
        r.raise_for_status()
        task = _safe_json(r)
        return json.dumps({"status": "success",
                           "message": f"Task '{task.get('content')}' created successfully.",
                           "task_id": task.get('id')})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def get_tasks(**kwargs):
    """List active tasks. Supports project_id, label, filter, ids (comma-separated), etc."""
    try:
        api_url = f"{TODOIST_BASE}/tasks"
        params = {k: v for k, v in kwargs.items() if v is not None}
        r = requests.get(api_url, headers=AUTH_HEADERS, params=params, timeout=(5, 20))
        r.raise_for_status()
        tasks = _safe_json(r)
        if not tasks:
            return json.dumps({"status": "success", "message": "No tasks found matching the criteria."})
        formatted = [{"id": t.get("id"),
                      "content": t.get("content"),
                      "due": t.get("due"),
                      "project_id": t.get("project_id")} for t in tasks]
        return json.dumps({"status": "success", "tasks": formatted})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def get_task(task_id):
    try:
        r = requests.get(f"{TODOIST_BASE}/tasks/{task_id}", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps(_safe_json(r))
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def update_task(task_id, **kwargs):
    """Update task. Same fields as create_task (appropriate subset)."""
    try:
        r = requests.post(f"{TODOIST_BASE}/tasks/{task_id}", headers=JSON_HEADERS,
                          json={k: v for k, v in kwargs.items() if v is not None},
                          timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Task {task_id} updated."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def close_task(task_id):
    try:
        r = requests.post(f"{TODOIST_BASE}/tasks/{task_id}/close", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Task {task_id} completed."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def reopen_task(task_id):
    try:
        r = requests.post(f"{TODOIST_BASE}/tasks/{task_id}/reopen", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Task {task_id} reopened."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def delete_task(task_id):
    try:
        r = requests.delete(f"{TODOIST_BASE}/tasks/{task_id}", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Task {task_id} deleted."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def create_project(name, **kwargs):
    try:
        r = requests.post(f"{TODOIST_BASE}/projects", headers=JSON_HEADERS,
                          json={"name": name, **{k: v for k, v in kwargs.items() if v is not None}},
                          timeout=(5, 20))
        r.raise_for_status()
        p = _safe_json(r)
        return json.dumps({"status": "success", "message": f"Project '{p.get('name')}' created.", "project_id": p.get('id')})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def get_projects():
    try:
        r = requests.get(f"{TODOIST_BASE}/projects", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        projects = _safe_json(r)
        formatted = [{"id": p.get("id"), "name": p.get("name")} for p in projects]
        return json.dumps({"status": "success", "projects": formatted})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def get_project(project_id):
    try:
        r = requests.get(f"{TODOIST_BASE}/projects/{project_id}", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps(_safe_json(r))
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def update_project(project_id, **kwargs):
    try:
        r = requests.post(f"{TODOIST_BASE}/projects/{project_id}", headers=JSON_HEADERS,
                          json={k: v for k, v in kwargs.items() if v is not None},
                          timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Project {project_id} updated."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def delete_project(project_id):
    try:
        r = requests.delete(f"{TODOIST_BASE}/projects/{project_id}", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Project {project_id} deleted."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def archive_project(project_id):
    try:
        r = requests.post(f"{TODOIST_BASE}/projects/{project_id}/archive", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Project {project_id} archived."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def unarchive_project(project_id):
    try:
        r = requests.post(f"{TODOIST_BASE}/projects/{project_id}/unarchive", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Project {project_id} unarchived."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def create_section(name, project_id, **kwargs):
    try:
        r = requests.post(f"{TODOIST_BASE}/sections", headers=JSON_HEADERS,
                          json={"name": name, "project_id": project_id, **{k: v for k, v in kwargs.items() if v is not None}},
                          timeout=(5, 20))
        r.raise_for_status()
        s = _safe_json(r)
        return json.dumps({"status": "success", "message": f"Section '{s.get('name')}' created.", "section_id": s.get('id')})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def get_sections(**kwargs):
    try:
        r = requests.get(f"{TODOIST_BASE}/sections", headers=AUTH_HEADERS,
                         params={k: v for k, v in kwargs.items() if v is not None},
                         timeout=(5, 20))
        r.raise_for_status()
        secs = _safe_json(r)
        formatted = [{"id": s.get("id"), "name": s.get("name"), "project_id": s.get("project_id")} for s in secs]
        return json.dumps({"status": "success", "sections": formatted})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def create_label(name, **kwargs):
    try:
        r = requests.post(f"{TODOIST_BASE}/labels", headers=JSON_HEADERS,
                          json={"name": name, **{k: v for k, v in kwargs.items() if v is not None}},
                          timeout=(5, 20))
        r.raise_for_status()
        lbl = _safe_json(r)
        return json.dumps({"status": "success", "message": f"Label '{lbl.get('name')}' created.", "label_id": lbl.get('id')})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def get_labels():
    try:
        r = requests.get(f"{TODOIST_BASE}/labels", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        labels = _safe_json(r)
        formatted = [{"id": l.get("id"), "name": l.get("name"), "is_favorite": l.get("is_favorite")} for l in labels]
        return json.dumps({"status": "success", "labels": formatted})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})

def delete_label(label_id):
    try:
        r = requests.delete(f"{TODOIST_BASE}/labels/{label_id}", headers=AUTH_HEADERS, timeout=(5, 20))
        r.raise_for_status()
        return json.dumps({"status": "success", "message": f"Label {label_id} deleted."})
    except requests.exceptions.RequestException as e:
        body = e.response.text if getattr(e, "response", None) else str(e)
        return json.dumps({"status": "error", "message": f"API Error: {body}"})


available_tools = {
    # Tasks
    "create_task": create_task,
    "get_tasks": get_tasks,
    "get_task": get_task,
    "update_task": update_task,
    "close_task": close_task,
    "reopen_task": reopen_task,
    "delete_task": delete_task,

    # Projects
    "create_project": create_project,
    "get_projects": get_projects,
    "get_project": get_project,
    "update_project": update_project,
    "delete_project": delete_project,
    "archive_project": archive_project,
    "unarchive_project": unarchive_project,

    # Sections
    "create_section": create_section,
    "get_sections": get_sections,

    # Labels
    "create_label": create_label,
    "get_labels": get_labels,
    "delete_label": delete_label,
}

# --- OPENROUTER CALL ---

def call_openrouter(history):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "X-Title": "Todoist Telegram Bot",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": history,
                "tools": tools_definition,
                "tool_choice": "auto",
            },
            timeout=(10, 60),
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter: {e}")
        return None

# --- TELEGRAM HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.chat.id in conversation_histories:
        del conversation_histories[message.chat.id]
    welcome_text = (
        "Todoist assistant ready.\n"
        "Examples:\n"
        "- Add a task to buy groceries tomorrow at 5pm\n"
        "- What are my tasks for today?\n"
        "- Create a new project called Household\n"
    )
    bot.reply_to(message, welcome_text)

def _parse_tool_args(tool_call):
    """Hardened parser for tool_call.function.arguments"""
    args_raw = tool_call.get('function', {}).get('arguments', None)
    if isinstance(args_raw, dict):
        return args_raw
    if isinstance(args_raw, str):
        s = args_raw.strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # Some models may send single tokens or malformed JSON; fall back to {}
            return {}
    return {}

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_text = message.text

    if chat_id not in conversation_histories:
        conversation_histories[chat_id] = []

    history = conversation_histories[chat_id]
    history.append({"role": "user", "content": user_text})

    bot.send_chat_action(chat_id, 'typing')

    max_steps = 5
    for _ in range(max_steps):
        llm_response = call_openrouter(history)
        if not llm_response or not llm_response.get('choices'):
            bot.reply_to(message, "Upstream error.")
            return

        response_message = llm_response['choices'][0]['message']
        history.append(response_message)

        tool_calls = response_message.get("tool_calls")
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.get('function', {}).get('name')
                if function_name in available_tools:
                    function_to_call = available_tools[function_name]
                    try:
                        function_args = _parse_tool_args(tool_call)
                        function_response = function_to_call(**function_args)
                    except Exception as e:
                        function_response = json.dumps({"status": "error", "message": f"Error executing tool: {str(e)}"})
                else:
                    function_response = json.dumps({"status": "error", "message": f"Tool '{function_name}' not found."})

                history.append({
                    "tool_call_id": tool_call.get('id'),
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                })

            bot.send_chat_action(chat_id, 'typing')
            continue

        final_text = response_message.get('content')
        bot.reply_to(message, final_text if final_text else "No response.")
        break
    else:
        bot.reply_to(message, "Exceeded tool loop steps.")

    conversation_histories[chat_id] = history


if __name__ == '__main__':
    print("Bot is starting...")
    bot.polling(none_stop=True)
