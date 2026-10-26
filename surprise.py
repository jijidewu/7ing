"""
彩蛋与节日模块 —— 让每天的推送都“知道今天是什么日子”

功能：
1. 北京时间日期（GitHub Actions 运行在 UTC，直接用 date.today() 会差一天）
2. 阳历 / 农历生日倒计时（农历换算基于开源库 6tail/lunar-python）
3. 自动识别：生日、恋爱周年、每月纪念日、恋爱天数里程碑、
   阳历节日、农历节日（春节/七夕/中秋…）、二十四节气
4. 读取 surprises.json 自定义彩蛋日历（提前写好某天想对她说的话）

注意：微信模板消息每个字段最多显示 20 个字，且不支持换行，
所以这里所有文案都控制在 20 字以内，并且不带表情（模板每行开头已自带表情）。
"""
import os
import json
import datetime

try:
    from lunar_python import Solar, Lunar
except ImportError:  # 未安装农历库时，农历相关功能自动降级跳过
    Solar = None
    Lunar = None

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))

# 优先级：数字越大越优先展示
P_BIRTHDAY = 100
P_ANNIVERSARY = 90
P_CUSTOM = 80
P_FESTIVAL = 60
P_MILESTONE = 50
P_MONTHLY = 30
P_JIEQI = 10


def beijing_today():
    """获取北京时间的今天"""
    return datetime.datetime.now(BEIJING_TZ).date()


def parse_date(date_str):
    return datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# 生日
# ---------------------------------------------------------------------------
def _birthday_in_year(year, month, day, birthday_type):
    """返回某一年里生日对应的阳历日期"""
    if birthday_type == "lunar" and Lunar is not None:
        solar = Lunar.fromYmd(year, month, day).getSolar()
        return datetime.date(solar.getYear(), solar.getMonth(), solar.getDay())
    try:
        return datetime.date(year, month, day)
    except ValueError:  # 2 月 29 日生日，平年按 2 月 28 日过
        return datetime.date(year, 2, 28)


def next_birthday(birthday_str, birthday_type="solar", today=None):
    """计算下一个生日的阳历日期（今天是生日则返回今天）"""
    today = today or beijing_today()
    parts = birthday_str.strip().split("-")
    month, day = int(parts[-2]), int(parts[-1])
    # 农历日期按“农历年”换算，往前多看一年，防止跨年时漏算
    for year in (today.year - 1, today.year, today.year + 1):
        d = _birthday_in_year(year, month, day, birthday_type)
        if d >= today:
            return d
    return _birthday_in_year(today.year + 1, month, day, birthday_type)


# ---------------------------------------------------------------------------
# 节日数据：(名称, 早安心意, 是否重要节日)
# ---------------------------------------------------------------------------
SOLAR_FESTIVALS = {
    "01-01": ("元旦", "新年快乐！今年也请多多指教", True),
    "02-14": ("情人节", "情人节快乐，我的玫瑰只给你", True),
    "03-08": ("女神节", "女神节快乐，愿你永远自由闪亮", False),
    "03-14": ("白色情人节", "白色情人节，还是想说我爱你", False),
    "04-01": ("愚人节", "今天说的都是假的，除了爱你", False),
    "05-20": ("520", "520快乐，我爱你，每一天", True),
    "05-21": ("521", "521，爱你的第二天也一样爱", False),
    "06-01": ("儿童节", "儿童节快乐，我的小朋友", False),
    "10-31": ("万圣节", "万圣节快乐，不给糖就亲你", False),
    "11-11": ("双十一", "光棍节？还好我早就有你啦", False),
    "12-24": ("平安夜", "平安夜快乐，岁岁平安年年有我", True),
    "12-25": ("圣诞节", "圣诞快乐，你是我的圣诞礼物", True),
    "12-31": ("跨年夜", "今年最后一天，谢谢你陪着我", True),
}

LUNAR_FESTIVALS = {
    (1, 1): ("春节", "新春快乐！新的一年也要在一起", True),
    (1, 15): ("元宵节", "元宵节快乐，汤圆甜，你更甜", False),
    (5, 5): ("端午节", "端午安康，粽子甜咸都随你", False),
    (7, 7): ("七夕", "七夕快乐，我想每天都见到你", True),
    (8, 15): ("中秋节", "中秋快乐，有你才算团圆", True),
    (9, 9): ("重阳节", "重阳节，想和你慢慢变老", False),
    (12, 8): ("腊八节", "腊八节，记得喝碗热粥哦", False),
}

JIEQI_TIPS = {
    "立春": "今天立春，一起等花开吧",
    "立夏": "今天立夏，多喝水别中暑",
    "立秋": "立秋啦，秋天第一杯奶茶我请",
    "立冬": "今天立冬，记得吃饺子哦",
    "冬至": "冬至快乐，吃碗热乎的汤圆",
    "夏至": "今天夏至，白天最长想你最久",
    "小寒": "今天小寒，多穿点别冻着",
    "大寒": "今天大寒，最冷的时候抱抱你",
}

MILESTONE_WORDS = {
    520: "相恋第520天，我爱你",
    521: "相恋第521天，我爱你",
    666: "相恋第666天，一路都很顺",
    999: "相恋第999天，长长久久",
    1000: "相恋第1000天，未来还很长",
    1314: "相恋第1314天，一生一世",
    1666: "相恋第1666天，顺顺利利",
    2000: "相恋第2000天，谢谢你一直在",
    3344: "相恋第3344天，生生世世",
    5200: "相恋第5200天，依然爱你",
}


def _event(name, priority, note, night_note=None, tips=None, major=False):
    return {
        "name": name,          # 短名称，用于“明天是XX”“再过N天就是XX”
        "priority": priority,
        "note": note,          # 早安心意（≤20 字）
        "night_note": night_note,  # 晚安心意（≤20 字）
        "tips": tips,          # 替换贴士行（节气）
        "major": major,        # 是否提前预告
    }


def _load_custom_surprises():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "surprises.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("dates", {}) if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[警告] 读取 surprises.json 失败: {e}")
        return {}


def _months_between(start, day):
    return (day.year - start.year) * 12 + (day.month - start.month)


def _is_monthly_day(start, day):
    """每月的纪念日（处理 31 号这类大月日期在小月的情况）"""
    next_month_first = (day.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    last_day = (next_month_first - datetime.timedelta(days=1)).day
    return day.day == min(start.day, last_day)


def get_events(day, config):
    """返回某一天的所有特殊事件（按优先级从高到低排序）"""
    events = []

    # 1. 生日
    birthday = config.get("birthday")
    if birthday:
        try:
            bday = next_birthday(birthday, config.get("birthday_type", "solar"), day)
            if bday == day:
                events.append(_event(
                    "你的生日", P_BIRTHDAY,
                    "生日快乐！今天全世界都爱你",
                    night_note="生日快过完啦，再说一次生日快乐",
                    major=True,
                ))
        except Exception as e:
            print(f"[提示] 生日解析失败: {e}")

    # 2. 恋爱周年 / 每月纪念日 / 天数里程碑
    start_str = config.get("start_date")
    if start_str:
        try:
            start = parse_date(start_str)
            love_days = (day - start).days
            if day > start and (day.month, day.day) == (start.month, start.day):
                years = day.year - start.year
                events.append(_event(
                    f"{years}周年纪念日", P_ANNIVERSARY,
                    f"{years}周年快乐，往后每一年都是你",
                    night_note=f"{years}周年快过完了，明年还牵着你",
                    major=True,
                ))
            elif day > start and _is_monthly_day(start, day):
                months = _months_between(start, day)
                events.append(_event(
                    f"在一起第{months}个月", P_MONTHLY,
                    f"在一起第{months}个月啦，每月都纪念",
                ))
            if love_days > 0 and (love_days % 100 == 0 or love_days in MILESTONE_WORDS):
                events.append(_event(
                    f"相恋第{love_days}天", P_MILESTONE,
                    MILESTONE_WORDS.get(love_days, f"相恋第{love_days}天，谢谢你一直在"),
                    major=love_days % 1000 == 0 or love_days in (520, 1314),
                ))
        except Exception as e:
            print(f"[提示] 纪念日解析失败: {e}")

    # 3. 阳历节日
    mmdd = day.strftime("%m-%d")
    if mmdd in SOLAR_FESTIVALS:
        fname, note, major = SOLAR_FESTIVALS[mmdd]
        events.append(_event(fname, P_FESTIVAL, note, major=major))

    # 4. 农历节日 + 节气
    if Solar is not None:
        solar = Solar.fromYmd(day.year, day.month, day.day)
        lunar = solar.getLunar()
        key = (lunar.getMonth(), lunar.getDay())  # 闰月为负数，自动不会匹配
        if key in LUNAR_FESTIVALS:
            fname, note, major = LUNAR_FESTIVALS[key]
            events.append(_event(fname, P_FESTIVAL, note, major=major))
        tomorrow = solar.next(1).getLunar()
        if tomorrow.getMonth() == 1 and tomorrow.getDay() == 1:
            events.append(_event(
                "除夕", P_FESTIVAL, "除夕快乐，今年也和你一起守岁",
                night_note="新年第一个想见的人，还是你",
                major=True,
            ))
        jieqi = lunar.getJieQi()
        if jieqi:
            tip = JIEQI_TIPS.get(jieqi, f"今天{jieqi}，换季注意身体哦")
            events.append(_event(jieqi, P_JIEQI, None, tips=tip))

    # 5. 自定义彩蛋（surprises.json）
    custom = _load_custom_surprises()
    for key in (day.strftime("%Y-%m-%d"), mmdd):
        item = custom.get(key)
        if not item:
            continue
        if isinstance(item, str):
            item = {"note": item}
        events.append(_event(
            item.get("name", "专属彩蛋"), P_CUSTOM,
            item.get("note"),
            night_note=item.get("night_note"),
            major=bool(item.get("major", False)),
        ))
        break

    events.sort(key=lambda e: e["priority"], reverse=True)
    return events


def get_upcoming_major(today, config, within_days=3, exclude_birthday=True):
    """找出未来几天内最近的一个重要日子，用于预告"""
    for offset in range(1, within_days + 1):
        day = today + datetime.timedelta(days=offset)
        for e in get_events(day, config):
            if not e["major"]:
                continue
            if exclude_birthday and e["name"] == "你的生日":
                continue
            return offset, e
    return None
