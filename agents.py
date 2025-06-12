import os
import shutil
import zipfile

import toml

from intake_obsidian import intake
from search_obsidian import search
from openai import OpenAI

# ---- CONFIG ----
CONFIG = toml.load("config.toml")
TELEGRAM_TOKEN = CONFIG["telegram"]["token"]
OPENAI_API_KEY = CONFIG["openai"]["api"]
EXAMPLES_PATH = "examples.jsonl"
USER_PROFILE = CONFIG["prompts"]["user_profile"]
BOT_PROFILE = CONFIG["prompts"]["bot_profile"]

class Agent:
    def __init__(self, name):
        self.name = name

    def handle(self, bot, message):
        raise NotImplementedError("Agent must implement handle()")

class VaultAgent(Agent):
    def __init__(self, name, vault_name):
        super().__init__(name)
        self.vault = vault_name
        self.zip_filename = f"{vault_name}.zip"
        self.dest_dir = f"./temp/{vault_name}"

    def handle(self, bot, message):
        if message.content_type == 'text':
            self._handle_text(bot, message)
        elif message.content_type == 'document':
            self._handle_document(bot, message)

    def _handle_text(self, bot, message):
        bot.send_message(message.chat.id, search(message.text, self.vault))

    def _handle_document(self, bot, message):
        doc = message.document
        if not doc or not doc.file_name.lower().endswith('.zip'):
            return
        if doc.file_name.lower() != self.zip_filename.lower():
            return

        chat_id = message.chat.id
        bot.send_message(chat_id, f"New {self.vault} archive received.")
        print(f"New {self.vault} Obtained")

        if os.path.exists(self.dest_dir):
            shutil.rmtree(self.dest_dir)
        os.makedirs(self.dest_dir, exist_ok=True)

        zip_path = None
        try:
            file_info = bot.get_file(doc.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            zip_path = os.path.join(self.dest_dir, "temp.zip")

            with open(zip_path, "wb") as f:
                f.write(downloaded_file)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.dest_dir)

        except zipfile.BadZipFile:
            bot.send_message(chat_id, "Failed to unzip file. Make sure it's a valid .zip archive.")
            return
        except Exception as e:
            bot.send_message(chat_id, f"Error downloading or extracting: {e}")
            return
        finally:
            if zip_path and os.path.exists(zip_path):
                os.remove(zip_path)

        try:
            result = intake(self.dest_dir, self.vault)
            bot.send_message(chat_id, result or "(intake returned nothing)")
        except Exception as e:
            bot.send_message(chat_id, f"Error running intake(): {str(e)}")

class PersonalNotesAgent(VaultAgent):
    def __init__(self):
        super().__init__("Search_Personal_Notes", "wanderland")


class TTRPGNotesAgent(VaultAgent):
    def __init__(self):
        super().__init__("Search_TTRPG_Notes", "TTRPG")


class WeatherAgent(Agent):
    def __init__(self):
        super().__init__("Weather_Bot")

    def handle(self, bot, message):
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model="gpt-4.1",
            tools=[{"type": "web_search_preview"}],
            input=[
                {
                    "role": "developer",
                    "content": BOT_PROFILE + USER_PROFILE + "The current USERMODE is 'Weather."
                },
                {
                    "role": "user",
                    "content": message.text
                }
            ]
        )

        print(response.output_text)
        bot.send_message(message.chat.id, response.output_text)


class TaskAgent(Agent):
    def __init__(self):
        super().__init__("TaskMaster")

    def handle(self, bot, message):
        if message.text.lower().startswith("add task"):
            bot.send_message(message.chat.id, f"[{self.name}] Task added: {message.text[9:].strip()}")
        else:
            bot.send_message(message.chat.id, f"[{self.name}] I do not understand: {message.text}")


bot_agents = {
    "personal_notes": PersonalNotesAgent(),
    "ttrpg_notes": TTRPGNotesAgent(),
    "use_weather": WeatherAgent(),
    "use_tasks": TaskAgent()
}
