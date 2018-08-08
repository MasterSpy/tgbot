import json
import urllib.request
import re

from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import InlineQueryHandler, ChosenInlineResultHandler, Handler
from telegram.ext.dispatcher import run_async
from tg_bot import dispatcher
from tg_bot.config import Development as Config
from tg_bot.modules.sql import inline_sql as sql

FRESHDESK_URL = Config.FRESHDESK_URL
SEARCH_URL = FRESHDESK_URL+'/support/search/solutions.json?term='
ARTICLE_URL = FRESHDESK_URL+'/support/solutions/articles/'
ARTICLE_ID_REGEXP = re.compile(r'\/(\d+)-')

#check if freshdesk link is valid
try:
    urllib.request.urlopen(SEARCH_URL)
except urllib.error.URLError as e:
    raise Exception('Your FRESHDESK_URL variable is not valid: '+str(e))
except:
    raise Exception('config.py must have valid FRESHDESK_URL value for the "fresh_inline" module to work')


def escape_HTML(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


@run_async
def inline_search(bot, update):
    query = update.inline_query.query
    
    if not query:
        bot.answer_inline_query(update.inline_query.id, [InlineQueryResultArticle(
                                                                id = article.article_id,
                                                                title = i+1,
                                                                description = article.title,
                                                                input_message_content = InputTextMessageContent(
                                                                        message_text = 'FAQ page: <a href="{}">{}</a>'.format(
                                                                                ARTICLE_URL+str(article.article_id),
                                                                                escape_HTML(article.title)
                                                                            ),
                                                                        parse_mode = 'HTML',
                                                                        disable_web_page_preview = True
                                                                    ),
                                                                )
                                                         for i, article in enumerate(sql.get_top_searches())],
                                )
        return
    
    with urllib.request.urlopen(SEARCH_URL+query.replace(' ', '%20')) as response:
        results = json.loads(response.read())
    
    if len(results) > 50:
        results = results [:49]
    
    results = [InlineQueryResultArticle(
                    id = ARTICLE_ID_REGEXP.search(article['url']).group(1),
                    title = article['source']['article']['title'],
                    input_message_content = InputTextMessageContent(
                            message_text = 'FAQ page: <a href="{}">{}</a>'.format(
                                    FRESHDESK_URL+article['url'],
                                    escape_HTML(article['source']['article']['title'])
                                ),
                            parse_mode = 'HTML',
                            disable_web_page_preview = True
                        ),
                    description = article['source']['article']['desc_un_html'][:80]+'...'
                ) for article in results]
    
    bot.answer_inline_query(update.inline_query.id, results)


@run_async
def chosen_result(bot, update):
    result_id = update.chosen_inline_result.result_id
    with urllib.request.urlopen(ARTICLE_URL+result_id+'.json') as response:
        article = json.loads(response.read())
    sql.increment(result_id, article['article']['title'])


INLINE_HANDLER = InlineQueryHandler(inline_search)
CHOSEN_HANDLER = ChosenInlineResultHandler(chosen_result)
dispatcher.add_handler(INLINE_HANDLER)
dispatcher.add_handler(CHOSEN_HANDLER, -1)
