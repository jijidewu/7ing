# ❤️ 微信每日早安推送程序（送给女朋友的专属仪式感）

每天早晨自动给女朋友（以及你自己）发送一条温馨浪漫的微信早安问候！
支持包含：**当天天气、气温贴士、恋爱天数、生日倒计时、每日情话/金句**。

无需购买云服务器，借助 **GitHub Actions** 每天免费自动定时推送。

---

## 🛠️ 第一步：申请微信测试号（3分钟搞定）

因为微信正式服务号需要企业认证，个人可以使用微信官方提供的**免费免审核测试号**。

1. **登录微信测试平台**：
   访问微信公众平台测试账号页面：[https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login](https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login)
   用你的微信扫码登录即可。

2. **获取核心凭证**：
   - 页面顶部可以看到：`appID` 和 `appsecret`。

3. **扫码关注与获取 OpenID**：
   - 页面向下滚动，会看到一个“**测试号二维码**”。
   - 拿你自己的微信以及**女朋友的微信**扫码关注该测试号。
   - 扫码关注后，右侧的“用户列表”里就会出现对应的“微信号”（这就是 `User OpenID`，一串字符）。

4. **新增消息模板**：
   在页面中找到“**新增测试模板**”，点击新增：
   - **模板标题**：`早安宝贝`
   - **模板内容**（直接完整复制下面这段文本粘贴进去）：

```text
亲爱的宝贝，早安！❤️

📅 今天是：{{date.DATA}}
🏙️ 城市：{{city.DATA}}
⛅ 天气：{{weather.DATA}}
🌡️ 气温：{{temperature.DATA}}
💨 风力：{{wind.DATA}}
💡 贴士：{{tips.DATA}}

👩‍❤️‍👨 我们已经相恋了：{{love_days.DATA}}
🎂 距离你的生日：{{birthday_days.DATA}}

{{words.DATA}}
```

   - 点击提交后，会生成一个 **模板ID (`template_id`)**。

---

## 💻 第二步：本地一键测试（即时验证）

在上传 GitHub 之前，可以在本地电脑先测一次，确认手机能正常收到消息：

1. 复制一份配置文件：
   将项目根目录的 `config.example.json` 复制并重命名为 `config.json`。

2. 填入你的真实信息：
```json
{
  "app_id": "你的微信测试号appID",
  "app_secret": "你的微信测试号appsecret",
  "template_id": "刚才生成的模板ID",
  "user_openid": "女朋友扫码后获取的openid,你自己的openid",
  "city": "北京",
  "start_date": "2023-05-20",
  "birthday": "10-01",
  "custom_note": "今天又是超级想你的一天，记得按时吃早饭哦！"
}
```
> 💡 提示：`user_openid` 可以填多个，用半角逗号 `,` 隔开，这样你和女朋友能同时收到推送。`config.json` 已在 `.gitignore` 中，不会被意外推送到公共代码库。

3. 运行测试：
```bash
python main.py
```
运行后，手机微信就会立刻收到一条精美的早安卡片！

---

## ☁️ 第三步：配置 GitHub Actions（免服务器每天定时自动推送）

想让它每天早晨（例如 7:30）全自动推送，只需将本仓库推送到你的 GitHub：

1. 将代码提交并推送到你个人的 GitHub 私有/公开仓库。
2. 进入仓库页面的 **Settings** -> **Secrets and variables** -> **Actions**。
3. 点击 **New repository secret**，依次添加以下环境变量：

| Secret 变量名 | 说明 | 示例值 |
| :--- | :--- | :--- |
| `APP_ID` | 微信测试号 appID | `wx123456789...` |
| `APP_SECRET` | 微信测试号 appsecret | `abcdef123456...` |
| `TEMPLATE_ID` | 消息模板 ID | `k9_aBcDeF...` |
| `USER_OPENID` | 接收消息的 OpenID（多个用逗号隔开） | `oABC123...,oXYZ456...` |
| `CITY` | 女朋友所在城市名称 | `北京` 或 `上海` |
| `START_DATE` | 恋爱纪念日（格式：年-月-日） | `2023-05-20` |
| `BIRTHDAY` | 女朋友生日（格式：月-日） | `10-01` |
| `CUSTOM_NOTE` | 你想额外嘱咐的甜言蜜语（选填） | `记得喝温水哦！` |

4. **开启与测试定时任务**：
   - 点击仓库顶部的 **Actions** 标签页。
   - 在左侧选择 **微信每日早安推送** 工作流。
   - 点击右侧的 **Run workflow** 按钮手动触发一次，验证 GitHub Actions 是否正常发送。
   - 以后每天北京时间早晨 **07:30**，GitHub 就会自动唤醒并替你准时送出这份早安心意！
