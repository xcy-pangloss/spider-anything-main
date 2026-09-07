import time as pytime
import typing as t
from enum import Enum

from pydantic import BaseModel, Field


XHSNoteType = t.Literal["normal", "video"]


class XhsNoteSortType(Enum):
    auto = 0
    new = 1
    more_like = 2
    more_comment = 3
    more_collect = 4


class XhsNoteType(Enum):
    normal = 0
    video = 1
    image = 2


class XhsNoteTimeType(Enum):
    normal = 0
    one_day = 1
    one_week = 2
    half_year = 3


class XhsNoteSearchScopeType(Enum):
    normal = 0
    viewed = 1
    not_viewed = 2
    subscribed = 3


class XhsLocationType(Enum):
    normal = 0
    city = 1
    nearby = 2


class XhsSearchParams(BaseModel):
    sort_type: XhsNoteSortType = Field(default=XhsNoteSortType.auto, description="排序类型")
    note_type: XhsNoteType = Field(default=XhsNoteType.normal, description="笔记类型")
    note_time_type: XhsNoteTimeType = Field(default=XhsNoteTimeType.normal, description="笔记时间类型")
    search_scope_type: XhsNoteSearchScopeType = Field(default=XhsNoteSearchScopeType.normal, description="搜索范围类型")
    location_type: XhsLocationType = Field(default=XhsLocationType.normal, description="位置类型")

    @property
    def format_params(self) -> str:
        return f"排序类型:{self.sort_type.name},笔记类型:{self.note_type.name},笔记时间类型:{self.note_time_type.name},搜索范围类型:{self.search_scope_type.name},位置类型:{self.location_type.name}"


class XhsNote(BaseModel):
    """ 小红书笔记模型 """
    id: t.Optional[int]                 = Field(None, description="自增ID")
    note_id: str                        = Field(..., description="笔记唯一 ID")
    note_url: str                       = Field(..., description="笔记 URL")
    type: t.Optional[XHSNoteType]       = Field(None, description="笔记类型(normal | video)")
    desc: t.Optional[str]               = Field("", description="笔记描述")
    title: t.Optional[str]              = Field("", description="笔记标题")
    tag_list: t.Optional[str]           = Field(None, description="标签列表")
    video_url: t.Optional[str]          = Field(None, description="视频地址")
    image_list: t.Optional[str]         = Field(None, description="笔记封面图片列表")
    avatar: t.Optional[str]             = Field(None, description="用户头像地址")
    user_id: t.Optional[str]            = Field(None, description="用户ID")
    nickname: t.Optional[str]           = Field(None, description="用户昵称")
    ip_location: t.Optional[str]        = Field(None, description="评论时的IP地址")
    liked_count: t.Optional[str]        = Field("0", description="笔记点赞数")
    share_count: t.Optional[str]        = Field("0", description="笔记分享数")
    comment_count: t.Optional[str]      = Field("0", description="笔记评论数")
    collected_count: t.Optional[str]    = Field("0", description="笔记收藏数")
    xsec_token: t.Optional[str]         = Field(None, description="xsec_token")
    source_keyword: t.Optional[str]     = Field(None, description="搜索关键词")

    time: int                           = Field(..., description="笔记发布时间戳")
    last_update_time: t.Optional[int]   = Field(None, description="笔记最后更新时间戳")

    add_ts: t.Optional[int]             = Field(int(pytime.time() * 1000), description="获取时间戳")
    last_modify_ts: t.Optional[int]     = Field(int(pytime.time() * 1000), description="最后修改时间戳")

    extra: t.Any                        = Field(default=dict(), description="额外信息")

    @property
    def tags(self) -> list[str]:
        if not self.tag_list:
            return []
        return self.tag_list.split(",")

    @property
    def videos(self) -> list[str]:
        if not self.video_url:
            return []
        return self.video_url.split(",")

    @property
    def images(self) -> list[str]:
        if not self.image_list:
            return []
        return self.image_list.split(",")
    
    def model_dump(self, *args, **kwargs):
        return super().model_dump(exclude_none=True, *args, **kwargs)


class XhsNoteComment(BaseModel):
    """小红书笔记评论模型"""
    id: t.Optional[int]                 = Field(None, description="自增ID")
    note_id: str                        = Field(..., description="笔记唯一 ID")
    comment_id: str                     = Field(..., description="评论唯一 ID")
    parent_comment_id: t.Optional[str]  = Field(None, description="父评论唯一 ID")
    content: t.Optional[str]            = Field(None, description="评论内容")
    picture_list: t.Optional[str]       = Field(None, description="评论图片")
    avatar: t.Optional[str]             = Field(None, description="用户头像地址")
    user_id: t.Optional[str]            = Field(None, description="用户ID")
    nickname: t.Optional[str]           = Field(None, description="用户昵称")
    ip_location: t.Optional[str]        = Field(None, description="IP 所在地")
    like_count: t.Optional[str]         = Field("0", description="点赞数")
    sub_comment_count: t.Optional[str]  = Field("0", description="子评论数量")

    create_time: t.Optional[int]        = Field(..., description="评论时间戳")

    add_ts: t.Optional[int]             = Field(int(pytime.time() * 1000), description="获取时间戳")
    last_modify_ts: t.Optional[int]     = Field(int(pytime.time() * 1000), description="最后修改时间戳")

    extra: t.Any                        = Field(default=dict(), description="额外信息")

    @property
    def pictures(self) -> list[str]:
        if not self.picture_list:
            return []
        return self.picture_list.split(",")

    def model_dump(self, *args, **kwargs):
        return super().model_dump(exclude_none=True, *args, **kwargs)
