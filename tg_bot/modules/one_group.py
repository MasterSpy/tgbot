# make the bot work on one group only - must have ALLOWED_GROUP set on config

from telegram.ext import Filters, MessageHandler, DispatcherHandlerStop
from telegram.ext.filters import BaseFilter
from tg_bot.config import Development as Config
from tg_bot import dispatcher

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
mute_handler = MessageHandler(~ Filters.chat(ALLOWED_GROUP) & ~ id_command(), mute_group)

#use a very high priority to make sure this is handled before anything else
dispatcher.add_handler(mute_handler, -99)
