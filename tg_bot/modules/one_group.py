# make the bot work on one group only - must have ALLOWED_GROUP set on config

from telegram.ext import Filters, MessageHandler, DispatcherHandlerStop
from telegram.ext.filters import BaseFilter
from tg_bot.config import Development as Config
from tg_bot import dispatcher, updater, SUDO_USERS

#check if allowed group is valid
try:
    ALLOWED_GROUP = int(Config.ALLOWED_GROUP)
except ValueError:
    raise Exception("Your ALLOWED_GROUP variable is not a valid integer.")
except:
    raise Exception("config.py must have valid ALLOWED_GROUP value for this module to work")

#returns true if the command is exactly "/id". This is the only command that is allowed
class id_command(BaseFilter):
    def filter(self, message):
        if message.text == '/id':
            return True

#can't be async to use handlerstop
def mute_group(bot, update):
    #do nothing and stop any other handlers from activating
    raise DispatcherHandlerStop

#capture every message received from a non-allowed group, except "/id" command
mute_handler = MessageHandler(Filters.group & ~ Filters.chat(ALLOWED_GROUP) & ~ id_command(), mute_group)

#use a very high priority to make sure this is handled before anything else
dispatcher.add_handler(mute_handler, -99)

#add all admins of allowed group to sudo, so regular users have differentiated messages
administrators = set(member.user.id for member in updater.bot.get_chat_administrators(ALLOWED_GROUP) if not member.user.is_bot)
SUDO_USERS = list(set(SUDO_USERS) | administrators)
