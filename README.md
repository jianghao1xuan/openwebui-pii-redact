# openwebui-pii-redact

> ## ⚠️ 早期版本，请自己复核结果
>
> 这个插件还在早期阶段，识别规则一定有漏的写法、也一定有判断不准的地方。
> **凡是用它处理过的内容，最终结果请你自己再确认一遍**，不要直接当成“已经安全”。
> 尤其是要发给第三方、或者要过合规检查的材料——它的作用是减少暴露面，不是给你签字背书。
>
> **发现漏挡、误伤，或者有别的想法：[开个 Issue 告诉我](https://github.com/jianghao1xuan/openwebui-pii-redact/issues)。** 我更想知道它漏在哪儿。

给 Open WebUI 用的中文脱敏插件（Filter）。发出去之前把手机号、身份证、银行卡这些换成占位符，模型回话时再换回真值。

一句话：**你看到的还是真号，模型从头到尾只见到 `[PHONE_1]`。**

> 适用于 Open WebUI 0.13.x，实测于 0.13.4。

---

## 它挡什么

共八类，能挡的都带校验，不是看见一串数字就换：

| 类型 | 占位符 | 例子 | 怎么判断 |
|---|---|---|---|
| 手机号 | `[PHONE_n]` | `+86 138 0000 6666`、`138-0000-7777`、`13812345678` | 11 位、1 开头，允许 `+86`、空格、横杠 |
| 身份证（18 位） | `[ID_n]` | `11010519491231002X` | 校验位对得上才换 |
| 老身份证（15 位） | `[ID_n]` | `110105491231003` | 出生日期合法才换 |
| 银行卡 | `[BANK_n]` | `4111 1111 1111 1111` | 16–19 位，Luhn 校验对得上才换 |
| 邮箱 | `[EMAIL_n]` | `a.b@example.com` | 标准邮箱格式 |
| 固话 | `[TEL_n]` | `0571-88888888`、`(010) 12345678`、`400-123-4567` | 区号 + 号码格式 |
| 车牌 | `[PLATE_n]` | `京A12345`、`粤BD12345` | 省简称 + 格式；新能源 6 位也认 |
| 统一社会信用代码 | `[USCC_n]` | `91350100M000100Y43` | GB 32100 校验位对得上才换 |
| 护照 | `[PASSPORT_n]` | `E12345678`、`G87654321` | E/G + 8 位数字 |

同一句话里出现两个手机号，会是 `[PHONE_1]`、`[PHONE_2]`；同一个号出现两次，只占一个编号。

**还原是逐字的**：原文 `+86 138 0000 6666` 被换成 `[PHONE_1]`，还原回来还是 `+86 138 0000 6666`，连空格都在。

---

## 它不做什么（重要：这几类它真不做）

- **不做姓名、地址、公司名**。靠词典会漏（张三李四之外的名字），靠模型会误判（“北京”可能是地址也可能只是地名），误伤一次就把正文改坏。这几类请自己判断。
- **不做金额、IP、QQ/微信、港澳台证件、军官证**。
- **非流式 API 的返回体不还原**。界面走的是流式，能还原；如果你用脚本直接调 `stream: false` 的接口，返回里仍是 `[PHONE_1]`。`outlet` 改的是库里的消息和发给前端的事件，不重写那一次 HTTP 响应。
- **映射只在内存**。进程重启，旧对话里的占位符就换不回来了（不会错换，只是不再换）。这是故意的：不落盘，就没有“映射表被拿走”的风险。
- **挡不住“模型自己猜”**。占位符里没有任何真实信息，但如果上下文里有其他线索（比如“我在杭州，尾号 5678”），模型仍可能推断——这不在插件的能力范围内。

---

## 装

1. 打开 Open WebUI → 右上角头像 → **Admin Panel** → **Functions** → 右上角 **+**
2. 类型选 **Filter**，名字随便（ID 只能用字母、数字、下划线，建议 `pii_redact`）
3. 把 [`filter.py`](filter.py) 的内容整个粘进去 → Save
4. 回到 Functions 列表，把这一项打开 **Active** 和 **Global**
5. 刷新页面，随便发一句带手机号的话

装好后没有任何界面——它就在后台生效。

### 验证它真的在工作

发这一句：

```
我的手机号 13812345678，我的手机号后四位是多少？
```

模型应当**答不出后四位**，并可能告诉你“这是占位符”。如果它直接答 5678，说明插件没生效（检查 Active/Global）。

---

## 配置

点开这个 Function 的齿轮（Valves），全部有默认值，一般不用动：

| 参数 | 默认 | 说明 |
|---|---|---|
| `mask_phone` / `mask_id` / `mask_bank` / `mask_email` | 开 | 关掉对应的类就不挡 |
| `mask_tel` / `mask_plate` / `mask_uscc` / `mask_passport` | 开 | 同上 |
| `restore` | 开 | 关掉就只挡不还原，回复里会留着 `[PHONE_1]` |
| `log_payload` | **关** | 排查用：把“模型实际收到的那句”写进文件 |
| `log_dir` | 空 | `log_payload` 打开后写到哪个目录；空则写系统临时目录 |

**日志默认关**：装上它不会在你硬盘上写任何东西。只有你自己要看来回的样子时才打开，而且只记脱敏后的内容，不记真值。

---

## 它怎么做的（原理，四行）

1. `inlet` 每轮一次：把这一说的映射清空，给这句里的敏感值编号。
2. `request` 每次发给模型前都跑一遍：工具调用一轮会发好几次，占位符已经不含数字，再跑不会变形。
3. `stream` / `outlet` 在回来的路上把占位符换回原文；流式会被切成小块，所以有半截占位符的缓冲。
4. 映射只存在进程内存里，按对话 ID 分场，不落盘、不写日志。

---

## 自己验（不花钱）

**普通用户不用看这一节。** 装完之后按上一节发一句话就能验，不需要 Python、不需要命令行。

下面这三组脚本是给想改代码、或者想确认“它真的没漏”的人用的：

```bash
python tests/test_basic.py     # 六条：挡得住、重复跑不变形、还原准
python tests/test_variants.py  # 八种写法 + 不该误伤的
python tests/test_new_types.py # 固话/车牌/信用代码/护照
```

预期输出：`六条全过`、`变体 8/8 全过`、`应挡 8/8｜误伤 0/6`。

要求：**任意 Python 3.8+，没有第三方依赖**。没装 pydantic 也能跑（`tests/_stub.py` 会顶上）。

<details>
<summary>为什么插件本身不需要装 Python</summary>

插件是跑在 Open WebUI 自己的 Python 环境里的——你已经装了 Open WebUI，环境就在那儿，插件只是一个 `.py` 文件，粘贴进管理面板即可。不用打包 Python，也不用在你自己电脑上再装一个。
</details>

---

## English

A Chinese-PII redaction filter for Open WebUI. Before your message leaves the browser it replaces Chinese mobile numbers, ID card numbers, bank cards, emails, landlines, license plates, unified social credit codes, and passports with placeholders like `[PHONE_1]`; placeholders are restored on the way back, so you see real values while the model never does.

- Chinese-first rules with real checksums (ID check digit, Luhn, GB 32100).
- Reversible, byte-for-byte on restore, works with streaming.
- Mapping lives in process memory only; nothing is written to disk by default.
- Does **not** handle names, addresses, amounts, IPs.
- MIT licensed.

---

## 反馈

这个插件的规则是照着“能想到的写法”写的，真实世界一定还有没想到的。

- **发现漏挡**：把脱敏后的样子贴出来（**别贴真号**），说明是什么写法漏的
- **发现误伤**：把被改坏的那句贴出来，说明本来应该是什么
- **想加类型**：说清规则和校验方式，能验的我加

到 [Issues](https://github.com/jianghao1xuan/openwebui-pii-redact/issues) 留言就行。一个人想不全，你碰到的那种写法，我大概率没想到。

---

## 许可

MIT，见 [LICENSE](LICENSE)。用之前请自己判断它是否适合你的场景——它挡的是“格式明确的号码”，不是“所有敏感信息”。
