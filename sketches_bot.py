import pickle
import os.path
import googleapiclient.discovery
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import telegram
from telegram.ext import CommandHandler, MessageHandler, Filters
import time
import random
import os
import sys
from telegram.ext import Updater
from threading import Thread
from typing import List
from typing import Optional
from typing import Any
from typing import NamedTuple

import credentials
SPREADSHEET_ID = credentials.spreadsheetId
TELEGRAM_UPDATER_TOKEN = credentials.telegramUpdaterToken
TELEGRAM_BOT_TOKEN = credentials.telegramBotToken
SCOPES = credentials.scopes
SPREADSHEET_RANGE = credentials.spreadsheetRange

class Prompt(NamedTuple):
    prompt_text: str
    submitter_name: Optional[str]

class PromptList:
    def __init__(self) -> None:
        self.unused_prompts: List[Prompt] = []
        self.used_prompts: List[Prompt] = []

    def get_random_prompt(self) -> Optional[Prompt]:
        if len(self.unused_prompts) > 0:
            random.shuffle(self.unused_prompts)
            prompt = self.unused_prompts.pop()
            self.used_prompts.append(prompt)
            return prompt
        else:
            return None

"""
GOOGLE SHEETS INTEGRATION
"""

def google_authentication() -> Any:
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

def call_api(range: str) -> List[Prompt]:
    creds = google_authentication()

    service = googleapiclient.discovery.build('sheets', 'v4', credentials=creds)
    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range=range).execute()
    values = result.get('values', [])

    prompts: List[Prompt] = []

    for row in values:
        if len(row) == 2:
            prompt = Prompt(row[0], row[1])
        else:
            prompt = Prompt(row[0], None)
        prompts.append(prompt)

    return prompts


"""
TELEGRAM INTEGRATION
"""

def start_bot(updater: Any, context: Any) -> None:
    custom_keyboard = [['Get me a prompt!']]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(chat_id=updater.effective_chat.id,
                 text="Welcome to the Sketches From a Hat Bot!",
                 reply_markup=reply_markup)

def send_prompt(update: Any, context: Any, prompt_list: PromptList) -> None:
    # selected_prompt is a list like [prompt, submitter_name]
    # or, is None if there are no prompts to return
    # submitter_name is optional
    selected_prompt = prompt_list.get_random_prompt()

    if not selected_prompt:
        context.bot.send_message(chat_id=update.effective_chat.id, parse_mode="Markdown", text="No prompts have been submitted yet. Go out there and get some!")
    elif len(selected_prompt) == 2:
        context.bot.send_message(chat_id=update.effective_chat.id, parse_mode="Markdown", text="*Prompt:* %s\n*Submitted by:* %s" % (selected_prompt[0], selected_prompt[1]))
    elif len(selected_prompt) == 1:
        context.bot.send_message(chat_id=update.effective_chat.id, parse_mode="Markdown", text="*Prompt:* %s\n*Submitted by:* Anonymous" % selected_prompt[0])

def main() -> None:
    starttime=time.time()

    updater = Updater(token=TELEGRAM_UPDATER_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

    prompt_list = PromptList()

    dispatcher.add_handler(CommandHandler('start', start_bot))

    def _send_prompt(update: Any, context: Any) -> None:
        send_prompt(update, context, prompt_list)
    dispatcher.add_handler(MessageHandler(Filters.text('Get me a prompt!'), _send_prompt))

    updater.start_polling()

    last_row = 2

    try:
        while True:
          RANGE_NAME = SPREADSHEET_RANGE.format(last_row)

          prompt_list.unused_prompts.extend(call_api(RANGE_NAME))
          last_row = len(prompt_list.unused_prompts) + len(prompt_list.used_prompts) + 2
          print(prompt_list.unused_prompts)
          time.sleep(60.0 - ((time.time() - starttime) % 60.0))
    except KeyboardInterrupt:
        print("exiting...")
        os._exit(0)

if __name__ == '__main__':
    main()
