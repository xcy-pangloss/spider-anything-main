import time as pytime

from tortoise import fields, Model


class TwitterSearchResult(Model):
    keyword = fields.CharField(max_length=255)
    url = fields.TextField(null=False)
    url_with_params = fields.TextField(null=False)
    content = fields.TextField()

    updated_at = fields.BigIntField(default=int(pytime.time() * 1000))
    obtained_at = fields.BigIntField(default=int(pytime.time() * 1000))

    class Meta:
        table = "twitter_search_result"


class TwitterUser(Model):
    id = fields.CharField(pk=True, max_length=255)
    avatar = fields.CharField(max_length=500)
    username = fields.CharField(max_length=255)
    screen_name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    location = fields.CharField(max_length=255, null=True)
    favourites_count = fields.BigIntField(default=0)
    followers_count = fields.BigIntField(default=0)
    friends_count = fields.BigIntField(default=0)
    statuses_count = fields.BigIntField(default=0)
    content = fields.JSONField(default=dict())
    created_at = fields.BigIntField(null=True)
    history = fields.JSONField(default=list())

    updated_at = fields.BigIntField(default=int(pytime.time() * 1000))
    obtained_at = fields.BigIntField(default=int(pytime.time() * 1000))

    class Meta:
        table = "twitter_user"


class TwitterTweet(Model):
    id = fields.CharField(pk=True, max_length=255)
    quote_id = fields.CharField(max_length=255, null=True)
    parent_id = fields.CharField(max_length=255, null=True)
    user_id = fields.CharField(max_length=255)
    url = fields.TextField(null=False)
    full_text = fields.TextField()
    lang = fields.CharField(default="zh", index=True, max_length=10)
    quote_count = fields.BigIntField(default=0)
    reply_count = fields.BigIntField(default=0)
    retweet_count = fields.BigIntField(default=0)
    favorite_count = fields.BigIntField(default=0)
    bookmark_count = fields.BigIntField(default=0)
    with_media = fields.BooleanField(default=False)
    content = fields.JSONField(default=dict())
    keyword = fields.CharField(max_length=255)
    created_at = fields.BigIntField(null=True)

    updated_at = fields.BigIntField(default=int(pytime.time() * 1000))
    obtained_at = fields.BigIntField(default=int(pytime.time() * 1000))

    class Meta:
        table = "twitter_tweet"


class TwitterMedia(Model):
    id = fields.CharField(max_length=255, pk=True)
    sha256 = fields.CharField(max_length=255)
    source_id = fields.CharField(max_length=255)
    source_type = fields.CharField(max_length=255)
    download_url = fields.CharField(max_length=500, null=True)
    type = fields.CharField(max_length=255, null=True)
    content = fields.JSONField(default=dict())

    updated_at = fields.BigIntField(default=int(pytime.time() * 1000))
    obtained_at = fields.BigIntField(default=int(pytime.time() * 1000))

    class Meta:
        table = "twitter_media"


class TwitterConversation(Model):
    id = fields.CharField(pk=True, max_length=255)
    tweet_id = fields.CharField(max_length=255)
    quote_id = fields.CharField(max_length=255, null=True)
    parent_id = fields.CharField(max_length=255, null=True)
    user_id = fields.CharField(max_length=255)
    url = fields.TextField(null=False)
    full_text = fields.TextField()
    lang = fields.CharField(default="zh", index=True, max_length=10)
    quote_count = fields.BigIntField(default=0)
    reply_count = fields.BigIntField(default=0)
    retweet_count = fields.BigIntField(default=0)
    favorite_count = fields.BigIntField(default=0)
    bookmark_count = fields.BigIntField(default=0)
    content = fields.JSONField(default=dict())
    with_media = fields.BooleanField(default=False)
    keyword = fields.CharField(max_length=255)
    created_at = fields.BigIntField(null=True)

    updated_at = fields.BigIntField(default=int(pytime.time() * 1000))
    obtained_at = fields.BigIntField(default=int(pytime.time() * 1000))

    class Meta:
        table = "twitter_conversation"


class TwitterDetailResult(Model):
    url = fields.TextField(null=False)
    url_with_params = fields.TextField(null=False)
    tweet_id = fields.CharField(max_length=255)
    content = fields.TextField()

    updated_at = fields.BigIntField(default=int(pytime.time() * 1000))
    obtained_at = fields.BigIntField(default=int(pytime.time() * 1000))

    class Meta:
        table = "twitter_detail_result"