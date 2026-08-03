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
from datetime import datetime
from pathlib import Path

@register(
    "welcome_group",
    "YourName",
    "Astrbot群管插件",
    "2.4.0",
    "https://github.com/mjy1113451/welcome_group"
)
class WelcomePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        try:
            from astrbot.api.star import StarTools
            self.data_dir = StarTools.get_data_dir() / "welcome_group"
        except ImportError:
            self.data_dir = Path(os.getcwd()) / "data" / "welcome_group"

        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = self.data_dir / "config.json"
        self.config = self.load_config()

    def _get_default_config(self) -> dict:
        return {
            "groups": {},
            "global_enabled": False,
            "global_increase_message": "欢迎 {at} 加入本群！当前时间：{time}",
            "global_leave_message": "{user_id} 离开了本群。",
            "global_kick_message": "{user_id} 被移出了本群。"
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
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def _ensure_group(self, group_id: str) -> dict:
        if group_id not in self.config["groups"]:
            self.config["groups"][group_id] = {
                "enabled": False,
                "message": "",
                "leave_enabled": False,
                "leave_message": "",
                "kick_enabled": False,
                "kick_message": ""
            }
        return self.config["groups"][group_id]

    def _get_raw_message(self, event: AstrMessageEvent):
        try:
            return event.message_obj.raw_message
        except AttributeError:
            return None

    def _parse_time(self, raw: dict) -> str:
        try:
            timestamp = raw.get("time")
            if timestamp:
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _build_onebot_message(self, processed: str, user_id):
        if "{at}" in processed:
            parts = processed.split("{at}")
            message_list = []
            for i, part in enumerate(parts):
                if part:
                    message_list.append(Plain(part))
                if i < len(parts) - 1:
                    message_list.append(At(qq=user_id))
            return message_list
        else:
            return [Plain(processed)]

    def _build_fallback_chain(self, processed: str, user_id):
        fallback = processed.replace("{at}", f"@{user_id}")
        return [Plain(fallback)]

    async def _send_group_msg(self, event: AstrMessageEvent, group_id: str, message_list):
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

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_increase(self, event: AstrMessageEvent):
        try:
            raw = self._get_raw_message(event)
            if not raw or not isinstance(raw, dict):
                return

            if raw.get("post_type") != "notice" or raw.get("notice_type") != "group_increase":
                return

            group_id = str(raw.get("group_id"))
            user_id = raw.get("user_id")
            self_id = raw.get("self_id")

            if str(user_id) == str(self_id):
                return

            group_config = self.config["groups"].get(group_id)
            welcome_template = ""

            if not group_config:
                if self.config.get("global_enabled", False):
                    logger.info(f"群 {group_id} 未配置，使用全局入群欢迎语")
                    welcome_template = self.config.get("global_increase_message", "欢迎 {at} 加入本群！当前时间：{time}")
                else:
                    logger.info(f"群 {group_id} 未配置且全局模式未开启，跳过欢迎")
                    return
            else:
                if not group_config.get("enabled", False):
                    return
                welcome_template = group_config.get("message", self.config.get("global_increase_message", "欢迎 {at} 加入本群！当前时间：{time}"))

            time_str = self._parse_time(raw)
            processed = welcome_template.replace("{time}", time_str).replace("{user_id}", str(user_id))
            message_list = self._build_onebot_message(processed, user_id)
            success = await self._send_group_msg(event, group_id, message_list)

            if not success:
                try:
                    fallback_list = self._build_fallback_chain(processed, user_id)
                    if MessageChain is not None:
                        await event.send(MessageChain(fallback_list))
                    else:
                        await event.send(fallback_list)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"处理入群事件时出错: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_group_decrease(self, event: AstrMessageEvent):
        try:
            raw = self._get_raw_message(event)
            if not raw or not isinstance(raw, dict):
                return

            if raw.get("post_type") != "notice" or raw.get("notice_type") != "group_decrease":
                return

            sub_type = raw.get("sub_type", "")
            group_id = str(raw.get("group_id"))
            user_id = raw.get("user_id")
            self_id = raw.get("self_id")

            if sub_type == "kick_me" or str(user_id) == str(self_id):
                return

            group_config = self.config["groups"].get(group_id, {})
            template = ""

            default_leave = self.config.get("global_leave_message", "{user_id} 离开了本群。")
            default_kick = self.config.get("global_kick_message", "{user_id} 被移出了本群。")

            if sub_type == "leave":
                if not group_config.get("leave_enabled", False):
                    if not group_config:
                        if self.config.get("global_enabled", False):
                            template = default_leave
                        else:
                            return
                    else:
                        return
                template = group_config.get("leave_message", default_leave)
            elif sub_type == "kick":
                if not group_config.get("kick_enabled", False):
                    if not group_config:
                        if self.config.get("global_enabled", False):
                            template = default_kick
                        else:
                            return
                    else:
                        return
                template = group_config.get("kick_message", default_kick)
            else:
                return

            time_str = self._parse_time(raw)
            processed = template.replace("{time}", time_str).replace("{user_id}", str(user_id))
            message_list = self._build_onebot_message(processed, user_id)
            await self._send_group_msg(event, group_id, message_list)
        except Exception as e:
            logger.error(f"处理退群事件时出错: {e}")

    @filter.command_group("welcome", "欢迎功能管理")
    def welcome(self):
        pass

    @welcome.command("set", "设置当前群欢迎语")
    async def set_welcome(self, event: AstrMessageEvent, message: str = ""):
        if not event.message_obj.group_id:
            yield event.plain_result("此指令只能在群聊中使用")
            return

        group_id = str(event.message_obj.group_id)
        group_config = self._ensure_group(group_id)

        if message.strip():
            group_config["enabled"] = True
            group_config["message"] = message.strip()
            self.save_config()
            yield event.plain_result(f"已设置群 {group_id} 的欢迎语：\n{message}")
        else:
            group_config["enabled"] = False
            group_config["message"] = ""
            self.save_config()
            yield event.plain_result(f"已重置群 {group_id} 的欢迎语为全局默认")

    @welcome.command("leave", "设置退群提示")
    async def set_leave(self, event: AstrMessageEvent, message: str = ""):
        if not event.message_obj.group_id:
            yield event.plain_result("此指令只能在群聊中使用")
            return

        group_id = str(event.message_obj.group_id)
        group_config = self._ensure_group(group_id)

        if message.strip():
            group_config["leave_enabled"] = True
            group_config["leave_message"] = message.strip()
            self.save_config()
            yield event.plain_result(f"已设置退群提示：{message}")
        else:
            group_config["leave_enabled"] = False
            group_config["leave_message"] = ""
            self.save_config()
            yield event.plain_result("已禁用退群提示")

    @welcome.command("kick", "设置被踢提示")
    async def set_kick(self, event: AstrMessageEvent, message: str = ""):
        if not event.message_obj.group_id:
            yield event.plain_result("此指令只能在群聊中使用")
            return

        group_id = str(event.message_obj.group_id)
        group_config = self._ensure_group(group_id)

        if message.strip():
            group_config["kick_enabled"] = True
            group_config["kick_message"] = message.strip()
            self.save_config()
            yield event.plain_result(f"已设置被踢提示：{message}")
        else:
            group_config["kick_enabled"] = False
            group_config["kick_message"] = ""
            self.save_config()
            yield event.plain_result("已禁用被踢提示")

    @welcome.command("on", "开启欢迎功能")
    async def enable_welcome(self, event: AstrMessageEvent):
        if not event.message_obj.group_id:
            yield event.plain_result("此指令只能在群聊中使用")
            return

        group_id = str(event.message_obj.group_id)
        group_config = self._ensure_group(group_id)
        group_config["enabled"] = True
        self.save_config()
        yield event.plain_result(f"已开启群 {group_id} 的欢迎功能")

    @welcome.command("off", "关闭欢迎功能")
    async def disable_welcome(self, event: AstrMessageEvent):
        if not event.message_obj.group_id:
            yield event.plain_result("此指令只能在群聊中使用")
            return

        group_id = str(event.message_obj.group_id)
        group_config = self._ensure_group(group_id)
        group_config["enabled"] = False
        self.save_config()
        yield event.plain_result(f"已关闭群 {group_id} 的欢迎功能")

    @welcome.command("status", "查看欢迎状态")
    async def show_status(self, event: AstrMessageEvent):
        if not event.message_obj.group_id:
            yield event.plain_result("此指令只能在群聊中使用")
            return

        group_id = str(event.message_obj.group_id)
        group_config = self._ensure_group(group_id)

        status_info = [
            f"群 {group_id} 欢迎状态：",
            f"欢迎功能: {'开启' if group_config.get('enabled', False) else '关闭'}",
            f"欢迎语: {group_config.get('message', '使用全局默认')}",
            f"退群提示: {'开启' if group_config.get('leave_enabled', False) else '关闭'}",
            f"退群语: {group_config.get('leave_message', '使用全局默认')}",
            f"被踢提示: {'开启' if group_config.get('kick_enabled', False) else '关闭'}",
            f"被踢语: {group_config.get('kick_message', '使用全局默认')}",
        ]

        yield event.plain_result("\n".join(status_info))

    @welcome.command("list", "列出所有群配置")
    async def list_groups(self, event: AstrMessageEvent):
        if not self.config["groups"]:
            yield event.plain_result("当前没有任何群组配置")
            return

        group_list = []
        for group_id, config in self.config["groups"].items():
            status = "开启" if config.get("enabled", False) else "关闭"
            group_list.append(f"群 {group_id}: {status}")

        yield event.plain_result("已配置的群组列表：\n" + "\n".join(group_list))
