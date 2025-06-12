import telebot
from telebot.types import BotCommand
import toml
from agents import bot_agents

# ---- CONFIG ----
CONFIG = toml.load("config.toml")
TELEGRAM_TOKEN = CONFIG["telegram"]["token"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

# Register menu commands
bot.set_my_commands([
    BotCommand("personal_notes", "Search your personal notes"),
    BotCommand("ttrpg_notes", "Search TTRPG notes"),
    BotCommand("use_weather", "Get the weather"),
    BotCommand("use_tasks", "Manage your task list"),
])


# Handler registration
@bot.message_handler(commands=["personal_notes"])
def select_personal(msg):
    user_sessions[msg.chat.id] = "personal_notes"
    bot.reply_to(msg, f"You are now using: {bot_agents['personal_notes'].name}")

@bot.message_handler(commands=["ttrpg_notes"])
def select_ttrpg(msg):
    user_sessions[msg.chat.id] = "ttrpg_notes"
    bot.reply_to(msg, f"You are now using: {bot_agents['ttrpg_notes'].name}")

@bot.message_handler(commands=["use_weather"])
def select_weather(msg):
    user_sessions[msg.chat.id] = "use_weather"
    bot.reply_to(msg, f"You are now using: {bot_agents['use_weather'].name}")

@bot.message_handler(commands=["use_tasks"])
def select_tasks(msg):
    user_sessions[msg.chat.id] = "use_tasks"
    bot.reply_to(msg, f"You are now using: {bot_agents['use_tasks'].name}")

@bot.message_handler(func=lambda msg: True, content_types=['text', 'document'])
def route(msg):
    selected = user_sessions.get(msg.chat.id)
    if selected in bot_agents:
        bot_agents[selected].handle(bot, msg)
    else:
        bot.reply_to(msg, "Please choose a bot using the menu commands.")

bot.infinity_polling()
