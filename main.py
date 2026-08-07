from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, At

try:
    from astrbot.api.message import MessageChain
except ImportError:
    try:
        from astrbot.api.message_components import MessageChain
    except ImportError:
        MessageChain = None

import json
import os
import re
import time
import base64
from collections import defaultdict, deque
from pathlib import Path

try:
    import aiohttp
except ImportError:
    aiohttp = None


def _parse_qq_list(text: str) -> list:
    """从文本中提取所有合法的QQ号（5-12位数字）。"""
    return list({m.group(1) for m in re.finditer(r"(\d{5,12})", text or "")})


@register(
    "group_admin",
    "YourName",
    "QQ群群管插件 - 禁言/踢人/头衔/精华/撤回/群公告/关键词撤回/违规检测/排名",
    "2.4.0",
    "https://github.com/mjy1113451/astrbot_plugin_gm"
)
class GroupAdminPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        try:
            from astrbot.api.star import StarTools
            self.data_dir = StarTools.get_data_dir() / "group_admin"
        except ImportError:
            self.data_dir = Path(os.getcwd()) / "data" / "group_admin"

        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = self.data_dir / "config.json"
        self.stats_path = self.data_dir / "stats.json"
        self.reports_path = self.data_dir / "reports.json"
        self.config = self.load_config()
        self.stats = self.load_json(self.stats_path, {"groups": {}})
        self.reports = self.load_json(self.reports_path, {"pending": []})

        # 群违规检测运行时状态（#109 PR #1 合并自参考插件）
        # spam_records[(group_id, user_id)] -> [timestamp, ...]
        # 仅内存，进程重启清空（与参考插件行为一致）
        self.spam_records = defaultdict(list)

        # 本地群消息缓存（#117 #118），用于在不支持 get_group_msg_history 的
        # OneBot 实现上，提供 /撤回 @用户 N 与 /撤回 N 的回退数据源。
        # 结构：recent_messages[group_id] -> deque[{"message_id", "user_id"}, ...]
        # 仅记录本进程启动后经过 on_group_message 的消息，重启前历史不可恢复。
        # 使用普通 dict + setdefault 显式创建，避免 defaultdict 工厂被「in 检查」类用法意外触发。
        self.recent_messages = {}

    # ===================== 通用 IO =====================

    def load_json(self, path: Path, default):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载 {path.name} 失败: {e}")
        return default

    def save_json(self, path: Path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存 {path.name} 失败: {e}")

    def _get_default_config(self) -> dict:
        return {
            "show_recall_notice": True,
            "mute_notice": True,
            "reject_re_add": False,
            "plugin_admins": [],
            "groups": {},
            # 按操作类型分别配置管理员（#34 权限系统重构）
            "title_admins": [],
            "group_admin_admins": [],
            "kick_admins": [],
            # 关键词自动撤回（#46）
            "auto_recall_keywords": [],
            "auto_recall_enabled_groups": [],
            # 违规检测（#19）
            "violation_keywords": [],
            "violation_action": "none",
            "violation_mute_minutes": 10,
            "violation_enabled_groups": [],
            # 举报（#21）
            "report_notify_admins": [],
            # 群公告与排名（#16, #29）
            "rank_top_n": 10,
            # 禁言次数达到阈值后自动踢出（#103），0 表示关闭
            "mute_kick_threshold": 0,
            # 加群请求关键词同意（#27 增强）
            "join_approve_keywords": [],
            "join_notify_admins": [],
            # 加群申请群内提醒（#57）
            "join_request_notify_in_group": False,
            "pending_join_requests": {},
            # #74 配置按群独立（保留全局默认值）
            "group_overrides": {},
            # ====== 群违规检测（合并自 astrbot_plugin_group_moderation） ======
            # AI 审核 API（图片 / 骂人 AI 检测共用）
            "api_type": "openai_vision",
            "api_endpoint": "",
            "api_key": "",
            "model_name": "gpt-4o",
            "detection_prompt": "",
            "threshold": 0.7,
            "check_porn": True,
            "check_sexy": True,
            # 监控群组（* 或 all 表示全部启用；为空表示不监控；可按群覆盖为 bool）
            "enabled_groups": [],
            "spam_check_enabled": True,
            "spam_threshold": 5,
            "spam_time_window": 10,
            "spam_ban_duration": 600,
            "profanity_check_enabled": True,
            "profanity_use_ai": True,
            "profanity_ban_duration": 600,
            "profanity_keywords": [
                "傻逼", "操你妈", "妈的", "他妈的", "草你妈", "艹你妈",
                "你妈死了", "去你妈的", "狗日的", "王八蛋", "畜生", "杂种",
                "贱人", "婊子",
            ],
            "ad_check_enabled": True,
            "ad_ban_duration": 600,
            "ad_keywords": [
                "加群", "加微信", "加QQ", "联系我", "私聊", "代练", "代打",
                "刷钻", "刷币", "外挂", "辅助", "出售", "转让", "低价",
                "优惠", "促销", "折扣", "代购", "微商", "兼职", "赚钱",
                "日赚", "月入", "进群",
            ],
            "link_check_enabled": False,
            "link_ban_duration": 600,
            "group_promotion_check_enabled": True,
            "group_promotion_ban_duration": 600,
            "ban_duration": 600,
            "whitelist_users": [],
            "admin_bypass": True,
            "notify_on_violation": True,
        }

    def load_config(self) -> dict:
        default_config = self._get_default_config()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for key, value in default_config.items():
                        if key not in saved:
                            saved[key] = value
                    if "groups" not in saved:
                        saved["groups"] = {}
                    return saved
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                return default_config
        return default_config

    def save_config(self):
        self.save_json(self.config_path, self.config)

    def save_stats(self):
        self.save_json(self.stats_path, self.stats)

    def save_reports(self):
        self.save_json(self.reports_path, self.reports)

    # ===================== 工具方法 =====================

    def is_plugin_admin(self, user_id: str) -> bool:
        return str(user_id) in [str(uid) for uid in self.config.get("plugin_admins", [])]

    def get_group_setting(self, group_id: str, key: str, default=None):
        """按群读取配置项，先查 group_overrides[群号][key]，否则用全局配置/默认值。"""
        overrides = self.config.get("group_overrides", {}).get(str(group_id), {})
        if key in overrides:
            return overrides[key]
        return self.config.get(key, default)

    def _is_group_owner(self, raw: dict) -> bool:
        role = raw.get("sender", {}).get("role", "")
        return role == "owner"

    def _is_group_admin(self, raw: dict) -> bool:
        role = raw.get("sender", {}).get("role", "")
        return role in {"admin", "owner"}

    def _is_group_admin_or_owner(self, raw: dict) -> bool:
        return self._is_group_admin(raw) or self._is_group_owner(raw)

    def _is_sender_group_admin_only(self, raw: dict) -> bool:
        return raw.get("sender", {}).get("role", "") == "admin"

    def _sender_has_special_title(self, raw: dict) -> bool:
        sender = raw.get("sender", {}) if isinstance(raw, dict) else {}
        for key in ("title", "special_title"):
            value = str(sender.get(key, "")).strip()
            if value:
                return True
        return False

    def _get_group_override_list(self, group_id: str, key: str) -> list:
        overrides = self.config.setdefault("group_overrides", {})
        gconf = overrides.setdefault(str(group_id), {})
        value = gconf.setdefault(key, [])
        if not isinstance(value, list):
            value = [value] if value else []
            gconf[key] = value
        return value

    def _add_group_override_admins(self, group_id: str, key: str, qq_list: list) -> list:
        admins = self._get_group_override_list(group_id, key)
        added = []
        for qq in qq_list:
            qq = str(qq)
            if qq and qq not in [str(x) for x in admins]:
                admins.append(qq)
                added.append(qq)
        if added:
            self.save_config()
        return added

    def _remove_group_override_admins(self, group_id: str, key: str, qq_list: list) -> list:
        admins = self._get_group_override_list(group_id, key)
        removed = []
        for qq in qq_list:
            qq = str(qq)
            for item in list(admins):
                if str(item) == qq:
                    admins.remove(item)
                    removed.append(qq)
                    break
        if removed:
            self.save_config()
        return removed

    def has_title_admin_rights(self, user_id: str, group_id: str, raw: dict) -> bool:
        uid = str(user_id)
        if self.is_plugin_admin(uid):
            return True
        title_admins = [str(x) for x in self.get_group_setting(group_id, "title_admins", [])]
        if uid in title_admins:
            return True
        if self._is_group_admin_or_owner(raw):
            return True
        return False

    def has_kick_admin_rights(self, user_id: str, group_id: str, raw: dict) -> bool:
        uid = str(user_id)
        if self.is_plugin_admin(uid):
            return True
        kick_admins = [str(x) for x in self.get_group_setting(group_id, "kick_admins", [])]
        if uid in kick_admins:
            return True
        if self._is_group_admin_or_owner(raw):
            return True
        return False

    def has_group_admin_rights(self, user_id: str, group_id: str, raw: dict) -> bool:
        uid = str(user_id)
        if self.is_plugin_admin(uid):
            return True
        ga_admins = [str(x) for x in self.get_group_setting(group_id, "group_admin_admins", [])]
        if uid in ga_admins:
            return True
        if self._is_group_admin_or_owner(raw):
            return True
        return False

    def _get_raw_message(self, event: AstrMessageEvent):
        """Robustly extract the raw message dict from the event."""
        try:
            return event.message_obj.raw_message
        except Exception:
            pass
        return getattr(event, "raw_message", None)

    def _parse_qq(self, text: str) -> str:
        nums = _parse_qq_list(text)
        return nums[0] if nums else ""

    def _extract_at_qq(self, raw: dict) -> str:
        """Extract first QQ number from At components in the raw message."""
        if not raw:
            return ""
        for seg in raw.get("message", []):
            if isinstance(seg, dict) and seg.get("type") == "at":
                qq = str(seg.get("data", {}).get("qq", ""))
                if qq:
                    return qq
        return ""

    def _extract_at_qqs(self, raw: dict) -> list:
        """Extract all QQ numbers from At components in the raw message."""
        if not raw:
            return []
        qqs = []
        for seg in raw.get("message", []):
            if isinstance(seg, dict) and seg.get("type") == "at":
                qq = str(seg.get("data", {}).get("qq", ""))
                if qq and qq not in qqs:
                    qqs.append(qq)
        return qqs

    def _extract_image_url(self, event: AstrMessageEvent) -> str:
        """从 event 的消息链中提取第一张图片的 URL。"""
        try:
            chain = getattr(event.message_obj, "message", None) or getattr(event, "message", None)
            if chain is None:
                return ""
            # AstrBot 的 message chain 可能是 MessageChain 或 list
            if hasattr(chain, "chain"):
                segs = chain.chain
            elif isinstance(chain, (list, tuple)):
                segs = chain
            else:
                segs = []
            for seg in segs:
                # 兼容不同的 Image 表示
                if isinstance(seg, dict):
                    if seg.get("type") == "image":
                        return seg.get("data", {}).get("url") or seg.get("data", {}).get("file", "")
                    continue
                if getattr(seg, "type", None) == "image":
                    return getattr(seg, "url", "") or getattr(seg, "file", "")
        except Exception as e:
            logger.error(f"提取图片URL失败: {e}")
        return ""

    def _build_text(self, text: str, at: str = None):
        if at:
            return [Plain(text), At(qq=at)] if text else [At(qq=at)]
        return [Plain(text)]

    async def _send(self, event: AstrMessageEvent, message_list):
        try:
            if hasattr(event, "send"):
                if MessageChain is not None:
                    await event.send(MessageChain(message_list))
                else:
                    await event.send(message_list)
                return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
        return False

    def _action_result_success(self, result) -> bool:
        """把 OneBot 调用返回值规整为布尔成功/失败。"""
        if result is None:
            return True
        if isinstance(result, bool):
            return result
        if isinstance(result, dict):
            status = str(result.get("status", "")).lower()
            if status in {"failed", "error"}:
                return False
            retcode = result.get("retcode")
            if retcode is not None:
                try:
                    return int(retcode) == 0
                except (TypeError, ValueError):
                    return False
            if status in {"ok", "async"}:
                return True
        return bool(result)

    async def _execute_action(self, event: AstrMessageEvent, action: str, return_raw: bool = False, **params):
        """调用 OneBot API。
        优先尝试 event.bot.call_action（AstrBot 推荐方式），
        其次 fallback 到 self.context.{action} 和 event.{action}。
        默认返回 True/False；return_raw=True 时返回 API 原始结果（用于查询类 API）。
        """
        # 参数转换：group_id / user_id / message_id 转为 int（OneBot 要求）
        for k in ("group_id", "user_id", "message_id"):
            if k in params and isinstance(params[k], str) and params[k].isdigit():
                params[k] = int(params[k])

        bot = getattr(event, "bot", None)
        if bot is not None:
            call = getattr(bot, "call_action", None)
            if callable(call):
                try:
                    result = await call(action, **params)
                    if return_raw:
                        return result
                    return self._action_result_success(result)
                except Exception as e:
                    logger.error(f"bot.call_action({action}) 失败: {e}")
            api = getattr(bot, "api", None)
            if api is not None:
                call = getattr(api, "call_action", None)
                if callable(call):
                    try:
                        result = await call(action, **params)
                        if return_raw:
                            return result
                        return self._action_result_success(result)
                    except Exception as e:
                        logger.error(f"bot.api.call_action({action}) 失败: {e}")
        handler = getattr(self.context, action, None)
        if callable(handler):
            try:
                result = await handler(**params)
                if return_raw:
                    return result
                return self._action_result_success(result)
            except Exception as e:
                logger.error(f"调用 {action} 失败: {e}")
        if hasattr(event, action):
            handler = getattr(event, action)
            if callable(handler):
                try:
                    result = await handler(**params)
                    if return_raw:
                        return result
                    return self._action_result_success(result)
                except Exception as e:
                    logger.error(f"调用 event.{action} 失败: {e}")
        return None if return_raw else False

    def _get_reply_id(self, event: AstrMessageEvent):
        """提取被引用/回复的消息 ID。优先从 message_obj，回退 raw message 字段。"""
        mo = getattr(event, "message_obj", None)
        if mo:
            for attr in ("reply_id", "quote_id"):
                v = getattr(mo, attr, None)
                if v:
                    return str(v)
        # 尝试从 raw message 的 segment 中找 Reply 类型
        raw = self._get_raw_message(event)
        if isinstance(raw, dict):
            for seg in raw.get("message", []) or []:
                if isinstance(seg, dict):
                    t = seg.get("type")
                    if t in ("reply", "quote"):
                        data = seg.get("data", {})
                        rid = data.get("id") or data.get("message_id")
                        if rid:
                            return str(rid)
                    if t == "text" and isinstance(seg.get("data", {}).get("text", ""), str):
                        # 部分 OneBot 引用消息嵌在 text 中
                        pass
        return None

    # ===================== OneBot API 封装 =====================

    async def _recall_message(self, event: AstrMessageEvent, message_id: str):
        """撤回消息。OneBot 标准 API 名为 delete_msg。"""
        return await self._execute_action(event, "delete_msg", message_id=message_id)

    async def _set_group_admin(self, event: AstrMessageEvent, group_id: str, qq: str, enable: bool):
        return await self._execute_action(event, "set_group_admin", group_id=group_id, user_id=qq, enable=enable)

    async def _set_group_title(self, event: AstrMessageEvent, group_id: str, qq: str, title: str):
        """设置群头衔。OneBot v11 set_group_special_title 接口。
        注意：不传 duration 参数（属于 set_group_ban 的参数，传了会导致 NapCatQQ 等静默失败）。
        """
        return await self._execute_action(event, "set_group_special_title",
                                          group_id=group_id, user_id=qq, special_title=title)

    async def _clear_group_title(self, event: AstrMessageEvent, group_id: str, qq: str) -> bool:
        """清空群头衔。每步调用后用 get_group_member_info 读回 title 字段校验
        是否真的清空，避免 OneBot 实现返回成功但实际未清空（#111 #119）。

        校验严格判断 title 是否为空字符串 / 字段缺失，不能 strip 后判空——
        否则单空格 " " 会被误判为已清空，导致实际仍存在空格头衔（#119）。
        """
        async def _verify() -> bool:
            info = await self._execute_action(
                event, "get_group_member_info", return_raw=True,
                group_id=group_id, user_id=qq, no_cache=True,
            )
            if isinstance(info, dict):
                data = info.get("data") or info
                after = data.get("title")
                if after is None:
                    after = data.get("special_title")
                # 严格判空：必须是空字符串或字段缺失；空格、不可见字符均视为未清空
                return after is None or after == ""
            return False

        # 1) duration=-1（部分实现要求的清空语义）
        ok1 = await self._execute_action(
            event, "set_group_special_title",
            group_id=group_id, user_id=qq,
            special_title="", duration=-1,
        )
        if ok1 and await _verify():
            return True
        # 2) 空字符串（不带 duration）
        ok2 = await self._execute_action(
            event, "set_group_special_title",
            group_id=group_id, user_id=qq, special_title="",
        )
        if ok2 and await _verify():
            return True
        # 3) 单空格兼容兜底：旧版 OneBot 拒绝空字符串时设置 " "。
        #    但需要校验：若 OneBot 实际把 " " 写回去了，#119 报告就是这种场景，
        #    此时不能视为成功；只有真正被解释为空（接口忽略空白）才算清空。
        ok3 = await self._execute_action(
            event, "set_group_special_title",
            group_id=group_id, user_id=qq, special_title=" ",
        )
        if ok3 and await _verify():
            return True
        return False

    # ===================== 群消息本地缓存（#117 #118） =====================

    def _record_recent_message(self, group_id: str, message_id, user_id):
        """记录一条群消息到本地缓存，供 /撤回 N / /撤回 @用户 N 在
        OneBot 不支持 get_group_msg_history 时作为回退数据源（#117 #118）。"""
        if not group_id or not message_id or user_id is None:
            return
        bucket = self.recent_messages.setdefault(str(group_id), deque(maxlen=100))
        bucket.append(
            {"message_id": str(message_id), "user_id": str(user_id)}
        )

    def _get_recent_messages_for_recall(self, group_id: str) -> list:
        """返回本地缓存中该群的最近消息列表，按从旧到新顺序排列
        （与 OneBot get_group_msg_history 的 messages 字段方向一致）。"""
        if not group_id:
            return []
        cache = self.recent_messages.get(str(group_id))
        if not cache:
            return []
        return list(cache)

    async def _set_group_card(self, event: AstrMessageEvent, group_id: str, qq: str, card: str):
        return await self._execute_action(event, "set_group_card",
                                          group_id=group_id, user_id=qq, card=card)

    async def _set_essence(self, event: AstrMessageEvent, message_id: str, group_id: str = None):
        """OneBot 标准 API 名为 set_essence_msg，部分实现也支持 set_essence。"""
        kwargs = {"message_id": message_id}
        if group_id is not None:
            kwargs["group_id"] = group_id
        # 优先尝试标准名 set_essence_msg，再回退 set_essence
        result = await self._execute_action(event, "set_essence_msg", **kwargs)
        if not result:
            result = await self._execute_action(event, "set_essence", **kwargs)
        return result

    async def _delete_essence(self, event: AstrMessageEvent, message_id: str, group_id: str = None):
        """取消精华消息。OneBot 标准 API 名为 delete_essence_msg。"""
        kwargs = {"message_id": message_id}
        if group_id is not None:
            kwargs["group_id"] = group_id
        result = await self._execute_action(event, "delete_essence_msg", **kwargs)
        if not result:
            result = await self._execute_action(event, "delete_essence", **kwargs)
        return result

    async def _mute_member(self, event: AstrMessageEvent, group_id: str, qq: str, duration_seconds: int):
        return await self._execute_action(event, "set_group_ban",
                                          group_id=group_id, user_id=qq, duration=duration_seconds)

    async def _unmute_member(self, event: AstrMessageEvent, group_id: str, qq: str):
        return await self._execute_action(event, "set_group_ban",
                                          group_id=group_id, user_id=qq, duration=0)

    async def _kick_member(self, event: AstrMessageEvent, group_id: str, qq: str):
        return await self._execute_action(event, "kick", group_id=group_id, user_id=qq)

    async def _set_group_avatar(self, event: AstrMessageEvent, group_id: str, file: str):
        """修改群头像，file 可以是 URL 或本地路径或 base64。"""
        return await self._execute_action(event, "set_group_portrait",
                                          group_id=group_id, file=file)

    async def _handle_group_request(self, event: AstrMessageEvent, flag: str, approve: bool, reason: str = ""):
        return await self._execute_action(event, "handle_group_request",
                                          flag=flag, approve=approve, reason=reason)

    # ===================== 消息收发辅助 =====================

    async def _send_private_msg(self, user_id: str, content: str):
        """向指定QQ号发送私聊消息（通过 context）。"""
        if hasattr(self.context, "send_private_msg"):
            try:
                return await self.context.send_private_msg(user_id=user_id, message=content)
            except Exception as e:
                logger.error(f"发送私聊失败: {e}")
        return False

    async def _send_group_text(self, event: AstrMessageEvent, group_id: str, text: str):
        """向指定群发送纯文本消息，返回 message_id（用于后续引用回复关联）。"""
        try:
            if hasattr(self.context, "send_group_msg"):
                # AstrBot 标准方法：send_group_msg(group_id=, message=)
                result = await self.context.send_group_msg(group_id=int(group_id), message=text)
                # 返回值可能直接是 message_id，也可能是含 message_id 的 dict
                if isinstance(result, dict):
                    return str(result.get("message_id") or result.get("data", {}).get("message_id", ""))
                return str(result) if result else ""
            # 回退：使用 _send 但拿不到 message_id
            await self._send(event, [Plain(text)])
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")
        return ""

    async def _get_user_nickname(self, event: AstrMessageEvent, user_id: str) -> str:
        """获取用户昵称（通过 OneBot get_stranger_info API）。"""
        try:
            handler = getattr(self.context, "get_stranger_info", None)
            if callable(handler):
                info = await handler(user_id=int(user_id))
                if isinstance(info, dict):
                    return info.get("nickname") or info.get("data", {}).get("nickname", user_id)
                if hasattr(info, "nickname"):
                    return info.nickname
        except Exception as e:
            logger.error(f"获取昵称失败: {e}")
        return user_id

    async def _notify_admins(self, text: str, group_id: str = ""):
        """向 join_notify_admins 配置的管理员发送私聊通知。"""
        for admin_id in self.get_group_setting(group_id, "join_notify_admins", []) or []:
            await self._send_private_msg(str(admin_id), text)

    # ===================== 计数统计（#29） =====================

    def _increment_message_count(self, group_id: str, user_id: str):
        groups = self.stats.setdefault("groups", {})
        g = groups.setdefault(str(group_id), {"messages": {}})
        msgs = g.setdefault("messages", {})
        msgs[str(user_id)] = msgs.get(str(user_id), 0) + 1

    def get_rank(self, group_id: str, top_n: int) -> list:
        groups = self.stats.get("groups", {})
        msgs = groups.get(str(group_id), {}).get("messages", {})
        ranked = sorted(msgs.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_n]

    def reset_group_stats(self, group_id: str):
        self.stats.setdefault("groups", {})[str(group_id)] = {"messages": {}}
        self.save_stats()

    async def _record_mute_and_maybe_kick(self, event: AstrMessageEvent, group_id: str, user_id: str, operator_id: str = ""):
        """记录被禁言次数，达到阈值后自动踢出。阈值为 0/空则关闭。"""
        try:
            threshold = int(self.get_group_setting(group_id, "mute_kick_threshold", 0) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold <= 0:
            return
        group_key = str(group_id)
        user_key = str(user_id)
        groups = self.stats.setdefault("groups", {})
        g = groups.setdefault(group_key, {"messages": {}})
        counts = g.setdefault("mute_counts", {})
        counts[user_key] = int(counts.get(user_key, 0)) + 1
        self.save_stats()
        if counts[user_key] >= threshold:
            ok = await self._kick_member(event, group_id, user_id)
            if ok:
                counts[user_key] = 0
                self.save_stats()
                await self._send(event, self._build_text(f"{user_id} 禁言次数达到 {threshold} 次，已自动踢出"))

    # ===================== 群违规检测（合并自 astrbot_plugin_group_moderation） =====================

    def _record_violation(self, group_id: str, user_id: str, kind: str):
        """把一次违规记录到 stats 中（持久化）。"""
        g = self.stats.setdefault("groups", {}).setdefault(str(group_id), {"messages": {}})
        counts = g.setdefault("violation_counts", {})
        bucket = counts.setdefault(kind, {})
        bucket[str(user_id)] = int(bucket.get(str(user_id), 0)) + 1
        self.save_stats()

    def _is_group_monitoring_enabled(self, group_id: str) -> bool:
        """群是否启用违规检测。
        优先级
        1. group_overrides[gid]["enabled_groups"] 为 bool 时，按 bool 决定
        2. top-level enabled_groups 列表：包含 * / all 表示全部；包含群号表示启用
        3. 兼容旧 violation_enabled_groups 列表
        """
        overrides = self.config.get("group_overrides", {}).get(str(group_id), {})
        v = overrides.get("enabled_groups")
        if isinstance(v, bool):
            return v
        enabled = self.config.get("enabled_groups", []) or []
        if not enabled:
            return False
        for x in enabled:
            sx = str(x).lower()
            if sx in ("*", "all"):
                return True
            if str(x) == str(group_id):
                return True
        legacy = self.config.get("violation_enabled_groups", []) or []
        return str(group_id) in [str(x) for x in legacy]

    def _is_user_whitelisted(self, group_id: str, user_id: str) -> bool:
        whitelist = self.get_group_setting(group_id, "whitelist_users", []) or []
        return str(user_id) in [str(x) for x in whitelist]

    def _moderation_admin_bypass(self, group_id: str, raw: dict) -> bool:
        if not self.get_group_setting(group_id, "admin_bypass", True):
            return False
        role = raw.get("sender", {}).get("role", "") if isinstance(raw, dict) else ""
        return role in {"admin", "owner"}

    def _moderation_ban_duration(self, group_id: str, kind: str) -> int:
        """按违规类型读取对应禁言时长（秒）。"""
        key_map = {
            "image": "ban_duration",
            "spam": "spam_ban_duration",
            "profanity": "profanity_ban_duration",
            "ad": "ad_ban_duration",
            "link": "link_ban_duration",
            "group_promotion": "group_promotion_ban_duration",
        }
        key = key_map.get(kind, "ban_duration")
        default_map = {
            "image": 600, "spam": 600, "profanity": 600,
            "ad": 600, "link": 600, "group_promotion": 600,
        }
        try:
            v = int(self.get_group_setting(group_id, key, default_map.get(kind, 600)) or 600)
        except (TypeError, ValueError):
            v = default_map.get(kind, 600)
        return max(1, v)

    async def _handle_violation(
        self,
        event: AstrMessageEvent,
        kind: str,
        group_id: str,
        user_id: str,
        message_id: str,
        reason: str = "",
    ) -> bool:
        """处理一条违规：撤回 + 按配置时长禁言 + 计数 + 通知。"""
        ok_any = False
        # 1. 撤回
        if message_id:
            recalled = await self._recall_message(event, str(message_id))
            ok_any = recalled
        # 2. 禁言
        duration = self._moderation_ban_duration(group_id, kind)
        muted = await self._mute_member(event, group_id, user_id, duration)
        if muted:
            ok_any = True
            # 复用现有的 mute_kick_threshold 计数
            await self._record_mute_and_maybe_kick(event, group_id, user_id, "moderation")
        # 3. 计数
        self._record_violation(group_id, user_id, kind)
        # 4. 通知
        if self.get_group_setting(group_id, "notify_on_violation", True):
            label_map = {
                "image": "违规图片", "spam": "刷屏", "profanity": "骂人",
                "ad": "广告", "link": "链接", "group_promotion": "群号推广",
            }
            label = label_map.get(kind, "违规")
            note = f"检测到{label}行为"
            if reason:
                note += f"（{reason}）"
            note += f"，已撤回并禁言 {duration} 秒。"
            await self._send(event, self._build_text(note))
        return ok_any

    async def _moderation_dispatch(self, event, raw, group_id: str, user_id: str) -> bool:
        """群消息违规检测总入口。"""
        if not self._is_group_monitoring_enabled(group_id):
            return False
        if self._is_user_whitelisted(group_id, user_id):
            return False
        if self._moderation_admin_bypass(group_id, raw):
            return False
        msg_text = self._extract_text(raw) if isinstance(raw, dict) else ""
        # 1) 刷屏（不依赖文本）
        if await self._check_spam(group_id, user_id):
            mid = str(raw.get("message_id", "")) if isinstance(raw, dict) else ""
            await self._handle_violation(event, "spam", group_id, user_id, mid)
            return True
        # 2) 文本类检测
        if msg_text:
            if await self._check_profanity(msg_text, event, group_id, user_id):
                mid = str(raw.get("message_id", "")) if isinstance(raw, dict) else ""
                await self._handle_violation(event, "profanity", group_id, user_id, mid)
                return True
            if await self._check_ad(msg_text, event, group_id, user_id):
                mid = str(raw.get("message_id", "")) if isinstance(raw, dict) else ""
                await self._handle_violation(event, "ad", group_id, user_id, mid)
                return True
            if await self._check_link(msg_text, event, group_id, user_id):
                mid = str(raw.get("message_id", "")) if isinstance(raw, dict) else ""
                await self._handle_violation(event, "link", group_id, user_id, mid)
                return True
            if await self._check_group_promotion(msg_text, event, group_id, user_id):
                mid = str(raw.get("message_id", "")) if isinstance(raw, dict) else ""
                await self._handle_violation(event, "group_promotion", group_id, user_id, mid)
                return True
        # 3) 图片检测
        image_urls = self._collect_image_urls(raw)
        for url in image_urls:
            violated, reason = await self._check_image(url)
            if violated:
                mid = str(raw.get("message_id", "")) if isinstance(raw, dict) else ""
                await self._handle_violation(event, "image", group_id, user_id, mid, reason)
                return True
        return False

    # ----- 图片检测 -----

    def _collect_image_urls(self, raw) -> list:
        urls = []
        if not isinstance(raw, dict):
            return urls
        for seg in raw.get("message", []) or []:
            if isinstance(seg, dict):
                if seg.get("type") == "image":
                    data = seg.get("data", {}) or {}
                    u = data.get("url") or data.get("file") or ""
                    if u and u not in urls:
                        urls.append(u)
        return urls

    async def _check_image(self, image_url: str):
        """调用 AI API 审核图片。返回 (is_violation, reason)。"""
        if aiohttp is None:
            logger.warning("[群违规检测] aiohttp 未安装，跳过图片审核")
            return False, ""
        api_endpoint = self.config.get("api_endpoint", "")
        api_key = self.config.get("api_key", "")
        api_type = self.config.get("api_type", "openai_vision")
        if not api_endpoint:
            return False, ""
        try:
            image_data = await self._download_image(image_url)
            if not image_data:
                return False, ""
            image_b64 = base64.b64encode(image_data).decode("utf-8")
            if api_type == "moderation":
                return await self._check_with_moderation_api(api_endpoint, api_key, image_b64)
            return await self._check_with_openai_vision(api_endpoint, api_key, image_b64)
        except Exception as e:
            logger.error(f"[群违规检测] 图片审核失败: {e}")
            return False, ""

    async def _check_with_openai_vision(self, api_endpoint: str, api_key: str, image_b64: str):
        model_name = self.config.get("model_name", "gpt-4o")
        prompt = self.config.get("detection_prompt") or (
            "请分析这张图片，判断是否包含违规内容（色情/擦边等）。"
            "请仅返回 JSON：{\"is_violation\": true/false, \"type\": \"porn/sexy/normal\", "
            "\"confidence\": 0.0-1.0, \"reason\": \"简短原因\"}"
        )
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]}],
            "max_tokens": 500,
            "temperature": 0.1,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession() as session:
                async with session.post(api_endpoint, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"[群违规检测] OpenAI Vision API 失败: {resp.status} {text[:200]}")
                        return False, ""
                    data = await resp.json()
            content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
            return self._parse_openai_response(content)
        except Exception as e:
            logger.error(f"[群违规检测] OpenAI Vision 调用失败: {e}")
            return False, ""

    def _parse_openai_response(self, content: str):
        if not content:
            return False, ""
        try:
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
            text = match.group() if match else content
            data = json.loads(text)
            is_violation = bool(data.get("is_violation", False))
            v_type = str(data.get("type", "normal")).lower()
            try:
                confidence = float(data.get("confidence", 0))
            except (TypeError, ValueError):
                confidence = 0.0
            reason = str(data.get("reason", ""))
            threshold = float(self.config.get("threshold", 0.7) or 0.7)
            check_porn = bool(self.config.get("check_porn", True))
            check_sexy = bool(self.config.get("check_sexy", True))
            if is_violation and confidence >= threshold:
                if v_type == "porn" and check_porn:
                    return True, f"检测到色情内容 (置信度: {confidence:.0%}) - {reason}"
                if v_type == "sexy" and check_sexy:
                    return True, f"检测到擦边内容 (置信度: {confidence:.0%}) - {reason}"
            return False, ""
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"[群违规检测] 解析 OpenAI 响应失败: {e}")
            return False, ""

    async def _check_with_moderation_api(self, api_endpoint: str, api_key: str, image_b64: str):
        payload = {"input": image_b64}
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.post(api_endpoint, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status != 200:
                        logger.error(f"[群违规检测] Moderation API 失败: {resp.status}")
                        return False, ""
                    data = await resp.json()
            results = data.get("results") or []
            if not results:
                return False, ""
            categories = results[0].get("categories", {}) or {}
            scores = results[0].get("category_scores", {}) or {}
            if categories.get("sexual"):
                return True, f"检测到性内容 (置信度: {scores.get('sexual', 0):.0%})"
            return False, ""
        except Exception as e:
            logger.error(f"[群违规检测] Moderation API 调用失败: {e}")
            return False, ""

    async def _download_image(self, url: str):
        if aiohttp is None:
            return None
        try:
            if url.startswith("http://") or url.startswith("https://"):
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=timeout) as resp:
                        if resp.status == 200:
                            return await resp.read()
            elif url.startswith("base64://"):
                return base64.b64decode(url[9:])
            elif url.startswith("file://"):
                with open(url[7:], "rb") as f:
                    return f.read()
            elif url and not url.startswith("http"):
                # 某些实现把图片作为本地路径返回
                try:
                    with open(url, "rb") as f:
                        return f.read()
                except OSError:
                    return None
        except Exception as e:
            logger.error(f"[群违规检测] 下载图片失败: {e}")
        return None

    # ----- 刷屏检测 -----

    async def _check_spam(self, group_id: str, user_id: str) -> bool:
        try:
            threshold = int(self.get_group_setting(group_id, "spam_threshold", 5) or 5)
            window = int(self.get_group_setting(group_id, "spam_time_window", 10) or 10)
        except (TypeError, ValueError):
            return False
        if not self.get_group_setting(group_id, "spam_check_enabled", True):
            return False
        if threshold <= 0 or window <= 0:
            return False
        now = time.time()
        key = f"{group_id}_{user_id}"
        records = self.spam_records[key]
        records[:] = [t for t in records if now - t < window]
        records.append(now)
        return len(records) >= threshold

    # ----- 骂人检测 -----

    async def _check_profanity(self, msg_text: str, event, group_id: str, user_id: str) -> bool:
        if not self.get_group_setting(group_id, "profanity_check_enabled", True):
            return False
        if not msg_text:
            return False
        use_ai = bool(self.get_group_setting(group_id, "profanity_use_ai", True))
        if use_ai and aiohttp is not None:
            api_endpoint = self.config.get("api_endpoint", "")
            api_key = self.config.get("api_key", "")
            if api_endpoint:
                is_profanity, reason = await self._check_profanity_with_ai(api_endpoint, api_key, msg_text)
                if is_profanity:
                    logger.warning(f"[群违规检测] 骂人 用户 {user_id} {reason}")
                    return True
                return False  # AI 模式下不再走关键词
        keywords = self.get_group_setting(group_id, "profanity_keywords", []) or []
        text_lower = msg_text.lower()
        for kw in keywords:
            if str(kw).lower() and str(kw).lower() in text_lower:
                return True
        return False

    async def _check_profanity_with_ai(self, api_endpoint: str, api_key: str, msg_text: str):
        model_name = self.config.get("model_name", "gpt-4o")
        prompt = (
            "你是严格的内容审核助手。请判断以下文本是否包含骂人、侮辱、人身攻击。\n"
            "请仅返回 JSON：{\"is_profanity\": true/false, \"reason\": \"简短原因\"}"
        )
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": f"{prompt}\n\n待检测文本：{msg_text}"}],
            "max_tokens": 200,
            "temperature": 0.1,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.post(api_endpoint, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status != 200:
                        logger.error(f"[群违规检测] 骂人 AI 失败: {resp.status}")
                        return False, ""
                    data = await resp.json()
            content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
            text = match.group() if match else content
            obj = json.loads(text)
            return bool(obj.get("is_profanity", False)), str(obj.get("reason", ""))
        except Exception as e:
            logger.error(f"[群违规检测] 骂人 AI 解析失败: {e}")
            return False, ""

    # ----- 广告 / 链接 / 群号推广 -----

    async def _check_ad(self, msg_text: str, event, group_id: str, user_id: str) -> bool:
        if not self.get_group_setting(group_id, "ad_check_enabled", True):
            return False
        if not msg_text:
            return False
        keywords = self.get_group_setting(group_id, "ad_keywords", []) or []
        text_lower = msg_text.lower()
        for kw in keywords:
            if str(kw).lower() and str(kw).lower() in text_lower:
                return True
        return False

    async def _check_link(self, msg_text: str, event, group_id: str, user_id: str) -> bool:
        if not self.get_group_setting(group_id, "link_check_enabled", False):
            return False
        if not msg_text:
            return False
        pattern = r"(https?://[^\s]+|www\.[^\s]+\.[^\s]+|[^\s]+\.(com|cn|net|org|io|xyz|top|vip|cc|me|tv|edu|gov)[^\s]*)"
        return re.search(pattern, msg_text, re.IGNORECASE) is not None

    async def _check_group_promotion(self, msg_text: str, event, group_id: str, user_id: str) -> bool:
        if not self.get_group_setting(group_id, "group_promotion_check_enabled", True):
            return False
        if not msg_text:
            return False
        promotion_keywords = ["进群", "加群", "群号", "入群", "拉群", "建群"]
        if not any(kw in msg_text for kw in promotion_keywords):
            return False
        group_pattern = r"[;；:,，\s]*(\d{5,12})"
        return bool(re.findall(group_pattern, msg_text))

    # ----- 群违规检测管理命令（仅插件管理员） -----

    def _moderation_require_admin(self, event):
        """校验消息发送者是否为插件管理员。是则返回 user_id，否则返回 None。"""
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            return None
        sender_id = str(raw.get("user_id", ""))
        if not self.is_plugin_admin(sender_id):
            return None
        return sender_id

    async def _moderation_require_admin_msg(self, event) -> bool:
        """校验插件管理员/群聊环境，不通过则发提示并返回 False。
        必须保持为普通 async 函数（不能 yield），否则 18 个调用点拿不到 bool。"""
        if self._moderation_require_admin(event) is not None:
            return True
        raw = self._get_raw_message(event)
        if raw and not raw.get("group_id"):
            await self._send(event, self._build_text("此指令只能在群聊中使用"))
            return False
        await self._send(event, self._build_text("只有插件管理员可执行此操作"))
        return False

    @filter.command("群违规检测状态", "查看群违规检测插件状态")
    async def moderation_status_cmd(self, event: AstrMessageEvent):
        if not await self._moderation_require_admin_msg(event):
            return
        api_type = self.config.get("api_type", "openai_vision")
        profanity_use_ai = self.config.get("profanity_use_ai", True)
        profanity_mode = "AI检测" if profanity_use_ai else "关键词检测"
        whitelist_users = self.config.get("whitelist_users", [])
        profanity_keywords = self.config.get("profanity_keywords", [])
        ad_keywords = self.config.get("ad_keywords", [])
        enabled_groups = self.config.get("enabled_groups", [])
        text = (
            "【群违规检测插件状态】\n"
            f"API 类型: {api_type}\n"
            f"API 站点: {self.config.get('api_endpoint', '') or '未配置'}\n"
            f"API Key: {'已配置' if self.config.get('api_key') else '未配置'}\n"
            f"模型: {self.config.get('model_name', 'gpt-4o')}\n"
            f"\n"
            f"监控群组: {enabled_groups if enabled_groups else '全部（需在群内启用 /设置群配置 enabled_groups true）'}\n"
            f"\n"
            f"【禁言时长（秒）】\n"
            f"图片: {self.config.get('ban_duration', 600)}\n"
            f"刷屏: {self.config.get('spam_ban_duration', 600)}\n"
            f"骂人: {self.config.get('profanity_ban_duration', 600)}\n"
            f"广告: {self.config.get('ad_ban_duration', 600)}\n"
            f"链接: {self.config.get('link_ban_duration', 600)}\n"
            f"群号推广: {self.config.get('group_promotion_ban_duration', 600)}\n"
            f"\n"
            f"【检测开关】\n"
            f"图片(色情/擦边): {self.config.get('check_porn', True)}/{self.config.get('check_sexy', True)}\n"
            f"刷屏: {self.config.get('spam_check_enabled', True)}（{self.config.get('spam_threshold', 5)} 条/{self.config.get('spam_time_window', 10)} 秒）\n"
            f"骂人: {self.config.get('profanity_check_enabled', True)}（{profanity_mode}, 关键词 {len(profanity_keywords)} 个）\n"
            f"广告: {self.config.get('ad_check_enabled', True)}（关键词 {len(ad_keywords)} 个）\n"
            f"链接: {self.config.get('link_check_enabled', False)}\n"
            f"群号推广: {self.config.get('group_promotion_check_enabled', True)}\n"
            f"\n"
            f"【其他】\n"
            f"白名单用户: {len(whitelist_users)} 人\n"
            f"管理员豁免: {self.config.get('admin_bypass', True)}\n"
            f"违规通知: {self.config.get('notify_on_violation', True)}\n"
            f"检测阈值: {self.config.get('threshold', 0.7)}"
        )
        yield event.plain_result(text)

    @filter.command("设置图片禁言时长", "设置图片违规禁言时长（秒）")
    async def set_image_ban_duration_cmd(self, event: AstrMessageEvent, seconds: int = 0):
        if not await self._moderation_require_admin_msg(event):
            return
        if seconds <= 0:
            yield event.plain_result("[错误] 禁言时长必须大于0秒")
            return
        self.config["ban_duration"] = seconds
        yield event.plain_result(f"[成功] 图片违规禁言时长已设置为 {seconds} 秒")

    @filter.command("设置刷屏禁言时长", "设置刷屏禁言时长（秒）")
    async def set_spam_ban_duration_cmd(self, event: AstrMessageEvent, seconds: int = 0):
        if not await self._moderation_require_admin_msg(event):
            return
        if seconds <= 0:
            yield event.plain_result("[错误] 禁言时长必须大于0秒")
            return
        self.config["spam_ban_duration"] = seconds
        yield event.plain_result(f"[成功] 刷屏禁言时长已设置为 {seconds} 秒")

    @filter.command("设置骂人禁言时长", "设置骂人禁言时长（秒）")
    async def set_profanity_ban_duration_cmd(self, event: AstrMessageEvent, seconds: int = 0):
        if not await self._moderation_require_admin_msg(event):
            return
        if seconds <= 0:
            yield event.plain_result("[错误] 禁言时长必须大于0秒")
            return
        self.config["profanity_ban_duration"] = seconds
        yield event.plain_result(f"[成功] 骂人禁言时长已设置为 {seconds} 秒")

    @filter.command("添加骂人关键词", "添加骂人关键词（关键词检测模式）")
    async def add_profanity_keyword_cmd(self, event: AstrMessageEvent, keyword: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("[错误] 请提供关键词")
            return
        kws = self.config.setdefault("profanity_keywords", [])
        if keyword in kws:
            yield event.plain_result(f"[错误] 关键词 '{keyword}' 已存在")
            return
        kws.append(keyword)
        self.config["profanity_keywords"] = kws
        yield event.plain_result(f"[成功] 已添加骂人关键词 '{keyword}'（当前 {len(kws)} 个）")

    @filter.command("删除骂人关键词", "删除骂人关键词")
    async def remove_profanity_keyword_cmd(self, event: AstrMessageEvent, keyword: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("[错误] 请提供关键词")
            return
        kws = self.config.get("profanity_keywords", [])
        if keyword not in kws:
            yield event.plain_result(f"[错误] 关键词 '{keyword}' 不存在")
            return
        kws.remove(keyword)
        self.config["profanity_keywords"] = kws
        yield event.plain_result(f"[成功] 已删除骂人关键词 '{keyword}'（当前 {len(kws)} 个）")

    @filter.command("查看骂人关键词", "查看骂人关键词列表")
    async def list_profanity_keywords_cmd(self, event: AstrMessageEvent):
        if not await self._moderation_require_admin_msg(event):
            return
        kws = self.config.get("profanity_keywords", [])
        if not kws:
            yield event.plain_result("当前没有设置骂人关键词")
            return
        listing = "\n".join([f"{i+1}. {kw}" for i, kw in enumerate(kws)])
        yield event.plain_result(f"骂人关键词列表（{len(kws)} 个）：\n{listing}")

    @filter.command("切换骂人检测模式", "切换 AI 检测 / 关键词检测")
    async def toggle_profanity_mode_cmd(self, event: AstrMessageEvent):
        if not await self._moderation_require_admin_msg(event):
            return
        cur = bool(self.config.get("profanity_use_ai", True))
        self.config["profanity_use_ai"] = not cur
        mode = "AI检测" if not cur else "关键词检测"
        yield event.plain_result(f"[成功] 已切换为 {mode} 模式")

    @filter.command("添加白名单用户", "添加白名单用户（不受违规检测限制）")
    async def add_whitelist_user_cmd(self, event: AstrMessageEvent, user_id: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        user_id = str(user_id).strip()
        if not user_id:
            yield event.plain_result("[错误] 请提供QQ号")
            return
        wl = self.config.setdefault("whitelist_users", [])
        if user_id in [str(x) for x in wl]:
            yield event.plain_result(f"[错误] 用户 {user_id} 已在白名单中")
            return
        wl.append(user_id)
        self.config["whitelist_users"] = wl
        yield event.plain_result(f"[成功] 已添加 {user_id} 到白名单（当前 {len(wl)} 人）")

    @filter.command("删除白名单用户", "从白名单移除用户")
    async def remove_whitelist_user_cmd(self, event: AstrMessageEvent, user_id: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        user_id = str(user_id).strip()
        if not user_id:
            yield event.plain_result("[错误] 请提供QQ号")
            return
        wl = self.config.get("whitelist_users", [])
        new_wl = [u for u in wl if str(u) != user_id]
        if len(new_wl) == len(wl):
            yield event.plain_result(f"[错误] 用户 {user_id} 不在白名单中")
            return
        self.config["whitelist_users"] = new_wl
        yield event.plain_result(f"[成功] 已从白名单移除 {user_id}（当前 {len(new_wl)} 人）")

    @filter.command("查看白名单", "查看白名单用户列表")
    async def list_whitelist_cmd(self, event: AstrMessageEvent):
        if not await self._moderation_require_admin_msg(event):
            return
        wl = self.config.get("whitelist_users", [])
        if not wl:
            yield event.plain_result("当前白名单为空")
            return
        listing = "\n".join([f"{i+1}. {u}" for i, u in enumerate(wl)])
        yield event.plain_result(f"白名单用户（{len(wl)} 人）：\n{listing}")

    @filter.command("查看违规统计", "查看违规统计（默认全群；带 QQ 号查个人）")
    async def view_violation_stats_cmd(self, event: AstrMessageEvent, user_id: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        user_id = (user_id or "").strip()
        if user_id:
            g = self.stats.get("groups", {}).get(str(user_id), {})  # 简化：user_id 当群号查
            counts = g.get("violation_counts", {})
            total = sum(sum(b.values()) for b in counts.values())
            yield event.plain_result(
                f"群 {user_id} 违规统计:\n"
                f"图片: {sum(counts.get('image', {}).values())} 次\n"
                f"刷屏: {sum(counts.get('spam', {}).values())} 次\n"
                f"骂人: {sum(counts.get('profanity', {}).values())} 次\n"
                f"广告: {sum(counts.get('ad', {}).values())} 次\n"
                f"链接: {sum(counts.get('link', {}).values())} 次\n"
                f"群号推广: {sum(counts.get('group_promotion', {}).values())} 次\n"
                f"总计: {total} 次"
            )
        else:
            groups = self.stats.get("groups", {})
            total_users = 0
            total_violations = 0
            for g in groups.values():
                for bucket in g.get("violation_counts", {}).values():
                    total_users += len(bucket)
                    total_violations += sum(bucket.values())
            yield event.plain_result(
                f"违规统计概览:\n违规用户数: {total_users} 人\n总违规次数: {total_violations} 次"
            )

    @filter.command("设置广告禁言时长", "设置广告禁言时长（秒）")
    async def set_ad_ban_duration_cmd(self, event: AstrMessageEvent, seconds: int = 0):
        if not await self._moderation_require_admin_msg(event):
            return
        if seconds <= 0:
            yield event.plain_result("[错误] 禁言时长必须大于0秒")
            return
        self.config["ad_ban_duration"] = seconds
        yield event.plain_result(f"[成功] 广告禁言时长已设置为 {seconds} 秒")

    @filter.command("设置链接禁言时长", "设置链接禁言时长（秒）")
    async def set_link_ban_duration_cmd(self, event: AstrMessageEvent, seconds: int = 0):
        if not await self._moderation_require_admin_msg(event):
            return
        if seconds <= 0:
            yield event.plain_result("[错误] 禁言时长必须大于0秒")
            return
        self.config["link_ban_duration"] = seconds
        yield event.plain_result(f"[成功] 链接禁言时长已设置为 {seconds} 秒")

    @filter.command("设置群号推广禁言时长", "设置群号推广禁言时长（秒）")
    async def set_group_promotion_ban_duration_cmd(self, event: AstrMessageEvent, seconds: int = 0):
        if not await self._moderation_require_admin_msg(event):
            return
        if seconds <= 0:
            yield event.plain_result("[错误] 禁言时长必须大于0秒")
            return
        self.config["group_promotion_ban_duration"] = seconds
        yield event.plain_result(f"[成功] 群号推广禁言时长已设置为 {seconds} 秒")

    @filter.command("添加广告关键词", "添加广告关键词")
    async def add_ad_keyword_cmd(self, event: AstrMessageEvent, keyword: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("[错误] 请提供关键词")
            return
        kws = self.config.setdefault("ad_keywords", [])
        if keyword in kws:
            yield event.plain_result(f"[错误] 关键词 '{keyword}' 已存在")
            return
        kws.append(keyword)
        self.config["ad_keywords"] = kws
        yield event.plain_result(f"[成功] 已添加广告关键词 '{keyword}'（当前 {len(kws)} 个）")

    @filter.command("删除广告关键词", "删除广告关键词")
    async def remove_ad_keyword_cmd(self, event: AstrMessageEvent, keyword: str = ""):
        if not await self._moderation_require_admin_msg(event):
            return
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("[错误] 请提供关键词")
            return
        kws = self.config.get("ad_keywords", [])
        if keyword not in kws:
            yield event.plain_result(f"[错误] 关键词 '{keyword}' 不存在")
            return
        kws.remove(keyword)
        self.config["ad_keywords"] = kws
        yield event.plain_result(f"[成功] 已删除广告关键词 '{keyword}'（当前 {len(kws)} 个）")

    @filter.command("查看广告关键词", "查看广告关键词列表")
    async def list_ad_keywords_cmd(self, event: AstrMessageEvent):
        if not await self._moderation_require_admin_msg(event):
            return
        kws = self.config.get("ad_keywords", [])
        if not kws:
            yield event.plain_result("当前没有设置广告关键词")
            return
        head = "\n".join([f"{i+1}. {kw}" for i, kw in enumerate(kws[:20])])
        more = f"\n…还有 {len(kws) - 20} 个" if len(kws) > 20 else ""
        yield event.plain_result(f"广告关键词（{len(kws)} 个）：\n{head}{more}")

    async def _edit_special_admins(self, event: AstrMessageEvent, target: str, key: str, label: str, add: bool):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            action = "添加" if add else "删除"
            yield event.plain_result(f"请提供QQ号，例如 /{action}{label}管理 123456")
            return
        if add:
            changed = self._add_group_override_admins(group_id, key, qq_list)
            verb = "添加"
            empty = "所列QQ号均已存在"
        else:
            changed = self._remove_group_override_admins(group_id, key, qq_list)
            verb = "移除"
            empty = "所列QQ号均不存在"
        detail = ", ".join(changed) if changed else empty
        yield event.plain_result(f"已为群 {group_id} {verb}{label}专项管理员: {detail}")

    # ===================== 群管指令 =====================

    @filter.command("设管", "添加插件管理员（支持批量）")
    async def add_plugin_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = _parse_qq_list(target)
        # 也可从At组件提取
        at_qq = self._extract_at_qq(raw)
        if at_qq:
            qq_list.append(at_qq)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result("请提供QQ号，例如 /设管 123456 234567")
            return
        added = []
        for qq in qq_list:
            if qq not in [str(x) for x in self.config.get("plugin_admins", [])]:
                self.config.setdefault("plugin_admins", []).append(qq)
                added.append(qq)
        self.save_config()
        if added:
            yield event.plain_result(f"已添加插件管理员: {', '.join(added)}")
        else:
            yield event.plain_result("所列QQ号均已是插件管理员")

    @filter.command("取管", "移除插件管理员（支持批量）")
    async def remove_plugin_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result("请通过 @某人 或QQ号指定，例如 /取管 @某人")
            return
        removed = []
        for qq in qq_list:
            if qq in [str(x) for x in self.config.get("plugin_admins", [])]:
                self.config["plugin_admins"].remove(qq)
                removed.append(qq)
        self.save_config()
        if removed:
            yield event.plain_result(f"已移除插件管理员: {', '.join(removed)}")
        else:
            yield event.plain_result("所列QQ号均非插件管理员")

    @filter.command("添加插件管理", "按群添加专项权限管理员（兼容旧命令）")
    async def add_group_admin(self, event: AstrMessageEvent, target: str = ""):
        """兼容旧命令：按群添加插件管理员已废弃，改为按群添加专项权限管理员。"""
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result(
                "按群插件管理已改为专项权限配置。\n"
                "请使用：/添加头衔管理 QQ、/添加管理管理 QQ、/添加踢人管理 QQ"
            )
            return
        added = []
        for key in ("title_admins", "group_admin_admins", "kick_admins"):
            added.extend(self._add_group_override_admins(group_id, key, qq_list))
        yield event.plain_result(
            "已按群添加专项权限管理员: " + (", ".join(sorted(set(added))) if added else "所列QQ号均已存在")
        )

    @filter.command("删除插件管理", "按群移除专项权限管理员（兼容旧命令）")
    async def remove_group_admin(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        qq_list = list({str(x) for x in qq_list if x})
        if not qq_list:
            yield event.plain_result(
                "按群插件管理已改为专项权限配置。\n"
                "请使用：/删除头衔管理 QQ、/删除管理管理 QQ、/删除踢人管理 QQ"
            )
            return
        removed = []
        for key in ("title_admins", "group_admin_admins", "kick_admins"):
            removed.extend(self._remove_group_override_admins(group_id, key, qq_list))
        yield event.plain_result(
            "已按群移除专项权限管理员: " + (", ".join(sorted(set(removed))) if removed else "所列QQ号均不存在")
        )

    @filter.command("添加头衔管理", "按群添加可设置/取消头衔的专项管理员")
    async def add_title_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        async for result in self._edit_special_admins(event, target, "title_admins", "头衔", True):
            yield result

    @filter.command("删除头衔管理", "按群移除可设置/取消头衔的专项管理员")
    async def remove_title_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        async for result in self._edit_special_admins(event, target, "title_admins", "头衔", False):
            yield result

    @filter.command("添加管理管理", "按群添加可设置/取消群管理的专项管理员")
    async def add_group_admin_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        async for result in self._edit_special_admins(event, target, "group_admin_admins", "群管理", True):
            yield result

    @filter.command("删除管理管理", "按群移除可设置/取消群管理的专项管理员")
    async def remove_group_admin_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        async for result in self._edit_special_admins(event, target, "group_admin_admins", "群管理", False):
            yield result

    @filter.command("添加踢人管理", "按群添加可踢人的专项管理员")
    async def add_kick_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        async for result in self._edit_special_admins(event, target, "kick_admins", "踢人", True):
            yield result

    @filter.command("删除踢人管理", "按群移除可踢人的专项管理员")
    async def remove_kick_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        async for result in self._edit_special_admins(event, target, "kick_admins", "踢人", False):
            yield result

    @filter.command("设管理", "设置群管理员（支持批量+@）")
    async def set_group_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.has_group_admin_rights(str(raw.get("user_id")), group_id, raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        if not qq_list:
            yield event.plain_result("请通过 @某人 或QQ号指定目标")
            return
        results = []
        for qq in qq_list:
            ok = await self._set_group_admin(event, group_id, qq, True)
            results.append((qq, ok))
        ok_list = [q for q, ok in results if ok]
        bad_list = [q for q, ok in results if not ok]
        msg = f"设置群管理成功: {', '.join(ok_list)}" if ok_list else "设置群管理全部失败"
        if bad_list:
            msg += f"\n失败: {', '.join(bad_list)}"
        yield event.plain_result(msg)

    @filter.command("取消管理", "取消群管理员（支持批量+@；管理员可取消自己）")
    async def unset_group_admin_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        if not qq_list:
            qq_list = [sender_id]
        qq_list = list({str(x) for x in qq_list if x})
        self_cancel = len(qq_list) == 1 and qq_list[0] == sender_id and self._is_sender_group_admin_only(raw)
        if not self.has_group_admin_rights(sender_id, group_id, raw) and not self_cancel:
            yield event.plain_result("只有插件管理员、群管理员或被取消者本人可执行此操作")
            return
        results = []
        for qq in qq_list:
            ok = await self._set_group_admin(event, group_id, qq, False)
            results.append((qq, ok))
        ok_list = [q for q, ok in results if ok]
        bad_list = [q for q, ok in results if not ok]
        msg = f"取消群管理成功: {', '.join(ok_list)}" if ok_list else "取消群管理全部失败"
        if bad_list:
            msg += f"\n失败: {', '.join(bad_list)}"
        yield event.plain_result(msg)

    @filter.command("头衔", "设置群头衔（@某人 头衔内容）")
    async def set_group_title_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_title_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员、头衔管理员或群管理员可执行此操作")
            return
        target_qq = self._extract_at_qq(raw)
        if not target_qq:
            target_qq = sender_id  # 操作对象为空时对自身（允许群管理员自设头衔）
        # 从 raw 消息提取所有 text 拼接，去掉命令前缀，得到完整头衔
        title = self._extract_text(raw).strip()
        for prefix in ("/头衔", "头衔"):
            if title.startswith(prefix):
                title = title[len(prefix):].lstrip()
                break
        # 去掉开头的 @ 提及占位（如果 AstrBot 在 text 中保留了 @xxx）
        import re as _re
        title = _re.sub(r"^@[\w（）()\d]+\s*", "", title)
        if not title:
            yield event.plain_result("请提供群头衔内容")
            return
        ok = await self._set_group_title(event, group_id, target_qq, title)
        yield event.plain_result("设置头衔成功" if ok else "设置头衔失败")

    @filter.command("取消头衔", "取消群头衔")
    async def unset_group_title_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        target_qq = self._extract_at_qq(raw) or self._parse_qq(target) or sender_id
        self_cancel = target_qq == sender_id and self._sender_has_special_title(raw)
        if not self.has_title_admin_rights(sender_id, group_id, raw) and not self_cancel:
            yield event.plain_result("只有插件管理员、头衔管理员、群管理员或有头衔者本人可执行此操作")
            return
        ok = await self._clear_group_title(event, group_id, target_qq)
        if ok:
            yield event.plain_result("取消头衔成功")
        else:
            yield event.plain_result(
                f"取消头衔失败：群 {group_id} 用户 {target_qq} 头衔清除后仍被读到。\n"
                "可能原因：Bot 权限不足 / 头衔由群主设置且不可由 Bot 修改。\n"
                "请确认 Bot 仍为群管理员并拥有设置头衔的权限。"
            )

    # #18: 别人昵称 - 设置他人的群昵称
    @filter.command("别人昵称", "设置他人群昵称（需要 @某人 + 新昵称）")
    async def set_other_card_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_group_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        target_qq = self._extract_at_qq(raw)
        if not target_qq:
            yield event.plain_result("请通过 @某人 来指定对象")
            return
        # 从原始消息提取所有 text 段拼接为 card（避免被 @ 组件挤掉）
        card = self._extract_text(raw).strip()
        # 去掉开头的 /别人昵称 命令名（如果存在）
        for prefix in ("/别人昵称", "别人昵称"):
            if card.startswith(prefix):
                card = card[len(prefix):].lstrip()
                break
        if not card:
            yield event.plain_result("请提供新昵称内容")
            return
        ok = await self._set_group_card(event, group_id, target_qq, card)
        yield event.plain_result(f"已将 {target_qq} 的群昵称设为 {card}" if ok else "设置群昵称失败")

    # #18: 改群昵称 - 设置自己的群昵称
    @filter.command("改群昵称", "设置自己的群昵称")
    async def set_self_card_cmd(self, event: AstrMessageEvent, card: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not card:
            yield event.plain_result("请提供新昵称内容")
            return
        ok = await self._set_group_card(event, group_id, sender_id, card)
        yield event.plain_result(f"已将你的群昵称设为 {card}" if ok else "设置群昵称失败")

    @filter.command("禁言", "禁言成员")
    async def mute_cmd(self, event: AstrMessageEvent, target: str = "", minutes: int = 10):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(sender_id) and not self._is_group_admin(raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要禁言的QQ号")
            return
        target_stripped = (target or "").strip()
        if target_stripped.isdigit():
            try:
                minutes = int(target_stripped)
            except ValueError:
                pass
        ok = await self._mute_member(event, group_id, qq, minutes * 60)
        if ok:
            await self._record_mute_and_maybe_kick(event, group_id, qq, sender_id)
        if self._should_notify_mute(ok):
            yield event.plain_result(f"禁言成功（{minutes}分钟）" if ok else "禁言失败")

    @filter.command("解禁", "解除禁言")
    async def unmute_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        if not self.is_plugin_admin(sender_id) and not self._is_group_admin(raw):
            yield event.plain_result("只有插件管理员或群管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请指定要解禁的QQ号")
            return
        ok = await self._unmute_member(event, group_id, qq)
        if self._should_notify_mute(ok):
            yield event.plain_result("解禁成功" if ok else "解禁失败")

    @filter.command("踢", "踢出群成员（支持批量+@）")
    async def kick_cmd(self, event: AstrMessageEvent, target: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self.has_kick_admin_rights(sender_id, group_id, raw):
            yield event.plain_result("只有插件管理员、踢人管理员或群管理员可执行此操作")
            return
        qq_list = self._extract_at_qqs(raw) or _parse_qq_list(target)
        if not qq_list:
            yield event.plain_result("请通过 @某人 或QQ号指定目标")
            return
        results = []
        for qq in qq_list:
            ok = await self._kick_member(event, group_id, qq)
            if ok and self.config.get("reject_re_add", False):
                await self._execute_action(event, "reject_add", group_id=group_id, user_id=qq)
            results.append((qq, ok))
        ok_list = [q for q, ok in results if ok]
        bad_list = [q for q, ok in results if not ok]
        msg = f"踢出成功: {', '.join(ok_list)}" if ok_list else "踢出全部失败"
        if bad_list:
            msg += f"\n失败: {', '.join(bad_list)}"
        yield event.plain_result(msg)

    @filter.command("撤回", "撤回消息（/撤回 + 引用消息 / /撤回 @用户 N / /撤回 N）")
    async def recall_cmd(self, event: AstrMessageEvent, count: str = ""):
        """统一分发器（#109 #110）：
        - 引用消息 -> 撤回引用消息
        - @用户 + N -> 撤回该用户最近 N 条
        - 仅有 N -> 撤回最近 N 条（不含指令本身）
        """
        try:
            count = int(count) if count else 0
        except (TypeError, ValueError):
            count = 0
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin(raw) and not self._is_group_owner(raw) and not self.is_plugin_admin(str(raw.get("user_id", ""))):
            yield event.plain_result("只有群管理员或群主可执行此操作")
            return

        reply_id = self._get_reply_id(event)
        target_qq = self._extract_at_qq(raw)
        self_msg_id = str(raw.get("message_id", "")) if raw.get("message_id") else ""

        # 1) 引用消息优先
        if reply_id:
            ok = await self._recall_message(event, reply_id)
            if ok and self.get_group_setting(group_id, "show_recall_notice", True):
                await self._send(event, self._build_text("已撤回该消息"))
            yield event.plain_result("撤回成功" if ok else "撤回失败")
            return

        # 2) @用户 + N（#110 #117）
        if target_qq:
            n = max(1, min(count or 1, 50))
            history = await self._execute_action(
                event, "get_group_msg_history", return_raw=True,
                group_id=group_id, message_id=None,
            )
            msgs = []
            if isinstance(history, dict):
                msgs = history.get("data", {}).get("messages") or history.get("messages") or []
            # 历史接口不可用时回退到本地缓存（#117）
            used_cache = False
            if not msgs:
                msgs = self._get_recent_messages_for_recall(group_id)
                used_cache = bool(msgs)
            if not msgs:
                yield event.plain_result(
                    "当前 OneBot 实现不支持按用户撤回（缺少 get_group_msg_history，且插件本地缓存为空）。\n"
                    "请使用 /撤回 + 引用消息 撤回指定消息。"
                )
                return
            candidates = [m for m in msgs if str(m.get("user_id")) == str(target_qq)][:n]
            recalled = 0
            for m in candidates:
                mid = m.get("message_id")
                if mid and str(mid) != self_msg_id and await self._recall_message(event, str(mid)):
                    recalled += 1
            if recalled:
                if self.get_group_setting(group_id, "show_recall_notice", True):
                    suffix = "（来自本地缓存）" if used_cache else ""
                    await self._send(event, self._build_text(f"已撤回用户 {target_qq} 的 {recalled} 条消息{suffix}"))
                yield event.plain_result(f"撤回成功（{recalled} 条）")
            else:
                yield event.plain_result("撤回失败，未找到该用户的可撤回消息")
            return

        # 3) 仅 N：撤回最近 N 条（#109，不撤回指令本身；#118 提供本地缓存回退）
        if count > 0:
            history = await self._execute_action(
                event, "get_group_msg_history", return_raw=True,
                group_id=group_id, message_id=None,
            )
            msgs = []
            if isinstance(history, dict):
                msgs = history.get("data", {}).get("messages") or history.get("messages") or []
            used_cache = False
            if not msgs:
                msgs = self._get_recent_messages_for_recall(group_id)
                used_cache = bool(msgs)
            if not msgs:
                yield event.plain_result(
                    "撤回失败：当前 OneBot 实现不支持 get_group_msg_history，且插件本地缓存为空。\n"
                    "请使用 /撤回 + 引用消息 撤回指定消息。"
                )
                return
            seen = {self_msg_id} if self_msg_id else set()
            recalled = 0
            for m in msgs:
                if recalled >= count:
                    break
                mid = m.get("message_id")
                if not mid or str(mid) in seen:
                    continue
                seen.add(str(mid))
                if await self._recall_message(event, str(mid)):
                    recalled += 1
            if recalled:
                if self.get_group_setting(group_id, "show_recall_notice", True):
                    suffix = "（来自本地缓存）" if used_cache else ""
                    await self._send(event, self._build_text(f"已撤回 {recalled} 条消息{suffix}"))
                yield event.plain_result(f"撤回成功（{recalled} 条）")
            else:
                yield event.plain_result("撤回失败，未找到可撤回消息")
            return

        # 4) 用法提示
        yield event.plain_result(
            "用法：\n"
            "/撤回 + 引用消息：撤回引用消息\n"
            "/撤回 @用户 N：撤回该用户最近 N 条（最多 50）\n"
            "/撤回 N：撤回最近 N 条（不含指令本身）"
        )

    @filter.command("设精", "设置精华消息")
    async def essence_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self._is_group_admin(raw) and not self._is_group_owner(raw):
            yield event.plain_result("只有群管理员或群主可执行此操作")
            return
        reply_id = self._get_reply_id(event)
        if not reply_id:
            yield event.plain_result("请引用一条消息后使用该指令")
            return
        ok = await self._set_essence(event, reply_id, group_id=str(raw.get("group_id")))
        yield event.plain_result("设精成功" if ok else "设精失败")

    @filter.command("取消设精", "取消精华消息")
    async def cancel_essence_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self._is_group_admin(raw) and not self._is_group_owner(raw):
            yield event.plain_result("只有群管理员或群主可执行此操作")
            return
        reply_id = self._get_reply_id(event)
        if not reply_id:
            yield event.plain_result("请引用一条精华消息后使用该指令")
            return
        ok = await self._delete_essence(event, reply_id, group_id=str(raw.get("group_id")))
        yield event.plain_result("取消设精成功" if ok else "取消设精失败")

    # #24: 改群头像
    @filter.command("改群头像", "引用图片回复即可修改群头像")
    async def set_group_avatar_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        image_url = self._extract_image_url(event)
        if not image_url:
            yield event.plain_result("请引用一条图片消息，或在消息中附带图片")
            return
        ok = await self._set_group_avatar(event, group_id, image_url)
        yield event.plain_result("群头像已更新" if ok else "修改群头像失败")

    # #79: 宵禁 - 全体禁言
    @filter.command("宵禁", "开启全群禁言")
    async def whole_ban_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        ok = await self._execute_action(event, "set_group_whole_ban",
                                        group_id=group_id, enable=True)
        if self._should_notify_mute(ok):
            yield event.plain_result("已开启全群禁言" if ok else "开启失败")

    # #79: 解除宵禁 - 解除全体禁言
    @filter.command("解除宵禁", "关闭全群禁言")
    async def unwhole_ban_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        ok = await self._execute_action(event, "set_group_whole_ban",
                                        group_id=group_id, enable=False)
        if self._should_notify_mute(ok):
            yield event.plain_result("已解除全群禁言" if ok else "解除失败")

    # #75: 禁我 [分钟] - 任意成员禁言自己
    @filter.command("禁我", "禁言自己，格式：/禁我 [分钟]，默认10分钟")
    async def mute_self_cmd(self, event: AstrMessageEvent, minutes: int = 10):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        minutes = max(1, min(int(minutes), 43200))  # 限制 1 分钟 ~ 30 天
        ok = await self._mute_member(event, group_id, sender_id, minutes * 60)
        if self._should_notify_mute(ok):
            yield event.plain_result(f"已禁言自己 {minutes} 分钟" if ok else "禁言失败")

    # #76: 群昵称 新昵称 - 插件管理员修改任意成员昵称
    @filter.command("群昵称", "设置指定成员群昵称（仅插件管理员）")
    async def set_member_card_cmd(self, event: AstrMessageEvent, target: str = "", card: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw) or self._parse_qq(target)
        if not qq:
            yield event.plain_result("请通过 @某人 或提供QQ号")
            return
        if not card:
            yield event.plain_result("请提供新昵称内容")
            return
        ok = await self._set_group_card(event, group_id, qq, card)
        yield event.plain_result(f"已将 {qq} 群昵称设为 {card}" if ok else "设置群昵称失败")

    # #16: 群公告
    @filter.command("发群公告", "发送群公告")
    async def send_group_notice_cmd(self, event: AstrMessageEvent, content: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        if not content:
            yield event.plain_result("请提供公告内容")
            return
        # 尝试通过 send_group_notice / _send_group_notice API
        ok = await self._execute_action(event, "_send_group_notice",
                                        group_id=group_id, content=content)
        if not ok:
            ok = await self._execute_action(event, "send_group_notice",
                                            group_id=group_id, content=content)
        if ok:
            yield event.plain_result("群公告已发布")
        else:
            # 退化为普通消息提示
            await self._send(event, [Plain(f"[群公告] {content}")])
            yield event.plain_result("当前框架不支持发群公告，已以普通消息发送")

    @filter.command("删群公告", "删除群公告")
    async def delete_group_notice_cmd(self, event: AstrMessageEvent, notice_id: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        if not notice_id:
            yield event.plain_result("请提供要删除的公告ID，例如 /删群公告 12345")
            return
        ok = await self._execute_action(event, "_delete_group_notice",
                                        group_id=group_id, notice_id=notice_id)
        if not ok:
            ok = await self._execute_action(event, "delete_group_notice",
                                            group_id=group_id, notice_id=notice_id)
        yield event.plain_result("群公告已删除" if ok else "删除群公告失败")

    # #29: 鞭尸禁言 + 发言排名
    @filter.command("鞭尸", "长期禁言被@的人（29天23小时59分）")
    async def whip_corpse_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        qq = self._extract_at_qq(raw)
        if not qq:
            yield event.plain_result("请 @要鞭尸的成员")
            return
        # 29天23小时59分 = 29*86400 + 23*3600 + 59*60 = 2591640 秒
        duration = 29 * 86400 + 23 * 3600 + 59 * 60
        ok = await self._mute_member(event, group_id, qq, duration)
        if ok:
            await self._record_mute_and_maybe_kick(event, group_id, qq, sender_id)
        yield event.plain_result("已鞭尸" if ok else "鞭尸失败")

    @filter.command("排名", "查看本群发言排名")
    async def rank_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        top_n = int(self.config.get("rank_top_n", 10))
        ranked = self.get_rank(group_id, top_n)
        if not ranked:
            yield event.plain_result("暂无发言数据")
            return
        lines = [f"{i+1}. {qq} - {cnt}条" for i, (qq, cnt) in enumerate(ranked)]
        yield event.plain_result(f"本群发言排名（Top {len(ranked)}）：\n" + "\n".join(lines))

    @filter.command("清除数据", "清除本群发言计数")
    async def clear_rank_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        sender_id = str(raw.get("user_id"))
        group_id = str(raw.get("group_id"))
        if not self._is_group_admin_or_owner(raw) and not self.is_plugin_admin(sender_id):
            yield event.plain_result("只有群管理员或插件管理员可执行此操作")
            return
        self.reset_group_stats(group_id)
        yield event.plain_result("已清除本群发言数据，重新开始计数")

    # #21: 举报违规
    @filter.command("举报", "举报群成员违规行为（需要引用消息）")
    async def report_cmd(self, event: AstrMessageEvent, reason: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        reporter_id = str(raw.get("user_id"))
        target_qq = self._extract_at_qq(raw)
        if not target_qq:
            yield event.plain_result("请 @要举报的成员")
            return
        reply_id = self._get_reply_id(event)
        record = {
            "group_id": group_id,
            "reporter_id": reporter_id,
            "target_qq": target_qq,
            "reason": reason or "（未提供原因）",
            "message_id": reply_id,
            "time": int(time.time()),
        }
        self.reports.setdefault("pending", []).append(record)
        self.save_reports()
        # 通知管理员
        notify_admins = self.config.get("report_notify_admins", [])
        if notify_admins:
            text = (f"[举报] 群 {group_id}\n"
                    f"举报人: {reporter_id}\n"
                    f"被举报: {target_qq}\n"
                    f"原因: {record['reason']}")
            for admin_id in notify_admins:
                await self._send_private_msg(str(admin_id), text)
        yield event.plain_result("已提交举报，管理员会尽快处理")

    # ===================== 状态查看 =====================

    # #74: 设置群配置（仅插件管理员）
    @filter.command("设置群配置", "为本群覆盖插件配置项：/设置群配置 <key> <value>")
    async def set_group_config_cmd(self, event: AstrMessageEvent, key: str = "", value: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        if not key:
            yield event.plain_result(
                "用法：/设置群配置 <key> <value>\n"
                "支持 key: show_recall_notice, reject_re_add, rank_top_n, mute_kick_threshold, "
                "title_admins, group_admin_admins, kick_admins, "
                "violation_action, violation_mute_minutes, join_approve_keywords, "
                "join_request_notify_in_group"
            )
            return
        # 类型转换
        parsed_value: object = value
        if value.lower() in ("true", "false"):
            parsed_value = (value.lower() == "true")
        elif value.isdigit():
            parsed_value = int(value)
        elif value.startswith("[") and value.endswith("]"):
            try:
                parsed_value = json.loads(value)
            except Exception:
                parsed_value = [v.strip() for v in value.strip("[]").split(",") if v.strip()]
        overrides = self.config.setdefault("group_overrides", {})
        gconf = overrides.setdefault(group_id, {})
        gconf[key] = parsed_value
        self.save_config()
        yield event.plain_result(f"已为本群设置 {key} = {parsed_value}")

    @filter.command("查看群配置", "查看本群生效的配置覆盖")
    async def view_group_config_cmd(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        group_id = str(raw.get("group_id"))
        gconf = self.config.get("group_overrides", {}).get(group_id, {})
        if not gconf:
            yield event.plain_result("本群未设置任何覆盖（全部使用全局默认）")
            return
        lines = [f"{k}: {v}" for k, v in gconf.items()]
        yield event.plain_result(f"本群覆盖配置：\n" + "\n".join(lines))

    @filter.command("清除群配置", "清除本群所有覆盖")
    async def clear_group_config_cmd(self, event: AstrMessageEvent, key: str = ""):
        raw = self._get_raw_message(event)
        if not raw or not raw.get("group_id"):
            yield event.plain_result("此指令只能在群聊中使用")
            return
        if not self.is_plugin_admin(str(raw.get("user_id"))):
            yield event.plain_result("只有插件管理员可执行此操作")
            return
        group_id = str(raw.get("group_id"))
        gconf = self.config.get("group_overrides", {}).get(group_id, {})
        if key:
            if key not in gconf:
                yield event.plain_result(f"本群未设置 {key}")
                return
            del gconf[key]
            self.save_config()
            yield event.plain_result(f"已清除本群 {key} 覆盖")
        else:
            if group_id in self.config.get("group_overrides", {}):
                del self.config["group_overrides"][group_id]
                self.save_config()
            yield event.plain_result("已清除本群所有覆盖")

    @filter.command("status", "查看插件配置")
    async def status_cmd(self, event: AstrMessageEvent):
        c = self.config
        raw = self._get_raw_message(event)
        group_id = str(raw.get("group_id", "")) if isinstance(raw, dict) else ""
        lines = [
            f"show_recall_notice: {c.get('show_recall_notice', True)}",
            f"reject_re_add: {c.get('reject_re_add', False)}",
            f"plugin_admins: {', '.join(map(str, c.get('plugin_admins', []))) or '空'}",
            f"auto_recall_keywords: {c.get('auto_recall_keywords', [])}",
            f"violation_keywords: {len(c.get('violation_keywords', []))} 个",
            f"rank_top_n: {c.get('rank_top_n', 10)}",
        ]
        if group_id:
            overrides = self.config.get("group_overrides", {}).get(group_id, {})
            lines.extend([
                f"本群 title_admins: {', '.join(map(str, self.get_group_setting(group_id, 'title_admins', []))) or '空'}",
                f"本群 group_admin_admins: {', '.join(map(str, self.get_group_setting(group_id, 'group_admin_admins', []))) or '空'}",
                f"本群 kick_admins: {', '.join(map(str, self.get_group_setting(group_id, 'kick_admins', []))) or '空'}",
                f"本群 mute_kick_threshold: {self.get_group_setting(group_id, 'mute_kick_threshold', 0)}"
                f"{'（按群覆盖）' if 'mute_kick_threshold' in overrides else '（全局默认）'}",
            ])
        yield event.plain_result("插件配置：\n" + "\n".join(lines))

    # ===================== 全消息监听 =====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息：发言计数 + 违规检测。"""
        raw = self._get_raw_message(event)
        if not raw or not isinstance(raw, dict):
            return
        if raw.get("post_type") != "message":
            return
        group_id = str(raw.get("group_id"))
        user_id = str(raw.get("user_id"))
        # 跳过 bot 自身
        if str(raw.get("self_id", "")) == user_id:
            return

        # 发言计数（#29）
        self._increment_message_count(group_id, user_id)

        # 本地缓存：用于 /撤回 N / /撤回 @用户 N 在不支持 get_group_msg_history 时回退（#117 #118）
        msg_id = raw.get("message_id")
        if msg_id:
            self._record_recent_message(group_id, msg_id, user_id)

        # 群违规检测（合并自参考插件，#19 + 图片/刷屏/骂人/广告/链接/群号推广）
        await self._moderation_dispatch(event, raw, group_id, user_id)

        # 加群申请引用回复处理（#57）
        reply_id = self._get_reply_id(event)
        has_permission = self._is_group_admin_or_owner(raw) or self.is_plugin_admin(user_id)
        if reply_id and has_permission:
            pending = self.config.get("pending_join_requests", {})
            info = pending.get(str(reply_id))
            if info:
                msg_text = self._extract_text(raw)
                if msg_text:
                    approve = "同意" in msg_text
                    deny = "拒绝" in msg_text
                    if approve or deny:
                        await self._handle_group_request(event, info["flag"], approve, "管理员审核")
                        result = "同意" if approve else "拒绝"
                        # 清理已处理的记录
                        del pending[str(reply_id)]
                        self.save_config()
                        yield event.plain_result(f"已{result} {info['user_id']} 的加群申请")
                        return

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_event(self, event: AstrMessageEvent):
        raw = self._get_raw_message(event)
        if not raw or not isinstance(raw, dict):
            return

        # 禁言通知统计（#103）
        if raw.get("post_type") == "notice" and raw.get("notice_type") == "group_ban":
            group_id = str(raw.get("group_id"))
            target_id = str(raw.get("user_id", ""))
            operator_id = str(raw.get("operator_id", ""))
            try:
                duration = int(raw.get("duration", 0) or 0)
            except (TypeError, ValueError):
                duration = 0
            if target_id and duration > 0:
                await self._record_mute_and_maybe_kick(event, group_id, target_id, operator_id)
            return

        # 入群欢迎
        if raw.get("post_type") == "notice" and raw.get("notice_type") == "group_increase":
            group_id = str(raw.get("group_id"))
            if self.config.get("groups", {}).get(group_id, {}).get("welcome_enabled", False):
                welcome = self.config["groups"][group_id].get("welcome_message", "欢迎 {at} 加入本群！")
                content = welcome.replace("{at}", f"@{raw.get('user_id')}")
                await self._send(event, self._build_text(content))
            return

        # 加群请求处理（#27 合并 group_manager）
        if raw.get("post_type") == "request" and raw.get("request_type") == "group":
            group_id = str(raw.get("group_id"))
            user_id = str(raw.get("user_id"))
            flag = raw.get("flag", "")
            comment = raw.get("comment", "")
            enabled_groups = self.get_group_setting(group_id, "violation_enabled_groups", [])
            violation_keywords = self.get_group_setting(group_id, "violation_keywords", [])
            join_approve_keywords = self.get_group_setting(group_id, "join_approve_keywords", [])
            enabled = enabled_groups and group_id in [str(x) for x in enabled_groups]

            # 命中违禁词：拒绝 + 通知管理员
            if enabled and violation_keywords and any(kw in comment for kw in violation_keywords):
                await self._handle_group_request(event, flag, False, "触发违禁词")
                yield event.plain_result(f"已拒绝 {user_id} 的加群申请（含违禁词）")
                await self._notify_admins(
                    f"[加群请求] 已拒绝 {user_id}（群 {group_id}）\n"
                    f"验证消息: {comment}\n"
                    f"原因: 命中违禁词",
                    group_id=group_id,
                )
                return

            # 命中关键词：同意 + 通知管理员
            if enabled and join_approve_keywords and any(kw in comment for kw in join_approve_keywords):
                await self._handle_group_request(event, flag, True, "命中关键词自动同意")
                yield event.plain_result(f"已同意 {user_id} 的加群申请（命中关键词）")
                await self._notify_admins(
                    f"[加群请求] 已同意 {user_id}（群 {group_id}）\n"
                    f"验证消息: {comment}\n"
                    f"原因: 命中关键词",
                    group_id=group_id,
                )
                return

            # 群内提醒（#57）：发送申请消息到对应群聊，等待管理员引用回复同意/拒绝
            if self.get_group_setting(group_id, "join_request_notify_in_group", False):
                nickname = await self._get_user_nickname(event, user_id)
                notify_text = (
                    f"【有新人加群申请】\n"
                    f"qq昵称：{nickname}\n"
                    f"新人qq号：{user_id}\n"
                    f"加群验证消息：{comment or '（无）'}\n"
                    f"注：引用消息回复同意或拒绝"
                )
                # 暂存 flag 等待引用回复
                sent_id = await self._send_group_text(event, group_id, notify_text)
                if sent_id:
                    pending = self.config.setdefault("pending_join_requests", {})
                    pending[str(sent_id)] = {"flag": flag, "group_id": group_id, "user_id": user_id}
                    self.save_config()
                    await self._notify_admins(
                        f"[加群请求] {user_id} 申请加入群 {group_id}\n"
                        f"已在群内发送提醒，请管理员引用回复同意/拒绝",
                        group_id=group_id,
                    )

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        """Bot 自身发言后：若命中关键词配置则自动撤回（#46）。"""
        raw = self._get_raw_message(event)
        if not raw:
            return
        group_id = str(raw.get("group_id", ""))
        if not group_id:
            return

        # 本地缓存：记录 bot 自身发言，以便 /撤回 N / /撤回 @bot N 也能回退（#117 #118）。
        # 与自动关键词撤回无关，所有群组都需要写入。
        bot_msg_id = raw.get("message_id")
        bot_user_id = raw.get("user_id") or raw.get("self_id")
        if bot_msg_id and bot_user_id:
            self._record_recent_message(group_id, bot_msg_id, bot_user_id)

        enabled = self.get_group_setting(group_id, "auto_recall_enabled_groups", [])
        if not enabled:
            return
        if group_id not in [str(x) for x in enabled]:
            return
        keywords = self.get_group_setting(group_id, "auto_recall_keywords", [])
        if not keywords:
            return
        msg_text = self._extract_text(raw)
        if not msg_text:
            return
        if any(kw in msg_text for kw in keywords):
            msg_id = raw.get("message_id")
            if msg_id:
                await self._recall_message(event, str(msg_id))

    def _extract_text(self, raw: dict) -> str:
        parts = []
        for seg in raw.get("message", []) or []:
            if isinstance(seg, dict) and seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts)

    def _should_notify_mute(self, ok: bool) -> bool:
        """判断禁言/解禁/宵禁/禁我 是否需要回复。
        配置 mute_notice=False 时只回复失败，成功静默。"""
        if not ok:
            return True  # 失败总是提示
        return bool(self.config.get("mute_notice", True))