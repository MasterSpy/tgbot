import threading

from sqlalchemy import Column, BigInteger, Integer, UnicodeText

from tg_bot.modules.sql import SESSION, BASE


class TopSearches(BASE):
    __tablename__ = "inline_top"
    article_id = Column(BigInteger, primary_key=True)
    hits = Column(Integer, default=0)
    title = Column(UnicodeText, nullable=False)

    def __init__(self, article_id, title):
        self.article_id = int(article_id)
        self.hits = 0
        self.game = False

    def __repr__(self):
        return "<Hits and title of article %s>" % self.article_id


TopSearches.__table__.create(checkfirst=True)


SEARCHES_LOCK = threading.RLock()

def increment(article_id, title):
    article_id = int(article_id) # ensure int
    
    with SEARCHES_LOCK:
        article = SESSION.query(TopSearches).get(article_id)
        if not article:
            article = TopSearches(article_id, title)

        article.hits = article.hits + 1
        article.title = title
        SESSION.add(article)
        SESSION.commit()


def get_top_searches():
    try:
        return SESSION.query(TopSearches).order_by(TopSearches.hits.desc()).limit(10).all()
    finally:
        SESSION.close()