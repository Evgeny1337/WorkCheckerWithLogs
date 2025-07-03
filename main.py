import requests
import time
import telegram
from dotenv import load_dotenv, find_dotenv, set_key
from os import environ, getenv
import telegram.ext
import logging

REQUEST_TIMEOUT = 5

logger = logging.getLogger(__file__)


class MyLogsHandler(logging.Handler):

    def __init__(self,chat_id:str, bot: telegram.ext.ExtBot, level = 0):
        super().__init__(level)
        format = logging.Formatter("%(process)d %(levelname)s %(message)s")
        self.setFormatter(format)
        self.bot = bot
        self.chat_id = chat_id

    def emit(self, record):
        log_entry = self.format(record)
        if self.chat_id:
            self.bot.send_message(chat_id=self.chat_id, text=log_entry)

    def set_chatid(self,chat_id):
        self.chat_id = chat_id


def save_chat_id(chat_id: str):
    env_path = find_dotenv()
    if not env_path:
        env_path = '/opt/.env'
    set_key(env_path, 'TG_CHAT_ID', chat_id)
    environ['TG_CHAT_ID'] = chat_id


def create_message(name, url, is_negative=False):
    if is_negative:
        return f"У вас проверили работу '{name}' \n\nК сожалению, в работе нашлись ошибки\n\n[{name}]({url})\."
    return f"У вас проверили работу '{name}'\n\nтПреподавателю все понравилось можете преступать к следующему уроку!\n\n[{name}]({url})\."


def check_reviews(bot:telegram.Bot, chat_id, devman_token):
    headers = {'Authorization':devman_token}
    params = {}
    while True:
        try:
            response = requests.get(
                url='https://dvmn.org/api/long_polling/',
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            review_info = response.json()
            if review_info['status'] == 'found':
                last_attempt = review_info['new_attempts'][-1] 
                lesson_title = last_attempt['lesson_title']
                is_negative = last_attempt['is_negative']
                lesson_url = last_attempt['lesson_url']
                message_text = create_message(lesson_title, lesson_url, is_negative)
                bot.send_message(chat_id=chat_id, text='{}'.format(message_text), parse_mode=telegram.ParseMode.MARKDOWN_V2)
                params = {'timestamp':review_info['last_attempt_timestamp']}
            else:
                params = {'timestamp':review_info['timestamp_to_request']}
        except requests.exceptions.ReadTimeout as e:
            pass
        except requests.exceptions.ConnectionError as e:
            print('Error {}'.format(e))
            time.sleep(5)


def start_handler(update: telegram.Update, context):
    devman_token = context.bot_data.get('devman_token')
    chat_id = update.effective_chat.id
    save_chat_id(str(chat_id))
    logger_handler = context.bot_data.get('logger_handler')
    logger_handler.set_chatid(chat_id)
    logger.info("В данный чат с id {} будут приходить уведомления о проверке работ".format(chat_id))
    check_reviews(context.bot, chat_id, devman_token)
    

def main():
    load_dotenv(override=True)
    devman_token = environ['DEVMAN_TOKEN']
    tg_token = environ['TG_TOKEN']
    chat_id =  getenv('TG_CHAT_ID', '').strip()
    updater = telegram.ext.Updater(token=tg_token, use_context=True)
    bot = updater.bot
    logger_handler = MyLogsHandler(chat_id, bot)
    logger.addHandler(logger_handler)
    logger.setLevel(logging.INFO)
    dispatcher = updater.dispatcher
    dispatcher.bot_data['devman_token'] = devman_token
    dispatcher.bot_data['logger_handler'] = logger_handler
    start_h = telegram.ext.CommandHandler("start",start_handler)
    dispatcher.add_handler(start_h)
    logger.info('Бот запущен...!')
    updater.start_polling()



if __name__ == '__main__':
    main()