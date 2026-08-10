# AstrBot QQ 群管插件

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-插件-green.svg)](https://github.com/Snowyyu/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 功能一览

### 基础管理

| 命令 | 所需权限 | 说明 |
|------|---------|------|
| `/设管 @某人` | 已废弃 | （已废弃，#132）插件管理员由 QQ 群管理员与群主自动识别 |
| `/禁言 @某人 [分钟]` | 插件管理员 | 禁言指定成员（默认 10 分钟） |
| `/解禁 @某人` | 插件管理员 | 解除禁言 |
| `/踢 @某人` | 插件管理员 | 踢出群成员（支持批量，可配合配置拒绝重新加群） |
| `/鞭尸 @某人` | 插件管理员 | 长期禁言被@的人（29 天 23 小时 59 分） |
| `/头衔 @某人 标题` | 插件管理员 | 设置成员专属头衔 |
| `/取消头衔 @某人` | 插件管理员 | 取消成员专属头衔 |
| `/设管理 @某人` | 插件管理员 | 设为群管理员 |
| `/取消管理 @某人` | 插件管理员 | 取消群管理员身份 |
| `/设精` / `/取消设精` | 插件管理员 | 设置 / 取消精华消息（引用消息） |
| `/设群昵称 @某人 昵称` | 插件管理员 | 设置指定成员的群昵称 |
| `/改昵称 新昵称` | 任意成员 | 修改自己的群昵称 |
| `/撤回 N` | 插件管理员 | 撤回最近 N 条消息（最多 50，不含指令本身） |
| `/撤回 @用户 N` | 插件管理员 | 撤回该用户最近 N 条消息（最多 50） |
| `/撤回` | 插件管理员 | 引用撤回某条消息 |
| `/撤回自身 N` | 插件管理员 | 撤回机器人最近发送的 N 条消息 |
| `/发群公告 内容` | 插件管理员 | 发送群公告 |
| `/删群公告` | 插件管理员 | 删除群公告 |
| `/改群头像` | 插件管理员 | 引用图片回复即可修改群头像 |
| `/宵禁` / `/解除宵禁` | 插件管理员 | 开启 / 关闭全群禁言 |
| `/禁我 [分钟]` | 任意成员 | 自怼（默认 10 分钟） |
| `/排名` | 任意成员 | 查看本群发言排名 |
| `/清除数据` | 插件管理员 | 清除本群发言计数 |
| `/举报` | 任意成员 | 举报群成员违规行为（需引用消息） |

### 按群覆盖配置

| 命令 | 所需权限 | 说明 |
|------|---------|------|
| `/设置群配置 <key> <value>` | 插件管理员 | 为本群覆盖插件配置项（如 `enabled_groups true`） |
| `/查看群配置` | 插件管理员 | 查看本群生效的配置覆盖 |
| `/清除群配置` | 插件管理员 | 清除本群所有覆盖 |
| `/status` | 插件管理员 | 查看插件配置 |

### 群违规检测

| 命令 | 所需权限 | 说明 |
|------|---------|------|
| `/群违规检测状态` | 插件管理员 | 查看群违规检测插件状态 |
| `/查看违规统计 [QQ]` | 插件管理员 | 查看违规统计（带 QQ 号查个人） |
| `/查看白名单` / `/添加白名单用户` / `/删除白名单用户` | 插件管理员 | 白名单管理（不受违规检测限制） |
| `/设置图片禁言时长` / `/设置刷屏禁言时长` / `/设置骂人禁言时长` / `/设置广告禁言时长` / `/设置链接禁言时长` / `/设置群号推广禁言时长` | 插件管理员 | 各违规类型禁言时长（秒） |
| `/添加骂人关键词` / `/删除骂人关键词` / `/查看骂人关键词` / `/切换骂人检测模式` | 插件管理员 | 骂人检测关键词与 AI / 关键词模式切换 |
| `/添加广告关键词` / `/删除广告关键词` / `/查看广告关键词` | 插件管理员 | 广告检测关键词管理 |

> 检测覆盖：图片 AI 审核（色情 / 擦边）、刷屏、骂人（AI 或关键词）、广告、链接、群号推广；命中后一律：撤回 + 按对应时长禁言。

---

## 安装

### 方法一：放入插件目录

1. 克隆本仓库：
   ```bash
   git clone https://github.com/mjy1113451/astrbot_plugin_gm.git
   ```
2. 将 `astrbot_plugin_gm` 目录放入 AstrBot 的 `plugins/` 目录
3. 重启 AstrBot 即可自动加载

### 方法二：通过包管理器安装

```bash
# 视AstrBot安装方式选择对应命令
pip install astrbot_plugin_group_admin
```

---

## 配置

插件提供以下可配置项（在 AstrBot 配置文件中设置，或在群内用 `/设置群配置` 按群覆盖）：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `show_recall_notice` | bool | `true` | 撤回操作后在群里发送提示 |
| `mute_notice` | bool | `true` | 禁言 / 解禁后回复结果 |
| `reject_re_add` | bool | `false` | 踢人后自动拒绝该用户再次加群 |
| `plugin_admins` | list | `[]` | 插件管理员 QQ 列表（可使用 `/设管` 动态添加） |
| `auto_recall_keywords` | list | `[]` | Bot 发言自动撤回关键词列表（推荐按群覆盖） |
| `auto_recall_enabled_groups` | list | `[]` | 启用自动撤回的群 ID 列表（推荐按群覆盖） |
| `enabled_groups` | list | `[]` | 启用违规检测的群号列表（`*` / `all` 表示全部；推荐按群覆盖） |
| `group_overrides` | dict | `{}` | 按群独立配置覆盖：`{群号: {key: value}}` |
| `max_message_history` | int | `50` | 每群内存缓存的撤回消息历史条数（用于 /撤回 N 与 /撤回自身 N） |

### 配置示例

```json
{
  "show_recall_notice": true,
  "reject_re_add": false,
  "plugin_admins": ["123456789", "987654321"]
}
```

### 按群覆盖示例

通过群内指令按群独立配置（推荐）：

```
/设置群配置 enabled_groups true
/设置群配置 auto_recall_keywords ["测试", "敏感词"]
/设置群配置 rank_top_n 20
```

或在配置文件中直接编辑 `group_overrides`：

```json
{
  "group_overrides": {
    "123456789": {
      "enabled_groups": true,
      "rank_top_n": 20,
      "auto_recall_keywords": ["测试", "敏感词"]
    }
  }
}
```

按群覆盖的可配置 key 包括：基础配置（`show_recall_notice`、`auto_recall_keywords`、`auto_recall_enabled_groups`、`rank_top_n`、`report_notify_admins`、`join_approve_keywords`、`join_notify_admins`、`join_request_notify_in_group`、`enabled_groups`）+ 违规检测全部子项（`spam_*`、`profanity_*`、`ad_*`、`link_*`、`group_promotion_*`、`ban_duration`、`whitelist_users`、`admin_bypass`、`notify_on_violation`)+ 权限细分（`title_admins`、`group_admin_admins`、`kick_admins`、`mute_kick_threshold`）+ 撤回历史（`max_message_history`）。
---

## `/撤回` 用法与兼容性

`/撤回` 命令支持三种用法：

```
/撤回 + 引用消息        撤回引用消息
/撤回 @用户 N           撤回该用户最近 N 条（最多 50）
/撤回 N                撤回最近 N 条（最多 50，不含指令本身）
```

配套命令：

```
/撤回自身 N             撤回机器人最近发送的 N 条消息
```

**消息历史机制（修复 #117 #118 #122）**：

- 插件在每个群内存缓存最近 `max_message_history` 条（默认 50）消息；用户发送的插件指令消息不记录，避免编号偏移；Bot 自身发言也记录（可用 `/撤回自身`）。
- `/撤回 @用户 N`、`/撤回 N` 优先使用该本地历史；当某群本地历史为空时，自动调用 OneBot 的 `get_group_msg_history` 接口兜底加载。
- 若 OneBot 实现不支持 `get_group_msg_history` 且本地历史也为空，则提示改用「引用消息」撤回。
- 本地历史仅记录进程启动后经过监听的消息，重启前历史不可恢复。

---

## 权限说明

本插件采用 **两层权限** 设计：

1. **插件管理员（#132）**：拥有使用所有管理命令的权限。识别方式：
   - `plugin_admins` 配置列表中的 QQ 号
   - QQ 群管理员
   - QQ 群主
2. **专项权限管理员**：按群覆盖的 `title_admins`、`group_admin_admins`、`kick_admins` 等专项权限列表中的人，仅对相应操作生效。

> **#132 变更**：`/设管` 和 `/取管` 命令已移除。绝大多数群中群管理员与群主天然具备插件管理员身份。`plugin_admins` 配置项保留作为兼容（如需跨群插件管理员可在配置文件中设置）。

---

## 命令使用示例

```

# 禁言某成员 30 分钟
/禁言 @小明 30

# 长期禁言（29 天 23 小时 59 分）
/鞭尸 @小明

# 踢出成员（并拒绝重新加群，需开启配置）
/踢 @小明

# 设置成员头衔
/头衔 @小明 荣誉成员

# 取消头衔
/取消头衔 @小明

# 引用撤回某条消息
/撤回  ← 引用目标消息发送

# 撤回最近 5 条消息
/撤回 5

# 撤回某用户最近 3 条
/撤回 @小明 3

# 撤回机器人最近 3 条
/撤回自身 3

# 修改自己的群昵称
/改昵称 新名字

# 本群独立启用违规检测
/设置群配置 enabled_groups true

# 自怼（禁言自己 60 分钟）
/禁我 60
```

---

## 目录结构

```
astrbot_plugin_gm/
├── main.py              # 插件主逻辑（2800+ 行）
├── metadata.yaml         # 插件元信息
├── _conf_schema.json     # 配置项说明
├── README.md             # 本文件
├── LICENSE               # MIT License
├── requirements.txt      # Python 依赖（aiohttp）
└── .github/              # GitHub 配置
```

---

## 开发相关

- **Python 版本**：3.10+
- **依赖框架**：[AstrBot](https://github.com/Snowyyu/AstrBot)
- **主要 API**：aiocqhttp（QQ 平台）
- **API 调用兼容**：内部对多种 AstrBot 版本做了兼容性适配

---

## 反馈与贡献

- 🐛 发现 Bug？请提交 [Issue](https://github.com/mjy1113451/astrbot_plugin_gm/issues)
- 💡 有功能建议？请先提交 Issue 讨论，待 AI 审核确认后可提 PR
- 🔧 修复难度低到中的 PR，会被优先合并
- 作者的群1075920323
---

> 本插件仅供学习与交流使用，请遵守 QQ / QQ 群的相关使用规范。