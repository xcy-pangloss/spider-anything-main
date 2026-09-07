import time as pytime

from tortoise import fields, Model


class XhsNotes(Model):
    id = fields.BigIntField(pk=True, description="笔记计数 ID")
    note_id = fields.CharField(max_length=255, unique=True, db_index=True, description="笔记唯一 ID")
    note_url = fields.TextField(description="笔记 URL")
    type = fields.CharField(max_length=50, null=True, description="笔记类型")
    desc = fields.TextField(default="", description="笔记内容")
    title = fields.CharField(default="", max_length=1024, description="笔记标题")
    tag_list = fields.TextField(null=True)
    video_url = fields.TextField(null=True)
    image_list = fields.TextField(null=True)
    avatar = fields.CharField(max_length=500, null=True, description="用户头像")
    user_id = fields.CharField(max_length=255, null=True, db_index=True, description="用户 ID")
    nickname = fields.CharField(max_length=255, null=True, description="用户昵称")
    ip_location = fields.CharField(max_length=100, null=True, description="IP 所在地")
    liked_count = fields.CharField(default="0", max_length=50, description="点赞数")
    share_count = fields.CharField(default="0", max_length=50, description="分享数")
    comment_count = fields.CharField(default="0", max_length=50, description="评论数")
    collected_count = fields.CharField(default="0", max_length=50, description="收藏数")
    xsec_token = fields.CharField(max_length=255)
    source_keyword = fields.CharField(max_length=255, null=True)
    time = fields.BigIntField(description="笔记发布时间")
    last_update_time = fields.BigIntField(null=True, description="笔记发布时间")

    add_ts = fields.BigIntField(default=int(pytime.time() * 1000), description="获取时间戳")
    last_modify_ts = fields.BigIntField(default=int(pytime.time() * 1000), description="最后修改时间戳")

    extra = fields.JSONField(default={}, description="额外信息")

    class Meta:
        table = "xhs_notes"


class XhsNoteComments(Model):
    id = fields.BigIntField(pk=True, description="评论计数 ID")
    note_id = fields.CharField(max_length=255, db_index=True, description="笔记唯一 ID")
    comment_id = fields.CharField(max_length=255, unique=True, db_index=True, description="评论唯一 ID")
    parent_comment_id = fields.CharField(max_length=255, null=True, db_index=True, description="父评论唯一 ID")
    content = fields.TextField(null=True, description="评论内容")
    picture_list = fields.TextField(null=True, description="评论图片")
    avatar = fields.CharField(max_length=500, null=True, description="用户头像")
    user_id = fields.CharField(max_length=255, null=True, db_index=True, description="用户唯一 ID")
    nickname = fields.CharField(max_length=255, null=True, description="用户昵称")
    ip_location = fields.CharField(max_length=100, null=True, description="IP 所在地")
    like_count = fields.CharField(default="0", max_length=50, description="点赞数")
    sub_comment_count = fields.CharField(default="0", max_length=50, description="子评论数")
    
    create_time = fields.BigIntField(description="评论发布时间")
    
    add_ts = fields.BigIntField(default=int(pytime.time() * 1000), description="获取时间戳")
    last_modify_ts = fields.BigIntField(default=int(pytime.time() * 1000), description="最后修改时间戳")
    
    extra = fields.JSONField(default={}, description="额外信息")

    class Meta:
        table = "xhs_note_comments"