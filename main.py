import os
import sys
import json
import random
import datetime
import argparse
import requests

from surprise import beijing_today, next_birthday, get_events, get_upcoming_major

def load_config():
    """读取配置：优先从系统环境变量读取（适合 GitHub Actions），没有则读取本地 config.json"""
    config = {}
    config_file = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except Exception as e:
                print(f"[警告] 读取本地 config.json 失败: {e}")

    env_keys = [
        "APP_ID", "APP_SECRET", "TEMPLATE_ID", "USER_OPENID",
        "CITY", "START_DATE", "BIRTHDAY", "CUSTOM_NOTE", "AMAP_KEY",
        "NICKNAME", "BIRTHDAY_TYPE", "NIGHT_TEMPLATE_ID", "TARGET_URL"
    ]
    for key in env_keys:
        val = os.getenv(key)
        if val:
            config[key.lower()] = val

    return config

def get_access_token(app_id, app_secret):
    """获取微信公众号 access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    try:
        res = requests.get(url, timeout=10).json()
        if "access_token" in res:
            return res["access_token"]
        else:
            print(f"[错误] 获取 access_token 失败: {res}")
            return None
    except Exception as e:
        print(f"[异常] 请求微信 access_token 异常: {e}")
        return None

def translate_weather_desc(desc):
    """常见天气英文到中文映射，带贴心小图标"""
    mapping = {
        "patchy rain nearby": "局部阵雨 🌦️",
        "patchy light rain": "小阵雨 🌦️",
        "light rain shower": "小阵雨 🌦️",
        "rain shower": "阵雨 🌦️",
        "patchy rain possible": "局部可能有雨 🌦️",
        "light drizzle": "毛毛细雨 🌦️",
        "light rain": "小雨 🌧️",
        "moderate rain": "中雨 🌧️",
        "heavy rain": "大雨 ⛈️",
        "thundery outbreaks possible": "局部雷阵雨 ⛈️",
        "moderate or heavy rain with thunder": "雷阵雨 ⛈️",
        "partly cloudy": "多云 ⛅",
        "cloudy": "多云转阴 ☁️",
        "overcast": "阴天 ☁️",
        "sunny": "晴 ☀️",
        "clear": "晴朗 🌤️",
        "mist": "薄雾 🌫️",
        "fog": "大雾 🌁",
        "light snow": "小雪 ❄️",
        "moderate snow": "中雪 ❄️",
        "heavy snow": "大雪 ❄️",
    }
    desc_lower = desc.lower().strip()
    for k, v in mapping.items():
        if k in desc_lower:
            return v

    if "rain" in desc_lower:
        return "有雨 🌧️"
    if "cloud" in desc_lower:
        return "多云 ⛅"
    if "sun" in desc_lower:
        return "晴朗 ☀️"
    if "snow" in desc_lower:
        return "有雪 ❄️"

    return desc

def format_wind(wind_dir, wind_speed):
    """将生硬的风向风力转为生活化温馨描述"""
    dir_map = {
        "N": "北风", "S": "南风", "E": "东风", "W": "西风",
        "NE": "东北风", "NW": "西北风", "SE": "东南风", "SW": "西南风",
        "NNE": "偏北风", "NNW": "偏北风", "SSE": "偏南风", "SSW": "偏南风",
        "ENE": "偏东风", "ESE": "偏东风", "WNW": "偏西风", "WSW": "偏西风"
    }
    chinese_dir = dir_map.get(wind_dir.upper(), "微风")
    try:
        speed = float(wind_speed)
        if speed < 12:
            power = "微风拂面 🍃"
        elif speed < 28:
            power = "清风徐徐 🌿"
        else:
            power = "风力稍大 💨"
    except Exception:
        power = "轻柔微风 🍃"

    return f"{chinese_dir} · {power}"

def get_weather_info(city, amap_key=None, day_index=0):
    """获取天气信息（day_index=0 为今天，1 为明天，晚安推送用明天的天气）"""
    if amap_key:
        try:
            url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city}&key={amap_key}&extensions=all"
            r = requests.get(url, timeout=10).json()
            if r.get("status") == "1" and r.get("forecasts"):
                cast = r["forecasts"][0]["casts"][day_index]
                day_weather = cast.get("dayweather", "晴")
                night_weather = cast.get("nightweather", "多云")
                weather_str = day_weather if day_weather == night_weather else f"{day_weather}转{night_weather}"
                day_temp = cast.get("daytemp", "")
                night_temp = cast.get("nighttemp", "")
                wind = f"{cast.get('daywind', '')}风 {cast.get('daypower', '')}级"
                return {
                    "city": city,
                    "weather": weather_str,
                    "temperature": f"{night_temp}℃ ~ {day_temp}℃",
                    "wind": wind,
                    "min_temp": int(night_temp) if night_temp.isdigit() else 20,
                    "max_temp": int(day_temp) if day_temp.isdigit() else 25
                }
        except Exception as e:
            print(f"[提示] 高德天气接口调用失败: {e}")

    try:
        query_city = "闽侯" if "闽侯" in city else city
        url = f"https://wttr.in/{query_city}?format=j1"
        res = requests.get(url, timeout=10).json()
        cur = res["current_condition"][0]
        day = res["weather"][day_index]

        temp_c = cur.get("temp_C", "")
        min_temp = day.get("mintempC", "")
        max_temp = day.get("maxtempC", "")
        raw_desc = cur.get("weatherDesc", [{}])[0].get("value", "晴")
        if day_index > 0:
            # 明天的天气取中午时段的描述，而不是此刻的实时天气
            hourly = day.get("hourly", [])
            if hourly:
                raw_desc = hourly[len(hourly) // 2].get("weatherDesc", [{}])[0].get("value", raw_desc)
        weather_desc = translate_weather_desc(raw_desc)
        wind_dir = cur.get("winddir16Point", "E")
        wind_speed = cur.get("windspeedKmph", "8")
        wind_desc = format_wind(wind_dir, wind_speed)

        return {
            "city": city,
            "weather": weather_desc,
            "temperature": f"{min_temp}℃ ~ {max_temp}℃ (实时 {temp_c}℃)",
            "temp_range": f"{min_temp}℃ ~ {max_temp}℃",
            "current_temp": f"{temp_c}℃",
            "wind": wind_desc,
            "min_temp": int(min_temp) if min_temp.lstrip("-").isdigit() else 18,
            "max_temp": int(max_temp) if max_temp.lstrip("-").isdigit() else 25
        }
    except Exception as e:
        print(f"[警告] 获取天气失败: {e}")
        return {
            "city": city,
            "weather": "晴朗 🌤️",
            "temperature": "舒适",
            "temp_range": "20℃ ~ 26℃",
            "current_temp": "24℃",
            "wind": "微风拂面 🍃",
            "min_temp": 20,
            "max_temp": 25
        }

def get_care_tips(weather_info):
    """根据天气生成精炼关怀小贴士（严格控制字数，防止微信折叠截断）"""
    weather = weather_info.get("weather", "")
    min_temp = weather_info.get("min_temp", 20)
    max_temp = weather_info.get("max_temp", 25)

    if "雨" in weather:
        return "今天有雨，出门乖乖带伞哦 ☔"
    if "雪" in weather:
        return "下雪路滑，注意防滑保暖 ❄️"
    if min_temp < 12:
        return "早晚偏凉，多穿一件外套呀 🧣"
    if max_temp > 29:
        return "阳光充足，注意防晒多喝水 🥤"
    
    return "今天温度很舒服，保持好心情 🥪"

def calculate_love_days(start_date_str):
    """计算恋爱天数"""
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        today = beijing_today()
        delta = (today - start_date).days
        return f"{delta} 天 ❤️"
    except Exception as e:
        print(f"[提示] 计算恋爱天数格式有误: {e}")
        return "很长很长时间"

def calculate_birthday_days(birthday_str, birthday_type="solar"):
    """计算距离女朋友生日的天数（birthday_type 为 lunar 时按农历生日计算）"""
    try:
        today = beijing_today()
        days = (next_birthday(birthday_str, birthday_type, today) - today).days
        if days == 0:
            return "🎉 今天就是你的生日啦！祝宝贝生日快乐！🎂"
        return f"还有 {days} 天 🎂"
    except Exception as e:
        print(f"[提示] 计算生日格式有误: {e}")
        return "天天都是可爱日子"

def get_sweet_words(custom_note=""):
    """获取浪漫金句或情话"""
    try:
        res = requests.get("http://open.iciba.com/dsapi/", timeout=5).json()
        note = res.get("note", "").strip()
        content = res.get("content", "").strip()
        if note:
            prefix = f"{custom_note}\n\n" if custom_note else ""
            return f"{prefix}💬 每日一句：\n{note}\n({content})"
    except Exception as e:
        print(f"[提示] 金山词霸接口跳过: {e}")

    quotes_path = os.path.join(os.path.dirname(__file__), "quotes.json")
    if os.path.exists(quotes_path):
        try:
            with open(quotes_path, "r", encoding="utf-8") as f:
                quotes = json.load(f)
                if quotes:
                    word = random.choice(quotes)
                    prefix = f"{custom_note}\n\n" if custom_note else ""
                    return f"{prefix}💌 今日心语：{word}"
        except Exception:
            pass

    return custom_note if custom_note else "早安宝贝，愿今天好运常伴，超级想你！"

def get_today_str():
    """获取今天的日期和星期"""
    weekdays = ["星期一", "星期二", "星期四", "星期五", "星期六", "星期日"]
    # 修正星期索引
    all_weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    today = beijing_today()
    return f"{today.strftime('%Y年%m月%d日')} {all_weekdays[today.weekday()]}"

def send_template_message(access_token, user_openid, template_id, template_data, link_url=None):
    """向指定用户发送微信模板消息（支持点击卡片跳转到浪漫网页 link_url）"""
    url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"
    body = {
        "touser": user_openid,
        "template_id": template_id,
        "data": template_data
    }
    if link_url:
        body["url"] = link_url
    try:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        res = requests.post(url, data=data_bytes, headers=headers, timeout=10).json()
        if res.get("errcode") == 0:
            print(f"[成功] 消息已成功发送给用户: {user_openid}")
            return True
        else:
            print(f"[失败] 发送给用户 {user_openid} 失败: {res}")
            return False
    except Exception as e:
        print(f"[异常] 发送微信模板消息异常: {e}")
        return False

MAX_FIELD_LEN = 20  # 微信模板消息每个字段最多显示 20 个字，超出会被截断成“…”

def fit(text, limit=MAX_FIELD_LEN):
    """去掉换行并保证不超过字数上限，超出时在日志中提醒"""
    text = " ".join(str(text).split())
    if len(text) > limit:
        print(f"[提醒] 文案超过 {limit} 字会被微信截断，已自动裁剪：{text}")
        text = text[:limit - 1] + "…"
    return text

def load_messages():
    """读取 messages.json 中的早安 / 晚安文案"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[提示] 读取 messages.json 失败: {e}")
        return {}

def pick_daily(items, day, salt, fallback):
    """按天轮换文案：每轮打乱一次顺序，一轮之内不重复，同一天多次运行结果一致"""
    items = [x for x in items if x and len(x) <= MAX_FIELD_LEN]
    if not items:
        return fallback
    n = len(items)
    ordinal = day.toordinal()
    order = list(range(n))
    random.Random(f"{salt}-{ordinal // n}").shuffle(order)
    return items[order[ordinal % n]]

def short_city(city):
    """城市名尽量精简，给天气留出字数"""
    return "闽侯" if "闽侯" in city else city

def build_weather_line(weather_info, city_label):
    """天气行：闽侯 多云转阴 21~26℃"""
    clean_weather = weather_info['weather'].split(" ")[0].strip()
    min_t = weather_info.get('min_temp', 21)
    max_t = weather_info.get('max_temp', 26)
    return fit(f"{city_label} {clean_weather} {min_t}~{max_t}℃")

def build_tips(weather_info, day, when="今天"):
    """根据天气生成一句贴心提醒（≤20 字，每天换着说）"""
    weather = weather_info.get("weather", "")
    min_t = weather_info.get("min_temp", 20)
    max_t = weather_info.get("max_temp", 25)

    if "雨" in weather:
        options = [f"{when}有雨，出门记得带伞哦", f"{when}下雨，伞要带，鞋别湿啦", f"{when}有雨，带好伞，路滑慢慢走"]
    elif "雪" in weather:
        options = [f"{when}下雪，穿暖和点再出门", f"{when}有雪，路滑注意安全"]
    elif min_t < 8:
        options = [f"{when}很冷，围巾手套都带上", f"{when}降温了，羽绒服穿起来"]
    elif min_t < 15:
        options = [f"{when}有点凉，记得加件外套", f"{when}偏凉，别穿太少啦"]
    elif max_t - min_t >= 8:
        options = [f"{when}早晚温差大，带件外套", f"{when}温差有点大，注意加减衣服"]
    elif max_t >= 32:
        options = [f"{when}很热，防晒和水都带上", f"{when}太阳很大，记得防晒哦"]
    else:
        options = [f"{when}温度刚刚好，适合出去走走", f"{when}天气很舒服，心情也要好", f"{when}不冷不热，穿得舒服就好"]
    return fit(pick_daily(options, day, f"tips-{when}", options[0]))

def build_love_line(config):
    """恋爱与生日：相恋1635天 · 距生日160天"""
    today = beijing_today()
    try:
        love_days = (today - datetime.datetime.strptime(config["start_date"], "%Y-%m-%d").date()).days
    except Exception:
        love_days = "很多"
    try:
        days = (next_birthday(config["birthday"], config.get("birthday_type", "solar"), today) - today).days
        birthday_text = "今天是你的生日" if days == 0 else f"距生日{days}天"
    except Exception:
        birthday_text = "天天都是好日子"
    return fit(f"相恋{love_days}天 · {birthday_text}"), birthday_text

def build_morning_data(config, weather_info, city_label):
    """早安推送：今日天气 + 贴士 + 恋爱天数 + 今日心意 + 情话"""
    today = beijing_today()
    msgs = load_messages()

    weather_line = build_weather_line(weather_info, city_label)
    tips = build_tips(weather_info, today, "今天")
    love_line, birthday_text = build_love_line(config)
    note = pick_daily(msgs.get("morning_notes", []), today, "morning-note", "今天也超级想你，记得吃早饭")
    quote = pick_daily(msgs.get("morning_words", []), today, "morning-word", "今天也比昨天更喜欢你")

    # 今日彩蛋：生日 / 周年 / 节日 / 里程碑 / 自定义惊喜 —— 替换“心意”这一行
    events = get_events(today, config)
    main_event = next((e for e in events if e["note"]), None)
    if main_event:
        print(f"[彩蛋] 今天是：{main_event['name']}")
        note = main_event["note"]
    else:
        upcoming = get_upcoming_major(today, config)
        if upcoming:
            offset, e = upcoming
            print(f"[预告] {offset} 天后是：{e['name']}")
            note = f"再过{offset}天就是{e['name']}啦，期待吗"

    # 节气关怀：下雨下雪时天气提醒更重要，其余时候换成节气贴士
    jieqi_event = next((e for e in events if e["tips"]), None)
    if jieqi_event and "雨" not in weather_info['weather'] and "雪" not in weather_info['weather']:
        tips = jieqi_event["tips"]

    return {
        "greeting": "早安，我的小亚晴 ✨",
        "weather": weather_line,
        "tips": fit(tips),
        "love": love_line,
        "birthday": birthday_text,
        "note": fit(note),
        "quote": fit(quote),
    }

def build_night_data(config, weather_info, city_label):
    """晚安推送：明日天气 + 明日提醒 + 恋爱天数 + 晚安叮嘱 + 晚安情话"""
    today = beijing_today()
    tomorrow = today + datetime.timedelta(days=1)
    msgs = load_messages()

    weather_line = build_weather_line(weather_info, "明天")
    tips = build_tips(weather_info, today, "明天")
    love_line, birthday_text = build_love_line(config)
    note = pick_daily(msgs.get("night_notes", []), today, "night-note", "今天辛苦啦，早点睡哦")
    quote = pick_daily(msgs.get("night_words", []), today, "night-word", "今天也很爱你，晚安")

    # 今天是特殊日子：换成对应的晚安心意
    today_event = next((e for e in get_events(today, config) if e["note"]), None)
    if today_event:
        note = today_event["night_note"] or f"今天是{today_event['name']}，开心吗"

    # 明天是特殊日子：在贴士里提前预告（下雨时仍优先提醒带伞）
    tomorrow_event = next((e for e in get_events(tomorrow, config) if e["note"]), None)
    if tomorrow_event:
        print(f"[预告] 明天是：{tomorrow_event['name']}")
        if "雨" not in weather_info['weather']:
            tips = f"明天是{tomorrow_event['name']}，早点睡哦"

    return {
        "greeting": "晚安，我的小亚晴 🌙",
        "weather": weather_line,
        "tips": fit(tips),
        "love": love_line,
        "birthday": birthday_text,
        "note": fit(note),
        "quote": fit(quote),
    }

def to_template_data(content):
    """构造模板数据（确保模板中所有占位符如 greeting 均有值，避免显示变量名）"""
    data = {
        "greeting": content.get("greeting", "早安，小亚晴"),
        "weather": content.get("weather", ""),
        "tips": content.get("tips", ""),
        "love": content.get("love", ""),
        "note": content.get("note", ""),
        "quote": content.get("quote", ""),
        # 兼容备用字段名
        "birthday": content.get("birthday", ""),
    }
    return {k: {"value": v} for k, v in data.items()}

def main():
    parser = argparse.ArgumentParser(description="微信每日早安 / 晚安推送")
    parser.add_argument("--mode", choices=["morning", "night"], default=os.getenv("PUSH_MODE", "morning"),
                        help="morning=早安推送（默认），night=晚安推送")
    parser.add_argument("--date", help="模拟某一天（YYYY-MM-DD），用于预览彩蛋效果")
    parser.add_argument("--dry-run", action="store_true", help="只在终端预览内容，不真正发送")
    args = parser.parse_args()

    if args.date:
        fake_today = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        import surprise
        surprise.beijing_today = lambda: fake_today
        globals()["beijing_today"] = lambda: fake_today

    is_night = args.mode == "night"
    print("=" * 50)
    print(f"🚀 开始执行微信每日{'晚安' if is_night else '早安'}推送程序...")
    print("=" * 50)

    config = load_config()
    config.setdefault("nickname", "小亚晴")
    config.setdefault("start_date", "2022-05-05")
    config.setdefault("birthday", "04-04")
    config.setdefault("birthday_type", "solar")

    app_id = config.get("app_id")
    app_secret = config.get("app_secret")
    template_id = config.get("night_template_id") if is_night else config.get("template_id")
    user_openid = config.get("user_openid")

    city = config.get("city", "福州闽侯")
    amap_key = config.get("amap_key", "")
    weather_info = get_weather_info("闽侯" if "闽侯" in city else city, amap_key, day_index=1 if is_night else 0)

    if is_night:
        content = build_night_data(config, weather_info, short_city(city))
    else:
        content = build_morning_data(config, weather_info, short_city(city))

    print("\n—— 卡片预览（括号内为字数，微信上限 20）——")
    icons = {"weather": "🌤️", "tips": "🧣", "love": "❤️", "note": "💌", "quote": "💬"}
    for key in ("weather", "tips", "love", "note", "quote"):
        print(f"{icons[key]}  {content[key]}  ({len(content[key])})")
    print("—" * 20 + "\n")

    if args.dry_run:
        print("[预览模式] 未实际发送。")
        return

    if is_night and not template_id:
        print("[错误] 晚安推送需要单独的模板（标题不能是“早上好”），请配置 night_template_id / NIGHT_TEMPLATE_ID。")
        sys.exit(1)

    if not app_id or not app_secret or not template_id or not user_openid:
        print("[错误] 缺少核心配置！")
        sys.exit(1)

    token = get_access_token(app_id, app_secret)
    if not token:
        print("[终止] 无法获取微信 access_token，程序退出。")
        sys.exit(1)

    template_data = to_template_data(content)
    target_url = config.get("target_url")
    if target_url:
        print(f"[链接] 微信卡片将附带专属网页跳转: {target_url}")

    openids = []
    if isinstance(user_openid, list):
        openids = user_openid
    elif "," in str(user_openid):
        openids = [x.strip() for x in user_openid.split(",") if x.strip()]
    else:
        openids = [str(user_openid).strip()]

    for openid in openids:
        send_template_message(token, openid, template_id, template_data, link_url=target_url)

    print("\n✨ 全部推送任务处理完成！")

if __name__ == "__main__":
    main()
