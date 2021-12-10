import sys
import json
import traceback
import os
import time
import re
import random
import logging
from logging import StreamHandler
from logging.handlers import RotatingFileHandler

import requests
from furl import furl
from lxml import html
from requests.structures import CaseInsensitiveDict


DEFAULT_PROXY = 'http://localhost:7890'  # clash
DEFAULT_PROXY = 'http://localhost:8888'  # fiddler
DEFAULT_TIMEOUT = 30
DEFAULT_INTERVAL = 2
#############################################################

THIS_DIR = os.path.abspath(os.path.join(__file__, os.path.pardir))

formatter = logging.Formatter('[%(asctime)s %(levelname)s %(lineno)d]: %(message)s')
handler = RotatingFileHandler(
    filename=os.path.join(THIS_DIR, f'log.txt'),
    maxBytes=40*1024*1024,
    backupCount=1,
)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def get_tb():
    return ''.join(traceback.format_exception(*sys.exc_info()))

def dump_file_callback(filename):
    def callback(obj):
        with open(filename, 'a', encoding='utf8') as f:
            f.write(json.dumps(obj) + '\n')
    return callback


class TwitterAPI:
    query_args = {
        'include_profile_interstitial_type': '1',
        'include_blocking': '1',
        'include_blocked_by': '1',
        'include_followed_by': '1',
        'include_want_retweets': '1',
        'include_mute_edge': '1',
        'include_can_dm': '1',
        'include_can_media_tag': '1',
        'skip_status': '1',
        'cards_platform': 'Web-12',
        'include_cards': '1',
        'include_ext_alt_text': 'true',
        'include_quote_count': 'true',
        'include_reply_count': '1',
        'tweet_mode': 'extended',
        'include_entities': 'true',
        'include_user_entities': 'true',
        'include_ext_media_color': 'true',
        'include_ext_media_availability': 'true',
        'send_error_codes': 'true',
        'simple_quoted_tweet': 'true',
        'referrer': 'tweet',
        'count': '20',
        'include_ext_has_birdwatch_notes': 'false',
        'ext': 'mediaStats,highlightedLabel',
    }
    def __init__(
        self,
        timeout=DEFAULT_TIMEOUT,
        interval=DEFAULT_INTERVAL,
        proxy=DEFAULT_PROXY,  # e.g. http://localhost:7890 / None
    ) -> None:
        self.timeout = timeout
        self.interval = interval
        self.proxy = proxy
        self.sess: requests.Session = None
        self.guest_token: str = None
        self.csrf_token: str = None
        self.authorization: str = None

    def build_header(self, referer):
        return CaseInsensitiveDict({
            'authorization': self.authorization,
            'referer': referer,
            'x-guest-token': self.guest_token,
            'x-csrf-token': self.csrf_token,
            'x-twitter-active-user': 'no',
            # 'x-twitter-client-language': 'zh-cn',
            'x-twitter-client-language': 'en-us',
        })

    def init_token(self):
        sess = requests.Session()
        sess.headers = CaseInsensitiveDict({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36',
            'Accept-Encoding': ', '.join(('gzip', 'deflate')),
            'Accept': '*/*',
            'Connection': 'keep-alive',
        })
        sess.proxies =  { 'http': self.proxy, 'https': self.proxy }
        sess.verify = False

        # init personalization_id & guest_id cookies & gt & authorization
        resp = sess.get('https://twitter.com')
        # ">document.cookie = decodeURIComponent("gt=1402444682223751169; Max-Age=10800; Domain=.twitter.com; Path=/; Secure");</script
        self.guest_token = re.search('decodeURIComponent\("gt=(\d+); ', resp.text).group(1)
        sess.cookies.set('gt', self.guest_token)

        # find authorization in /responsive-web/client-web/main.41744fa5.js
        # "src="https://abs.twimg.com/responsive-web/client-web/main.ca936b25.js">"
        tree = html.fromstring(resp.text)
        node = tree.cssselect('[src*="/responsive-web/client-web/main."]')[0]
        js_link = node.attrib['src']
        resp = sess.get(js_link)

        authorization = re.search('s="(AAAAAAAA[^"]+)"', resp.text).group(1)
        self.authorization = 'Bearer ' + authorization

        # calc ct0
        rand_arr = [random.randint(0, 255) for _ in range(32)]
        rand_arr = [('%x' % v)[-1] for v in rand_arr]
        self.csrf_token = ''.join(rand_arr)
        sess.cookies.set('ct0', self.csrf_token)

        # init _twitter_sess cookie
        sess.get('https://twitter.com/i/js_inst?c_name=ui_metrics', timeout=self.timeout)

        # try to update guest token
        headers = self.build_header('https://twitter.com')
        resp = sess.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers, timeout=self.timeout)
        try:
            self.guest_token = resp.json()['guest_token']
            sess.cookies.set('gt', self.guest_token)
        except:
            logger.info('fail to update guest token %s', get_tb())
        self.sess = sess

    def search(
        self,
        contains: list=None,  # 所有这些词语，例如：有什么新鲜事 · 既包含“什么”，也包含“新鲜事”
        exact_search: str=None,  # 精确短语，可以包含空格，例如：欢乐时光 · 包含精确短语“欢乐时光”
        contains_any: list=None,  # 任何一词，例如：猫狗 · 包含“猫”或包含“狗”（或两者都包含）
        excludes: list=None,  # 排除这些词，例如：猫狗 · 不包含“猫”且不包含“狗”
        labels: list=None,  # 这些话题标签# [怀旧, 星期四]
        language=None,  # TODO:
        from_accounts: list=None,  # 来自这些账号 [elonmusk, Tesla]
        to_accounts: list=None,  # 发给这些账号 [elonmusk, Tesla]
        mention_accounts: list=None,  # 提及这些账号 [elonmusk, Tesla]
        min_replies: int=None,  # 最少回复次数
        min_faves: int=None,  # 最少喜欢次数
        min_retweets: int=None,  # 最少转推次数
        since: str=None,  # eg '2006-12-19'
        until: str=None,  # eg '2006-12-19'
        callback=None,
    ):
        '''
        q: 什么新鲜事 "欢乐时光" (猫狗) -鸡鸭 (#话题标签) (from:12 OR from:ab) (to:34 OR to:cd) (@56 OR @ef)
        q: a b "c d" (e OR f) -g -h (#aa OR #bb)
        q: min_replies:1 min_faves:2 min_retweets:3 until:2006-12-19 since:2006-11-22
        '''
        q = ''
        if contains:
            # [w1, w2] -> q: ' w1 w2'
            q += ' {%s}' % (' '.join(contains))
        if exact_search:
            # exact search -> q: ' "exact search"'
            q += f' "{exact_search}"'
        if contains_any:
            # [w1, w2] -> q: ' (w1 OR w2)'
            q += ' (%s)' % (' OR '.join(contains_any))
        if excludes:
            # [w1, w2] -> q: ' -w1 -w2'
            q += ' (%s)' % (' '.join(['-'+w for w in excludes]))
        if labels:
            # [w1, w2] -> q: ' (#w1 OR #w2)'
            q += ' (%s)' % (' OR '.join(['#'+w for w in labels]))
        if language:
            pass
        if from_accounts:
            # [w1, w2] -> q: ' (from:w1 OR from:w2)'
            q += ' (%s)' % (' OR '.join(['from:'+w for w in from_accounts]))
        if to_accounts:
            # [w1, w2] -> q: ' (to:w1 OR to:w2)'
            q += ' (%s)' % (' OR '.join(['to:'+w for w in to_accounts]))
        if mention_accounts:
            # [w1, w2] -> q: ' (@w1 OR @w2)'
            q += ' (%s)' % (' OR '.join(['@'+w for w in mention_accounts]))
        if min_replies:
            # w1 -> q: ' min_replies:w1'
            q += f' min_replies:{min_replies}'
        if min_faves:
            # w1 -> q: ' min_faves:w1'
            q += f' min_faves:{min_faves}'
        if min_retweets:
            # w1 -> q: ' min_retweets:w1'
            q += f' min_retweets:{min_retweets}'
        if since:
            # since:2006-11-22
            q += f' since:{since}'
        if until:
            # until:2006-11-22
            q += f' until:{until}'
        q = q.strip()

        base_url = 'https://twitter.com/i/api/2/search/adaptive.json'
        cursor = None
        while True:
            try:
                f = furl(base_url)
                f.args = self.query_args
                f.args['q'] = q
                if cursor:
                    f.args['cursor'] = cursor
                headers = self.build_header('https://twitter.com/search')
                resp = self.sess.get(f.url, headers=headers, timeout=self.timeout)

                json_data = resp.json()
                users: dict = json_data['globalObjects']['users']
                tweets: dict = json_data['globalObjects']['tweets']
                try:
                    callback({'users': users, 'tweets': tweets})
                except:
                    logger.info('fail to exec callback %s', get_tb())

                try:
                    # turn page
                    cursor: str = json_data['timeline']['instructions'][0]['addEntries']['entries'][-1]['content']['operation']['cursor']['value']
                    time.sleep(self.interval)
                except:
                    # this is the last page
                    logger.info('last page reached')
                    break
            except:
                logger.info('fail to fetch ajax %s', get_tb())
                break
        logger.info('fetch done')

    def crawl_post(self, post_url, callback):
        post_id = re.search('/status/([^/?]+)', post_url).group(1)
        cursor = ''
        base_url = 'https://twitter.com/i/api/2/timeline/conversation/{pid}.json'
        base_url = base_url.replace('{pid}', post_id)
        while True:
            try:
                f = furl(base_url)
                f.args = self.query_args
                if cursor:
                    f.args['cursor'] = cursor
                headers = self.build_header(post_url)
                resp = self.sess.get(f.url, headers=headers, timeout=self.timeout)

                json_data = resp.json()
                users: dict = json_data['globalObjects']['users']
                tweets: dict = json_data['globalObjects']['tweets']
                try:
                    callback({'users': users, 'tweets': tweets})
                except:
                    logger.info('fail to exec callback %s', get_tb())

                try:
                    # turn page
                    cursor: str = json_data['timeline']['instructions'][0]['addEntries']['entries'][-1]['content']['operation']['cursor']['value']
                    time.sleep(self.interval)
                except:
                    # this is the last page
                    logger.info('last page reached')
                    break
            except:
                logger.info('fail to fetch ajax %s', get_tb())
                break
        logger.info('fetch done')


def test_search():
    api = TwitterAPI()
    api.init_token()
    api.search(
        from_accounts=['HazelCurry2000'],
        min_replies=1,
        callback=dump_file_callback('search.txt'),
    )

def process_search_result():
    with open('search.txt', 'r', encoding='utf8') as f:
        lines = f.read().splitlines()

    post_urls = []
    for line in lines:
        data: dict = json.loads(line)

        users: dict = data['users']
        user_dict = dict()  # uid -> screen_name
        for uid, user in users.items():
            user_dict[uid] = user['screen_name']

        tweets: dict = data['tweets']
        for tid, tweet in tweets.items():
            uid = tweet['user_id_str']
            user_screen_name = user_dict[uid]
            post_url = f'https://twitter.com/{user_screen_name}/status/{tid}'
            post_urls.append(post_url)

    with open('post_urls.txt', 'w', encoding='utf8') as f:
        f.write('\n'.join(post_urls))

def test_crawl_post():
    with open('post_urls.txt', 'r', encoding='utf8') as f:
        urls = f.read().splitlines()

    for url in urls:
        try:
            api = TwitterAPI()
            api.init_token()
            api.crawl_post(url, dump_file_callback('post.txt'))
            time.sleep(DEFAULT_INTERVAL)
        except:
            logger.info('fail to exec %s', get_tb())

def process_post_result():
    with open('post.txt', 'r', encoding='utf8') as f:
        lines = f.read().splitlines()

    user_dict = dict()
    for line in lines:
        data: dict = json.loads(line)
        users: dict = data['users']
        for uid, user in users.items():
            user_dict[uid] = user['screen_name']

    post_dict = dict()
    for line in lines:
        data: dict = json.loads(line)
        tweets: dict = data['tweets']
        for tid, tweet in tweets.items():
            user_id = tweet['user_id_str']
            user_name = user_dict[user_id]
            try:
                image_url = tweet['entities']['media'][0]['media_url']
            except:
                image_url = ''

            post_dict[tid] = {
                'url': f'https://twitter.com/{user_name}/status/{tid}',
                'image_url': image_url,
                'reply_count': tweet['reply_count'],
            }

    rv = []
    for line in lines:
        data: dict = json.loads(line)
        tweets: dict = data['tweets']
        for tid, tweet in tweets.items():
            user_id = tweet['user_id_str']
            conv_id = tweet['conversation_id_str']
            text = tweet['full_text']
            create_at = tweet['created_at']
            conv = post_dict.get(conv_id, {})
            try:
                image_url = tweet['entities']['media'][0]['media_url']
            except:
                image_url = ''

            user_name = user_dict[user_id]
            out = [
                user_name,
                create_at,
                text.replace('\n', ' ').replace('\t', ' ').strip(),
                image_url,
                conv.get('url', ''),
                conv.get('image_url', ''),
                conv.get('reply_count', ''),
            ]
            out = '\t'.join(list(map(str, out)))
            rv.append(out)
    with open('out.txt', 'w', encoding='utf8') as f:
        f.write('\n'.join(rv))

if __name__ == '__main__':
    test_search()
    process_search_result()
    test_crawl_post()
    process_post_result()
