# make the bot work on one group only - must have ALLOWED_GROUP set on config

from telegram import ParseMode, error
from telegram.ext import Filters, MessageHandler, CommandHandler, DispatcherHandlerStop, run_async
from telegram.ext.filters import BaseFilter
from tg_bot.config import Development as Config
from tg_bot import dispatcher, updater
import tg_bot

#check if allowed group is valid
try:
    ALLOWED_GROUPS = [int(allowed) for allowed in Config.ALLOWED_GROUPS]
except ValueError:
    raise Exception("Your ALLOWED_GROUP variable is not a valid integer.")
except:
    raise Exception("config.py must have valid ALLOWED_GROUPS value for this module to work")

#returns true if the command is exactly "/id". This is the only command that is allowed on other groups
class IdCommand(BaseFilter):
    def filter(self, message):
        if message.text == '/id':
            return True

id_command = IdCommand()

#can't be async to use handlerstop
def mute_group(bot, update):
    #do nothing and stop any other handlers from activating
    print("muted")
    raise DispatcherHandlerStop

#capture every message received from a non-allowed group, except "/id" command
MUTE_HANDLER = MessageHandler(Filters.group & ~ Filters.chat(Config.ALLOWED_GROUPS) & ~ id_command, mute_group)
# use a very high priority to make sure this is handled before anything else
dispatcher.add_handler(MUTE_HANDLER, -99)

#add all admins of allowed group to sudo, so regular users have differentiated messages
administrators = set(member.user.id for group in ALLOWED_GROUPS for member in updater.bot.get_chat_administrators(group) if not member.user.is_bot)
tg_bot.SUDO_USERS = list(set(tg_bot.SUDO_USERS) | administrators)

__help__ = """
Disable all commands (except `/id`) in all groups except the group set in `Config.ALLOWED_GROUPS` (currently set to \
`{}`)""".format("`, `".join(str(group) for group in ALLOWED_GROUPS))


__mod_name__ = "One Group"