# twitter_crawler
crawl twitter via reverse engineering without using twitter token

## Usage

search
```python
api = TwitterAPI()
api.init_token()
api.search(
    from_accounts=['elonmusk'],
    min_replies=1,
    callback=dump_file_callback('search.txt'),
)
"""
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
    pass
"""
```

crawl post
```python
api = TwitterAPI()
api.init_token()
api.crawl_post(url, dump_file_callback('post.txt'))
```
