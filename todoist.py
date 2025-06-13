import toml
from todoist_api_python.api import TodoistAPI
from openai import OpenAI

CONFIG = toml.load("config.toml")
TODOIST_API_KEY = CONFIG["todoist"]["api"]
OPENAI_API_KEY = CONFIG["openai"]["api"]
USER_NAME = CONFIG["user"]["name"]


api = TodoistAPI(TODOIST_API_KEY)

from datetime import datetime

def generate_task_list(query=None, properties=None):
    tasks = [t for page in api.get_tasks() for t in page]
    tasks.sort(key=lambda t: (t.due is not None, str(t.due.date) if t.due else ""))

    project_lookup = {str(p.id): p.name for page in api.get_projects() for p in page}
    tasks = [t for page in api.get_tasks() for t in page]

    tasks.sort(key=lambda t: (t.due is not None, str(t.due.date) if t.due else ""))

    out = ""
    for t in tasks:
        due = t.due.date if t.due else None
        if due:
            try:
                due = datetime.fromisoformat(str(due)).strftime("%Y-%m-%d (%A)")
            except:
                pass

        line = f"content: {t.content}"
        if due:
            line += f", due_date: {due}"
        if t.project_id and str(t.project_id) in project_lookup:
            line += f", project: {project_lookup[str(t.project_id)]}"

        out += line + "\n"

    return out





def search(query, limit=5):
    TL = generate_task_list(query=query)
    client = OpenAI(api_key=OPENAI_API_KEY)

    today = datetime.now().strftime("%Y-%m-%d (%A)")
    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=f"Answer the user's question based on the provided task list. The current user is {USER_NAME}, and the date is {today}.",
        input=f"{query}\n\nHere is the task list:\n{TL}",
    )

    print(response.output_text)
    return response.output_text

if __name__ == "__main__":
    searches =["What am I doing thursday?", "What do I have on Laurens list?", "What tasks are due today?"]
    for search_query in searches:
        print(search(search_query))