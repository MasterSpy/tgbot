from typing import Optional, List

from telegram import Update, Bot
from telegram.ext import run_async, Filters, MessageHandler

# todo have an SQL table and settings options to save restriction time and type
#import tg_bot.modules.sql.welcome_sql as sql
from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import bot_admin, can_restrict

HANDLER_GROUP = 50

@run_async
@bot_admin
@can_restrict
def new_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    new_members = update.effective_message.new_chat_members
    for new_mem in new_members:
        # Don't restrict yourself
        if new_mem.id == bot.id:
            continue

        else:
            bot.restrict_chat_member(chat_id=chat.id, user_id=new_mem.id,
                            can_send_messages=True, can_send_media_messages=False,
                            can_send_other_messages=False, can_add_web_page_previews=False, until_date=0)


NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members, new_member)

dispatcher.add_handler(NEW_MEM_HANDLER, HANDLER_GROUP)
