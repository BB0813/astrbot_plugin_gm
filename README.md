# AstrBot QQ 群管插件

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-插件-green.svg)](https://github.com/Snowyyu/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> ⚠️ 功能会根据需求持续增加。如有 Bug 或功能建议，请先提 [Issue](https://github.com/mjy1113451/astrbot_plugin_gm/issues)；AI 审核确认后可自行提交 PR（修复难度低到中等）。

---

## 功能一览

| 命令 | 所需权限 | 说明 |
|------|---------|------|
| `/设管 @某人` | 插件管理员 / 群主 | 添加插件管理员（可动态增减） |
| `/取管 @某人` | 插件管理员 / 群主 | 移除插件管理员 |
| `/禁言 @某人 [分钟]` | 插件管理员 | 禁言指定成员（默认 10 分钟） |
| `/解禁 @某人` | 插件管理员 | 解除禁言 |
| `/踢 @某人` | 插件管理员 | 踢出群成员（可配合配置拒绝重新加群） |
| `/头衔 @某人 标题` | 插件管理员 | 设置成员专属头衔 |
| `/取消头衔 @某人` | 插件管理员 | 取消成员专属头衔 |
| `/设管理 @某人` | 插件管理员 | 设为群管理员 |
| `/取消管理 @某人` | 插件管理员 | 取消群管理员身份 |
| `/设精华` | 插件管理员 | 引用消息设为精华消息 |
| `/设群昵称 @某人 昵称` | 插件管理员 | 设置指定成员的群昵称 |
| `/改昵称 新昵称` | 任意成员 | 修改自己的群昵称 |
| `/撤回 N` | 插件管理员 | 撤回最近 N 条消息（最多 999） |
| `/撤回` | 插件管理员 | 引用撤回某条消息 |
| `/禁我 [分钟]` | 任意成员 | 自怼（默认 10 分钟） |

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

插件提供以下可配置项（在 AstrBot 配置文件中设置）：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `show_recall_notice` | bool | `true` | 撤回操作后在群里发送提示 |
| `reject_re_add` | bool | `false` | 踢人后自动拒绝该用户再次加群 |
| `plugin_admins` | list | `[]` | 插件管理员 QQ 列表（可使用 `/设管` 动态添加） |

### 配置示例

```json
{
  "show_recall_notice": true,
  "reject_re_add": false,
  "plugin_admins": ["123456789", "987654321"]
}
```

---

## 权限说明

本插件采用 **两层权限** 设计：

1. **插件管理员**：拥有使用所有管理命令的权限，由 `plugin_admins` 配置或通过 `/设管` 动态添加。群主也天然具备插件管理员身份。
2. **群管理员（QQ 官方）**：部分命令（禁言、踢人、设精华等）需要 QQ 群的管理员身份才能调用。

> **注意**：`/设管` 和 `/取管` 只需要插件管理员或群主身份即可操作，不需要 QQ 官方群管理员权限。

---

## 命令使用示例

```
# 添加插件管理员
/设管 @小明

# 禁言某成员 30 分钟
/禁言 @小明 30

# 踢出成员（并拒绝重新加群，需开启配置）
/踢 @小明

# 设置成员头衔
/头衔 @小明 荣誉成员

# 修改自己的群昵称
/改昵称 新名字

# 撤回最近 5 条消息
/撤回 5

# 引用撤回某条消息
/撤回  ← 引用目标消息发送

# 自怼（禁言自己 60 分钟）
/禁我 60
```

---

## 目录结构

```
astrbot_plugin_gm/
├── main.py              # 插件主逻辑（520 行）
├── metadata.yaml         # 插件元信息
├── _conf_schema.json     # 配置项说明
├── README.md             # 本文件
├── LICENSE               # MIT License
├── docs/                 # 文档
│   └── SOLUTIONS_bughigh_recall_command_因_.md
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
