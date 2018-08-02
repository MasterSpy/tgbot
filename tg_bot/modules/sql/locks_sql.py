# New chat added -> setup permissions
import threading
import re

from sqlalchemy import Column, String, Boolean, UnicodeText

from tg_bot.modules.sql import SESSION, BASE


class Permissions(BASE):
    __tablename__ = "permissions"
    chat_id = Column(String(14), primary_key=True)
    # Booleans are for "is this locked", _NOT_ "is this allowed"
    audio = Column(Boolean, default=False)
    voice = Column(Boolean, default=False)
    contact = Column(Boolean, default=False)
    video = Column(Boolean, default=False)
    document = Column(Boolean, default=False)
    photo = Column(Boolean, default=False)
    sticker = Column(Boolean, default=False)
    gif = Column(Boolean, default=False)
    url = Column(Boolean, default=False)
    bots = Column(Boolean, default=False)
    forward = Column(Boolean, default=False)
    game = Column(Boolean, default=False)
    location = Column(Boolean, default=False)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)  # ensure string
        self.audio = False
        self.voice = False
        self.contact = False
        self.video = False
        self.document = False
        self.photo = False
        self.sticker = False
        self.gif = False
        self.url = False
        self.bots = False
        self.forward = False
        self.game = False
        self.location = False

    def __repr__(self):
        return "<Permissions for %s>" % self.chat_id


class Restrictions(BASE):
    __tablename__ = "restrictions"
    chat_id = Column(String(14), primary_key=True)
    # Booleans are for "is this restricted", _NOT_ "is this allowed"
    messages = Column(Boolean, default=False)
    media = Column(Boolean, default=False)
    other = Column(Boolean, default=False)
    preview = Column(Boolean, default=False)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)  # ensure string
        self.messages = False
        self.media = False
        self.other = False
        self.preview = False

    def __repr__(self):
        return "<Restrictions for %s>" % self.chat_id

class URLWhitelist(BASE):
    __tablename__ = "permissions_urls"
    chat_id = Column(String(14), primary_key=True, nullable=False)
    url = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, chat_id, url):
        self.chat_id = str(chat_id)  # ensure string
        self.url = url

    def __repr__(self):
        return "<Permission url whitelist for %s>" % self.chat_id

Permissions.__table__.create(checkfirst=True)
Restrictions.__table__.create(checkfirst=True)
URLWhitelist.__table__.create(checkfirst=True)


PERM_LOCK = threading.RLock()
RESTR_LOCK = threading.RLock()
WHITELIST_LOCK = threading.RLock()
CHAT_WHITELIST = {}


def init_permissions(chat_id, reset=False):
    curr_perm = SESSION.query(Permissions).get(str(chat_id))
    if reset:
        SESSION.delete(curr_perm)
        SESSION.flush()
    perm = Permissions(str(chat_id))
    SESSION.add(perm)
    SESSION.commit()
    return perm


def init_restrictions(chat_id, reset=False):
    curr_restr = SESSION.query(Restrictions).get(str(chat_id))
    if reset:
        SESSION.delete(curr_restr)
        SESSION.flush()
    restr = Restrictions(str(chat_id))
    SESSION.add(restr)
    SESSION.commit()
    return restr

def update_lock(chat_id, lock_type, locked):
    with PERM_LOCK:
        curr_perm = SESSION.query(Permissions).get(str(chat_id))
        if not curr_perm:
            curr_perm = init_permissions(chat_id)

        if lock_type == "audio":
            curr_perm.audio = locked
        elif lock_type == "voice":
            curr_perm.voice = locked
        elif lock_type == "contact":
            curr_perm.contact = locked
        elif lock_type == "video":
            curr_perm.video = locked
        elif lock_type == "document":
            curr_perm.document = locked
        elif lock_type == "photo":
            curr_perm.photo = locked
        elif lock_type == "sticker":
            curr_perm.sticker = locked
        elif lock_type == "gif":
            curr_perm.gif = locked
        elif lock_type == 'url':
            curr_perm.url = locked
        elif lock_type == 'bots':
            curr_perm.bots = locked
        elif lock_type == 'forward':
            curr_perm.forward = locked
        elif lock_type == 'game':
            curr_perm.game = locked
        elif lock_type == 'location':
            curr_perm.location = locked

        SESSION.add(curr_perm)
        SESSION.commit()


def update_restriction(chat_id, restr_type, locked):
    with RESTR_LOCK:
        curr_restr = SESSION.query(Restrictions).get(str(chat_id))
        if not curr_restr:
            curr_restr = init_restrictions(chat_id)

        if restr_type == "messages":
            curr_restr.messages = locked
            if locked:
                curr_restr.media = locked
                curr_restr.other = locked
                curr_restr.preview = locked
        elif restr_type == "media":
            curr_restr.media = locked
            if locked:
                curr_restr.other = locked
                curr_restr.preview = locked
            else:
                curr_restr.messages = locked
        elif restr_type == "other":
            curr_restr.other = locked
            if not locked:
                curr_restr.messages = locked
                curr_restr.media = locked
        elif restr_type == "previews":
            curr_restr.preview = locked
            if not locked:
                curr_restr.messages = locked
                curr_restr.media = locked
        elif restr_type == "all":
            curr_restr.messages = locked
            curr_restr.media = locked
            curr_restr.other = locked
            curr_restr.preview = locked
        SESSION.add(curr_restr)
        SESSION.commit()


def is_locked(chat_id, lock_type):
    curr_perm = SESSION.query(Permissions).get(str(chat_id))
    SESSION.close()

    if not curr_perm:
        return False

    elif lock_type == "sticker":
        return curr_perm.sticker
    elif lock_type == "photo":
        return curr_perm.photo
    elif lock_type == "audio":
        return curr_perm.audio
    elif lock_type == "voice":
        return curr_perm.voice
    elif lock_type == "contact":
        return curr_perm.contact
    elif lock_type == "video":
        return curr_perm.video
    elif lock_type == "document":
        return curr_perm.document
    elif lock_type == "gif":
        return curr_perm.gif
    elif lock_type == "url":
        return curr_perm.url
    elif lock_type == "bots":
        return curr_perm.bots
    elif lock_type == "forward":
        return curr_perm.forward
    elif lock_type == "game":
        return curr_perm.game
    elif lock_type == "location":
        return curr_perm.location


def is_restr_locked(chat_id, lock_type):
    curr_restr = SESSION.query(Restrictions).get(str(chat_id))
    SESSION.close()

    if not curr_restr:
        return False

    if lock_type == "messages":
        return curr_restr.messages
    elif lock_type == "media":
        return curr_restr.media
    elif lock_type == "other":
        return curr_restr.other
    elif lock_type == "previews":
        return curr_restr.preview
    elif lock_type == "all":
        return curr_restr.messages and curr_restr.media and curr_restr.other and curr_restr.preview


def get_locks(chat_id):
    try:
        return SESSION.query(Permissions).get(str(chat_id))
    finally:
        SESSION.close()


def get_restr(chat_id):
    try:
        return SESSION.query(Restrictions).get(str(chat_id))
    finally:
        SESSION.close()


def get_whitelist(chat_id):
    #todo sort
    return CHAT_WHITELIST.get(str(chat_id), {})


def add_whitelist(chat_id, url):
    global CHAT_WHITELIST
    with WHITELIST_LOCK:
        url = url.lower()
        prev = SESSION.query(URLWhitelist).get((str(chat_id), url))
        if not prev:
            whitelisted = URLWhitelist(str(chat_id), url)
            SESSION.add(whitelisted)
            SESSION.commit()
        chat_whitelist = CHAT_WHITELIST.setdefault(str(chat_id), {})
        chat_whitelist.update({url: re.compile(r'(^http:\/\/|^https:\/\/|^ftp:\/\/|^)(www\.)?('+url+')($|\W.*)',
                                                flags=re.I)})


def remove_whitelist(chat_id, url):
    global CHAT_WHITELIST
    with WHITELIST_LOCK:
        url = url.lower()
        CHAT_WHITELIST.get(str(chat_id), {}).pop(url, None)
        white = SESSION.query(URLWhitelist).get((str(chat_id), url))
        if white:
            SESSION.delete(white)
            SESSION.commit()
            return True

        SESSION.close()
        return False


def __load_chat_whitelist():
    #whitelist for each group is a dict(url: compiled_regexp for url in group)
    global CHAT_WHITELIST
    try:
        chats = SESSION.query(URLWhitelist.chat_id).distinct().all()
        for (chat_id,) in chats:  # remove tuple by ( ,)
            CHAT_WHITELIST[str(chat_id)] = {}

        all_whites = SESSION.query(URLWhitelist).all()
        for x in all_whites:
            CHAT_WHITELIST[str(x.chat_id)].update({x.url: re.compile(r'(^http:\/\/|^https:\/\/|^ftp:\/\/|^)(www\.)?('+x.url+')', flags=re.I)})
    finally:
        SESSION.close()

def migrate_chat(old_chat_id, new_chat_id):
    with PERM_LOCK:
        perms = SESSION.query(Permissions).get(str(old_chat_id))
        if perms:
            perms.chat_id = str(new_chat_id)
        SESSION.commit()

    with RESTR_LOCK:
        rest = SESSION.query(Restrictions).get(str(old_chat_id))
        if rest:
            rest.chat_id = str(new_chat_id)
        SESSION.commit()
    
    with WHITELIST_LOCK:
        white = SESSION.query(URLWhitelist).filter(URLWhitelist.chat_id == str(old_chat_id)).all()
        for word in white:
            word.chat_id = str(new_chat_id)
        SESSION.commit()

__load_chat_whitelist()