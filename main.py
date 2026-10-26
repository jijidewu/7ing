import os
import json
import random
import datetime
import requests

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

    # 环境变量覆盖（GitHub Secrets）
    env_keys = [
        "APP_ID", "APP_SECRET", "TEMPLATE_ID", "USER_OPENID",
        "CITY", "START_DATE", "BIRTHDAY", "CUSTOM_NOTE", "AMAP_KEY"
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
    """常见天气英文到中文映射"""
    mapping = {
        "patchy rain nearby": "局部阵雨 🌦️",
        "patchy light rain": "小雨渐止 🌦️",
        "light rain shower": "小阵雨 🌦️",
        "rain shower": "阵雨 🌦️",
        "patchy rain possible": "可能有雨 🌦️",
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

def get_weather_info(city, amap_key=None):
    """获取天气信息（双方案：免 Key 的 wttr 或高德 API）"""
    # 方案 1: 如果配置了高德地图 API Key
    if amap_key:
        try:
            url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city}&key={amap_key}&extensions=all"
            r = requests.get(url, timeout=10).json()
            if r.get("status") == "1" and r.get("forecasts"):
                cast = r["forecasts"][0]["casts"][0]
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
            print(f"[提示] 高德天气接口调用失败，尝试备用天气源: {e}")

    # 方案 2: 免 Key 的 wttr.in 天气数据
    try:
        url = f"https://wttr.in/{city}?format=j1"
        res = requests.get(url, timeout=10).json()
        cur = res["current_condition"][0]
        day = res["weather"][0]

        temp_c = cur.get("temp_C", "")
        min_temp = day.get("mintempC", "")
        max_temp = day.get("maxtempC", "")
        raw_desc = cur.get("weatherDesc", [{}])[0].get("value", "晴")
        weather_desc = translate_weather_desc(raw_desc)
        wind_dir = cur.get("winddir16Point", "")
        wind_speed = cur.get("windspeedKmph", "")

        return {
            "city": city,
            "weather": weather_desc,
            "temperature": f"{min_temp}℃ ~ {max_temp}℃ (实时 {temp_c}℃)",
            "wind": f"{wind_dir}风 {wind_speed}km/h",
            "min_temp": int(min_temp) if min_temp.lstrip("-").isdigit() else 18,
            "max_temp": int(max_temp) if max_temp.lstrip("-").isdigit() else 25
        }
    except Exception as e:
        print(f"[警告] 获取天气失败: {e}")
        return {
            "city": city,
            "weather": "阳光明媚 ☀️",
            "temperature": "适宜",
            "wind": "微风",
            "min_temp": 20,
            "max_temp": 25
        }

def get_care_tips(weather_info):
    """根据天气生成关怀小贴士"""
    weather = weather_info.get("weather", "")
    min_temp = weather_info.get("min_temp", 20)
    max_temp = weather_info.get("max_temp", 25)

    tips = []
    if "雨" in weather:
        tips.append("今天可能有雨，出门千万记得带伞哦 ☔")
    elif "雪" in weather:
        tips.append("下雪路滑，走路慢一点，注意防寒保暖 ❄️")

    if min_temp < 10:
        tips.append("早晚温差大，出门多添一件外套，别着凉啦 🧣")
    elif max_temp > 30:
        tips.append("天气比较炎热，注意防晒，多喝温水哦 🥤")
    else:
        tips.append("今天温度很舒适，记得按时吃早饭，保持好心情 🥪")

    return " ".join(tips)

def calculate_love_days(start_date_str):
    """计算恋爱天数"""
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        delta = (today - start_date).days
        return f"{delta} 天 ❤️"
    except Exception as e:
        print(f"[提示] 计算恋爱天数格式有误: {e}")
        return "很长很长时间"

def calculate_birthday_days(birthday_str):
    """计算距离女朋友生日的天数 (格式如 10-01 或 2001-10-01)"""
    try:
        parts = birthday_str.strip().split("-")
        month = int(parts[-2])
        day = int(parts[-1])
        today = datetime.date.today()

        this_year_birthday = datetime.date(today.year, month, day)
        if today == this_year_birthday:
            return "🎉 今天就是你的生日啦！祝宝贝生日快乐！🎂"
        elif today < this_year_birthday:
            days = (this_year_birthday - today).days
            return f"还有 {days} 天 🎂"
        else:
            next_year_birthday = datetime.date(today.year + 1, month, day)
            days = (next_year_birthday - today).days
            return f"还有 {days} 天 🎂"
    except Exception as e:
        print(f"[提示] 计算生日格式有误: {e}")
        return "天天都是可爱日子"

def get_sweet_words(custom_note=""):
    """获取浪漫金句或情话"""
    # 尝试从金山词霸每日一句获取
    try:
        res = requests.get("http://open.iciba.com/dsapi/", timeout=5).json()
        note = res.get("note", "").strip()
        content = res.get("content", "").strip()
        if note:
            prefix = f"{custom_note}\n\n" if custom_note else ""
            return f"{prefix}💬 每日一句：\n{note}\n({content})"
    except Exception as e:
        print(f"[提示] 金山词霸接口跳过: {e}")

    # 读取本地精选情话兜底
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
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    today = datetime.date.today()
    return f"{today.strftime('%Y年%m月%d日')} {weekdays[today.weekday()]}"

def send_template_message(access_token, user_openid, template_id, template_data):
    """向指定用户发送微信模板消息"""
    url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"
    body = {
        "touser": user_openid,
        "template_id": template_id,
        "data": template_data
    }
    try:
        res = requests.post(url, json=body, timeout=10).json()
        if res.get("errcode") == 0:
            print(f"[成功] 消息已成功发送给用户: {user_openid}")
            return True
        else:
            print(f"[失败] 发送给用户 {user_openid} 失败: {res}")
            return False
    except Exception as e:
        print(f"[异常] 发送微信模板消息异常: {e}")
        return False

def main():
    print("=" * 50)
    print("🚀 开始执行微信每日早安推送程序...")
    print("=" * 50)

    config = load_config()

    app_id = config.get("app_id")
    app_secret = config.get("app_secret")
    template_id = config.get("template_id")
    user_openid = config.get("user_openid")

    if not app_id or not app_secret or not template_id or not user_openid:
        print("[错误] 缺少核心配置 (app_id, app_secret, template_id, user_openid)！")
        print("请在本地创建 config.json，或者在 GitHub Secrets 中配置相应环境变量。")
        return

    # 1. 获取微信 token
    token = get_access_token(app_id, app_secret)
    if not token:
        print("[终止] 无法获取微信 access_token，程序退出。")
        return

    # 2. 组装数据
    city = config.get("city", "闽侯")
    display_city = "福州 · 闽侯" if "闽侯" in city else city
    amap_key = config.get("amap_key", "")
    weather_info = get_weather_info("闽侯" if "闽侯" in city else city, amap_key)
    tips = get_care_tips(weather_info)

    start_date = config.get("start_date", "2022-05-05")
    love_days = calculate_love_days(start_date)

    birthday = config.get("birthday", "04-04")
    birthday_days = calculate_birthday_days(birthday)

    custom_note = config.get("custom_note", "")
    words = get_sweet_words(custom_note)
    today_str = get_today_str()

    # 3. 构造模板变量及颜色
    template_data = {
        "date": {"value": today_str, "color": "#1E90FF"},
        "city": {"value": display_city, "color": "#20B2AA"},
        "weather": {"value": weather_info["weather"], "color": "#3CB371"},
        "temperature": {"value": weather_info["temperature"], "color": "#FF8C00"},
        "wind": {"value": weather_info["wind"], "color": "#4682B4"},
        "tips": {"value": tips, "color": "#FF69B4"},
        "love_days": {"value": love_days, "color": "#FF1493"},
        "birthday_days": {"value": birthday_days, "color": "#FFA500"},
        "words": {"value": words, "color": "#9370DB"}
    }

    print("\n📦 今日生成的消息内容预览：")
    for k, v in template_data.items():
        print(f"  - {k}: {v['value']}")
    print("-" * 50)

    # 4. 支持单个或多个 openid（用逗号分隔，或者列表）
    openids = []
    if isinstance(user_openid, list):
        openids = user_openid
    elif "," in str(user_openid):
        openids = [x.strip() for x in user_openid.split(",") if x.strip()]
    else:
        openids = [str(user_openid).strip()]

    # 5. 循环发送
    for openid in openids:
        send_template_message(token, openid, template_id, template_data)

    print("\n✨ 全部推送任务处理完成！")

if __name__ == "__main__":
    main()
