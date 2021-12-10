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
```

crawl post
```python
api = TwitterAPI()
api.init_token()
api.crawl_post(url, dump_file_callback('post.txt'))
```
