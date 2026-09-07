import random
import asyncio

from src.const import ROOT_PATH
from src.handler.xhs import XhsHandler
from src.core.browser import Browser
from src.schema.xhs import XhsSearchParams
from src.schema.xhs import XhsNoteSortType
from src.schema.xhs import XhsNoteType
from src.schema.xhs import XhsLocationType
from src.schema.xhs import XhsNoteTimeType
from src.schema.xhs import XhsNoteSearchScopeType


keywords = [
    '好物分享', '电话', '付邮送', '养号', '震惊', '竟然', '却', '打架', '屁',
    '土嗨', '点赞', '好孕', '送花', '电影', '科普', '无声', '微信', '免费送',
    '副业', '爆料', '居然', '斗殴', '月经', '斗罗', '关注', '菩萨', '能量', '电视',
    '游戏', '小技巧', '绿色泡泡', 'fys', '无货源开店', '马云', '结果', '家暴', '放屁',
    '唐三', '评论', '祈福', '上岸', '影视剧', '社会知识', '冷知识', 'vx', '众筹', '起号',
    '许家印', '打戏', '黑头', '小舞', '转发', '发财', '考试', '综艺', '占卜', '心灵鸡汤',
    'qq', '救助', '标题', '千万不要', '穿刺', '粉刺', '比比东', '资料', '财神', '通过',
    '营销号', '塔罗', '故事', '手机号', '薅羊毛', '爆款', '胃镜', '闭口', '樱花校园',
    '滴滴', '佛言佛语', '交友dd', '小说', '11位数字', '医疗', '洗稿', '采耳', '痘痘',
    '奥特曼', '扣佛像', '扩列', '背景', '医美', 'ai', '掏耳', '白头', '恐怖', '下面',
    '保护', '扩圈', '主页', '兼职', 'AI', '耳洞', '头皮屑', '悬疑', '回复', '狗头',
    '找关系', '头像', '领养', 'Ai', '针灸', '苍蝇', '万圣节', '锦鲤', '福气', '星座', '签名',
    '交友', '模板', '打针', '蛇', '密室', '特效', '关猪', '惊喜', '神秘数字', '酒吧',
    '变现', '生产', '蜈蚣', '解密', '祈愿', '祝福', '悬念', '小红书号', '蹦迪',
    '刷量', '妊娠纹', '老鼠', '异宠', '正能量', '预测', '玄学', 'pm', '投资', '技巧',
    '伤疤', '蟑螂', '猫砂', '关注注', '置顶', '攻略', '短剧', '洗纹身', '蜥蜴', '呕吐',
    '顶置', '互勉', '剧情', '藤壶', '寄生虫', '喊麦', '二维码', '听歌养肝', '模仿', '莲蓬',
    '整蛊', '广场舞', '链接', '刷到', '原创剧情', '蜂巢', '疯癫', '双眼皮', '小程序',
    '玄学', '博眼球', '医院', '增高', '谣言', '克星', '节奏盒子', '花蝴蝶', 'ct', '丰胸',
    '考研', '消除', '家庭', '婆媳', '功效', '剧场', '屎', '降智', '术后', '减肥', '瘦',
    '私信', '蜜蜂', '扮丑', '绷带', '壮阳', '减', '一剂', '怀旧电影', '辱骂', '婚恋',
    '资源', '考公', '解决', '教育', '职业', '绝对化', '留学', '资料', '夸张', '出国',
    '测评', '医美', '夸大', '租房', '月子', '见效', '红娘', '高仿', '贱人', '人民币', '1：1',
    'sb', 'app', '情感', '诋毁', '私生女', '跑酷', '现金', '攀比', '潜水', '炫耀', '媛母婴',
    '奢侈品', '移民', '兴趣', '假货', '语言', '舞蹈', '盗摄', '文凭', '书法', '杂种', '炫富',
    '逼真', '露营', '极限运动', '野外', '中介', '小三', '婚外情', '私生子', '辟邪', '挡灾',
    '侮辱', '生火', '户外', '请勿模仿', '出轨', '自残', '抑郁症', '自闭', '自杀', '包养',
    '手相', '八卦', '消灾', '改运', '算命', '好运', '小心心', '新闻', '生活冷知识', '血腥'
]
selected_keywords = random.sample(keywords, 30)


async def main():
    browser = Browser()
    user_data_dir = ROOT_PATH / "userdata/xhs/2"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    await browser.init(**{
        "user_data_dir": user_data_dir,
    })

    xhs = XhsHandler(browser)
    await xhs.init()
    await xhs.crawler_by_keywords(keywords=selected_keywords, num=30, params=XhsSearchParams(
        sort_type=XhsNoteSortType.new,
        note_type=XhsNoteType.normal,
        note_time_type=XhsNoteTimeType.normal,
        search_scope_type=XhsNoteSearchScopeType.normal,
        location_type=XhsLocationType.normal,
    ))
    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
