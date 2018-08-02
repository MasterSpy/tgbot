import html
import re
from typing import Optional, List

import telegram
import telegram.ext as tg
from telegram import Message, Chat, Update, Bot, ParseMode, User, MessageEntity
from telegram import TelegramError
from telegram.error import BadRequest
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html, escape_markdown

import tg_bot.modules.sql.locks_sql as sql
from tg_bot import dispatcher, SUDO_USERS, LOGGER
from tg_bot.config import Development as Config
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import can_delete, is_user_admin, user_not_admin, user_admin, \
    bot_can_delete, is_bot_admin, bot_admin, can_restrict
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import users_sql

LOCK_TYPES = {'sticker': Filters.sticker,
              'audio': Filters.audio,
              'voice': Filters.voice,
              'document': Filters.document,
              'video': Filters.video,
              'contact': Filters.contact,
              'photo': Filters.photo,
              'gif': Filters.document & CustomFilters.mime_type("video/mp4"),
              'url': Filters.entity(MessageEntity.URL) |
                     Filters.caption_entity(MessageEntity.URL) |
                     Filters.entity(MessageEntity.TEXT_LINK) |
                     Filters.caption_entity(MessageEntity.TEXT_LINK),
              'bots': Filters.status_update.new_chat_members,
              'forward': Filters.forwarded,
              'game': Filters.game,
              'location': Filters.location,
              }

GIF = Filters.document & CustomFilters.mime_type("video/mp4")
OTHER = Filters.game | Filters.sticker | GIF
MEDIA = Filters.audio | Filters.document | Filters.video | Filters.voice | Filters.photo
MESSAGES = Filters.text | Filters.contact | Filters.location | Filters.venue | Filters.command | MEDIA | OTHER
PREVIEWS = Filters.entity("url")

RESTRICTION_TYPES = {'messages': MESSAGES,
                     'media': MEDIA,
                     'other': OTHER,
                     'previews': PREVIEWS, # NOTE: this has been removed cos its useless atm.
                     'all': Filters.all}

PERM_GROUP = 1
REST_GROUP = 2


class CustomCommandHandler(tg.CommandHandler):
    def __init__(self, command, callback, **kwargs):
        super().__init__(command, callback, **kwargs)

    def check_update(self, update):
        return super().check_update(update) and not (
                sql.is_restr_locked(update.effective_chat.id, 'messages') and not is_user_admin(update.effective_chat,
                                                                                                update.effective_user.id))


tg.CommandHandler = CustomCommandHandler


# NOT ASYNC
def restr_members(bot, chat_id, members, messages=False, media=False, other=False, previews=False):
    for mem in members:
        if mem.user in SUDO_USERS:
            pass
        try:
            bot.restrict_chat_member(chat_id, mem.user,
                                     can_send_messages=messages,
                                     can_send_media_messages=media,
                                     can_send_other_messages=other,
                                     can_add_web_page_previews=previews)
        except TelegramError:
            pass


# NOT ASYNC
def unrestr_members(bot, chat_id, members, messages=True, media=True, other=True, previews=True):
    for mem in members:
        try:
            bot.restrict_chat_member(chat_id, mem.user,
                                     can_send_messages=messages,
                                     can_send_media_messages=media,
                                     can_send_other_messages=other,
                                     can_add_web_page_previews=previews)
        except TelegramError:
            pass


@run_async
def locktypes(bot: Bot, update: Update):
    update.effective_message.reply_text("\n - ".join(["Locks: "] + list(LOCK_TYPES)) +
                                        "\n - ".join(["\nRestrictions:"] + list(RESTRICTION_TYPES)))


@user_admin
def add_whitelist(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    entities = message.parse_entities(MessageEntity.URL)
    added = []
    for url in entities.values():
        trimmed = re.search(r'(^http:\/\/|^https:\/\/|^ftp:\/\/|^)(www\.)?(\S*)', url, flags=re.I).group(3).lower()
        if trimmed.endswith('/'):
            trimmed = trimmed[:-1]
        sql.add_whitelist(chat.id, trimmed)
        added.append(trimmed)
    message.reply_text("Added {} to whitelist.".format(', '.join(w for w in added)))


@user_admin
def remove_whitelist(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    entities = message.parse_entities(MessageEntity.URL)
    removed = []
    for url in entities.values():
        trimmed = re.search(r'(^http:\/\/|^https:\/\/|^ftp:\/\/|^)(www\.)?(\S*)', url, flags=re.I).group(3).lower()
        if trimmed.endswith('/'):
            trimmed = trimmed[:-1]
        if sql.remove_whitelist(chat.id, trimmed):
            removed.append(trimmed)
    if removed:
        message.reply_text("Removed `{}` from whitelist.".format('`, `'.join(w for w in removed)),
            parse_mode=ParseMode.MARKDOWN)
    else:
        message.reply_text("Could not remove URL from whitelist.")

def list_white(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    all_whitelisted = sql.get_whitelist(chat.id)

    if not all_whitelisted:
        update.effective_message.reply_text("No URLs are whitelisted here!")
        return

    BASIC_WHITE_STRING = "Whitelisted URLs:\n"
    listwhite = BASIC_WHITE_STRING
    for url in sorted(all_whitelisted.keys()):
        entry = "{}, ".format(url)
        if len(entry) + len(listwhite) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(listwhite)
            listwhite = entry
        else:
            listwhite += entry

    if not listwhite == BASIC_WHITE_STRING:
        update.effective_message.reply_text(listwhite)


@user_admin
@bot_can_delete
@loggable
def lock(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    if can_delete(chat, bot.id):
        if len(args) >= 1:
            if args[0] in LOCK_TYPES:
                sql.update_lock(chat.id, args[0], locked=True)
                message.reply_text("Locked {} messages for all non-admins!".format(args[0]))

                return "<b>{}:</b>" \
                       "\n#LOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nLocked <code>{}</code>.".format(html.escape(chat.title),
                                                          mention_html(user.id, user.first_name), args[0])

            elif args[0] in RESTRICTION_TYPES:
                sql.update_restriction(chat.id, args[0], locked=True)

                message.reply_text("Locked {} for new members!".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#LOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nLocked <code>{}</code>.".format(html.escape(chat.title),
                                                          mention_html(user.id, user.first_name), args[0])

            else:
                message.reply_text("What are you trying to lock...? Try /locktypes for the list of lockables")

    else:
        message.reply_text("I'm not an administrator, or haven't got delete rights.")

    return ""


@run_async
@user_admin
@loggable
def unlock(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    if is_user_admin(chat, message.from_user.id):
        if len(args) >= 1:
            if args[0] in LOCK_TYPES:
                sql.update_lock(chat.id, args[0], locked=False)
                message.reply_text("Unlocked {} for everyone!".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#UNLOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nUnlocked <code>{}</code>.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name), args[0])

            elif args[0] in RESTRICTION_TYPES:
                sql.update_restriction(chat.id, args[0], locked=False)
                """
                members = users_sql.get_chat_members(chat.id)
                if args[0] == "messages":
                    unrestr_members(bot, chat.id, members, media=False, other=False, previews=False)

                elif args[0] == "media":
                    unrestr_members(bot, chat.id, members, other=False, previews=False)

                elif args[0] == "other":
                    unrestr_members(bot, chat.id, members, previews=False)

                elif args[0] == "previews":
                    unrestr_members(bot, chat.id, members)

                elif args[0] == "all":
                    unrestr_members(bot, chat.id, members, True, True, True, True)
                """
<<<<<<< HEAD
                message.reply_text("Unlocked {} for new members!".format(args[0]))
=======
                message.reply_text("Unlocked {} for everyone!".format(args[0]))
>>>>>>> dfe7a0e8d3284ad990b4b4dc2e3c0deaa4f85b4a

                return "<b>{}:</b>" \
                       "\n#UNLOCK" \
                       "\n<b>Admin:</b> {}" \
                       "\nUnlocked <code>{}</code>.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name), args[0])
            else:
                message.reply_text("What are you trying to unlock...? Try /locktypes for the list of lockables")

        else:
            bot.sendMessage(chat.id, "What are you trying to unlock...?")

    return ""


@run_async
@user_not_admin
def del_lockables(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]

    for lockable, filter in LOCK_TYPES.items():
        if filter(message) and sql.is_locked(chat.id, lockable) and can_delete(chat, bot.id):
            if lockable == "bots":
                new_members = update.effective_message.new_chat_members
                for new_mem in new_members:
                    if new_mem.is_bot:
                        if not is_bot_admin(chat, bot.id):
                            message.reply_text("I see a bot, and I've been told to stop them joining... "
                                               "but I'm not admin!")
                            return

                        chat.kick_member(new_mem.id)
                        message.reply_text("Only admins are allowed to add bots to this chat!")
            else:
                #allow whitelisted URLs
                if lockable == 'url':
                    entities = set(url for url in message.parse_entities(MessageEntity.URL).values())
                    #MessageEntity.TEXT_LINK could be added in the filter above, but would return the text, not the url,
                    #so add all entities that have a 'url' field instead
                    entities = entities | set(entity.url for entity in message.entities if entity.url)
                    #if all URLs are any of the whitelisted ones, accept the message
                    if all( any(regexp.search(text) for regexp in sql.get_whitelist(chat.id).values())
                            for text in entities):
                        continue
                try:
                    message.delete()
                except BadRequest as excp:
                    if excp.message == "Message to delete not found":
                        pass
                    else:
                        LOGGER.exception("ERROR in lockables")

            break

@run_async
@bot_admin
@can_restrict
def new_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    new_members = update.effective_message.new_chat_members
    restrictions = sql.get_restr(chat.id)
    for new_mem in new_members:
        # Don't restrict yourself
        if new_mem.id == bot.id:
            continue

        elif restrictions:
            bot.restrict_chat_member(chat_id=chat.id, user_id=new_mem.id,
                    can_send_messages= not restrictions.messages, can_send_media_messages= not restrictions.media,
                    can_send_other_messages= not restrictions.other, can_add_web_page_previews= not restrictions.preview,
                    until_date=0)


@run_async
@user_not_admin
def rest_handler(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    for restriction, filter in RESTRICTION_TYPES.items():
        if filter(msg) and sql.is_restr_locked(chat.id, restriction) and can_delete(chat, bot.id):
            try:
                msg.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("ERROR in restrictions")
            break


def build_lock_message(chat_id):
    locks = sql.get_locks(chat_id)
    restr = sql.get_restr(chat_id)
    if not (locks or restr):
        res = "There are no current locks in this chat."
    else:
        res = "These are the locks in this chat:"
        if locks:
            res += "\n - sticker = `{}`" \
                   "\n - audio = `{}`" \
                   "\n - voice = `{}`" \
                   "\n - document = `{}`" \
                   "\n - video = `{}`" \
                   "\n - contact = `{}`" \
                   "\n - photo = `{}`" \
                   "\n - gif = `{}`" \
                   "\n - url = `{}`" \
                   "\n - bots = `{}`" \
                   "\n - forward = `{}`" \
                   "\n - game = `{}`" \
                   "\n - location = `{}`".format(locks.sticker, locks.audio, locks.voice, locks.document,
                                                 locks.video, locks.contact, locks.photo, locks.gif, locks.url,
                                                 locks.bots, locks.forward, locks.game, locks.location)
        if restr:
            res += "\nNew member restrictions:" \
                   "\n - messages = `{}`" \
                   "\n - media = `{}`" \
                   "\n - other = `{}`" \
                   "\n - previews = `{}`".format(restr.messages, restr.media, restr.other, restr.preview)
    return res

@run_async
@user_admin
def list_locks(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    res = build_lock_message(chat.id)

    update.effective_message.reply_text(res, parse_mode=ParseMode.MARKDOWN)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return build_lock_message(chat_id)


__help__ = """
 - /locktypes: a list of possible locktypes
- /whitelisted: lists urls in this chat's whitelist

*Admin only:*
 - /lock <type>: lock items of a certain type (not available in private)
 - /unlock <type>: unlock items of a certain type (not available in private)
 - /locks: the current list of locks in this chat.
 - /whitelist <url>: add url to whitelist so it's not deleted by URL lock (accepts multiple)
 - /unwhitelist <url>: remove url from whitelist (accepts multiple)

Locks can be used to restrict a group's users.
eg:
Locking urls will auto-delete all messages with urls which haven't been whitelisted, locking stickers will delete all \
stickers, etc.
Locking bots will stop non-admins from adding bots to the chat.
Restrictions don't delete messages. Restricted members can never send them in the first place.
"""

__mod_name__ = "Locks"

LOCKTYPES_HANDLER = DisableAbleCommandHandler("locktypes", locktypes, admin_ok=True)
LOCK_HANDLER = CommandHandler("lock", lock, pass_args=True, filters=Filters.group)
UNLOCK_HANDLER = CommandHandler("unlock", unlock, pass_args=True, filters=Filters.group)
LOCKED_HANDLER = CommandHandler("locks", list_locks, filters=Filters.group)
WHITELIST_HANDLER = CommandHandler("whitelist", add_whitelist, filters=Filters.group)
UNWHITELIST_HANDLER = CommandHandler("unwhitelist", remove_whitelist, filters=Filters.group)
WHITELISTED_HANDLER = DisableAbleCommandHandler("whitelisted", list_white, filters=Filters.group, admin_ok=True)

dispatcher.add_handler(LOCK_HANDLER)
dispatcher.add_handler(UNLOCK_HANDLER)
dispatcher.add_handler(LOCKTYPES_HANDLER)
dispatcher.add_handler(LOCKED_HANDLER)
dispatcher.add_handler(WHITELIST_HANDLER)
dispatcher.add_handler(UNWHITELIST_HANDLER)
dispatcher.add_handler(WHITELISTED_HANDLER)

dispatcher.add_handler(MessageHandler(Filters.all & Filters.group, del_lockables), PERM_GROUP)
#dispatcher.add_handler(MessageHandler(Filters.all & Filters.group, rest_handler), REST_GROUP)
dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, new_member), REST_GROUP)
