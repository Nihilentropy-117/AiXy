import telebot
import keys
import notes

bot_token = keys.telegram_key
bot = telebot.TeleBot(bot_token)


def user_auth(message):
    authorized_users = keys.authorized_users
    user = f"{message.from_user.id}"
    if user in authorized_users:
        return authorized_users[user]
    else:
        return None


@bot.message_handler(func=lambda message: True)
def main_handler(message):
    user = user_auth(message)
    if user:
        notes.flow(message, bot)
    else:
        bot.send_message(message.chat.id, f"Unknown User")
        print(f"Denied User ID {message.from_user.id}")

def main():
    bot.polling()


if __name__ == '__main__':
    main()
