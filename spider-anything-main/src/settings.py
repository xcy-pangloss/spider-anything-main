import typing as t

from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.const import ROOT_PATH


class XhsConfigs(BaseModel):
    cookie: str = Field()
    keywords: str
    login_type: t.Literal["mobile", "qrcode", "cookie"] = Field(default="cookie")

    @property
    def keywords_list(self) -> list[str]:
        return self.keywords.split(",")


class TwitterConfigs(BaseModel):
    cookie: str = Field()
    login_type: t.Literal["mobile", "qrcode", "cookie"] = Field(default="cookie")


class PgsqlConfigs(BaseModel):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str
    password: str
    db: str = Field(default="test")


class FeishuConfigs(BaseModel):
    webhook: str
    webhook_secret: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # env_prefix="lawspider_",                    # 环境变量前缀
        env_file=str(ROOT_PATH / ".env"),           # 环境变量文件名称
        env_file_encoding="utf-8",                  # 环境变量文件编码格式
        env_nested_delimiter="__",                  # 环境变量处理嵌套属性时的分隔符
        extra="ignore",                             # 忽略未定义的字段
        frozen=True,                                # 创建后禁止修改
        case_sensitive=False,                       # 大小写敏感
        coerce_numbers_to_str=False,                # 禁止将数字转换为字符串
        nested_model_default_partial_update=True,   # 嵌套属性的默认值可以被修改
    )
    test: bool = Field(default=False)
    debug: bool = Field(default=False)

    pgsql: PgsqlConfigs
    feishu: FeishuConfigs

    xhs: t.Optional[XhsConfigs] = None
    twitter: t.Optional[TwitterConfigs] = None


settings = Settings()
