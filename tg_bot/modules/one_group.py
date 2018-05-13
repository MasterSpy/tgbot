# make the bot work on one group only - must have ALLOWED_GROUP set on config

from telegram import ParseMode, error
from telegram.ext import Filters, MessageHandler, CommandHandler, DispatcherHandlerStop, run_async
from telegram.ext.filters import BaseFilter
from tg_bot.config import Development as Config
from tg_bot import dispatcher, updater
import tg_bot

#check if allowed group is valid
try:
    ALLOWED_GROUP = int(Config.ALLOWED_GROUP)
except ValueError:
    raise Exception("Your ALLOWED_GROUP variable is not a valid integer.")
except:
    raise Exception("config.py must have valid ALLOWED_GROUP value for this module to work")

#returns true if the command is exactly "/id". This is the only command that is allowed on other groups
class IdCommand(BaseFilter):
    def filter(self, message):
        if message.text == '/id':
            return True

id_command = IdCommand()

#can't be async to use handlerstop
def mute_group(bot, update):
    #do nothing and stop any other handlers from activating
    raise DispatcherHandlerStop

@run_async
def announce(bot, update):
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    if user.id in tg_bot.SUDO_USERS:
        announcement = message.text.split(maxsplit=1)
        if len(announcement) <2:
            update.effective_chat.send_message(text="You must type something to be announced after the command.")
        else:
            try:
                bot.send_message(chat_id=ALLOWED_GROUP, text=announcement[1], parse_mode=ParseMode.MARKDOWN)
                update.effective_chat.send_message(text="Announced!")
            except error.BadRequest as e:
                update.effective_chat.send_message(text=str(e))


#capture every message received from a non-allowed group, except "/id" command
MUTE_HANDLER = MessageHandler(Filters.group & ~ Filters.chat(ALLOWED_GROUP) & ~ id_command, mute_group)
ANNOUNCE_HANDLER = CommandHandler('announce', announce, filters=Filters.private)

#use a very high priority to make sure this is handled before anything else
dispatcher.add_handler(MUTE_HANDLER, -99)
dispatcher.add_handler(ANNOUNCE_HANDLER)

#add all admins of allowed group to sudo, so regular users have differentiated messages
administrators = set(member.user.id for member in updater.bot.get_chat_administrators(ALLOWED_GROUP) if not member.user.is_bot)
tg_bot.SUDO_USERS = list(set(tg_bot.SUDO_USERS) | administrators)

__help__ = """
Disable all commands (except `/id`) in all groups except the group set in `Config.ALLOWED_GROUP` (currently set to \
{})

*Admin only:*
 - /announce <message>: send a message to the group via the bot, with [markdown]\
(https://core.telegram.org/bots/api#markdown-style) enabled.""".format(ALLOWED_GROUP)

__mod_name__ = "One Group"