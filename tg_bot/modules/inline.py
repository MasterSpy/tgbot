import json
import urllib.request

from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import InlineQueryHandler
from tg_bot import dispatcher
from tg_bot.config import Development as Config
from telegram.utils.helpers import escape_markdown

FRESHDESK_URL = Config.FRESHDESK_URL
SEARCH_URL = FRESHDESK_URL+'/support/search/solutions.json?term='
ARTICLE_URL = FRESHDESK_URL+'/api/v2/solutions/articles/'

#check if freshdesk link is valid
try:
    urllib.request.urlopen(SEARCH_URL)
except urllib.error.URLError as e:
    raise Exception('Your FRESHDESK_URL variable is not valid: '+str(e))
except:
    raise Exception('config.py must have valid FRESHDESK_URL value for the "fresh_inline" module to work')

def inline_search(bot, update):
    query = update.inline_query.query
    
    if not query:
        bot.answer_inline_query(update.inline_query.id, [])
        return
    
    with urllib.request.urlopen(SEARCH_URL+query.replace(' ', '%20')) as response:
        results = json.loads(response.read())
    
    if len(results) > 50:
        results = results [:49]
    
    results = [InlineQueryResultArticle(
                    id = article['source']['article']['id'],
                    title = article['source']['article']['title'],
                    input_message_content = InputTextMessageContent(
                            message_text = '[{}]({})'.format(
                                    escape_markdown(article['source']['article']['title']),
                                    FRESHDESK_URL+article['url']
                                ),
                            parse_mode = 'Markdown',
                            disable_web_page_preview = True
                        ),
                    description = article['source']['article']['desc_un_html'][:80]+'...'
                ) for article in results]
    
    bot.answer_inline_query(update.inline_query.id, results)

inline_handler = InlineQueryHandler(inline_search)
dispatcher.add_handler(inline_handler)