import asyncio
from astrbot.api import star, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import At, Plain, Reply
from typing import Optional, Union, List, Dict, Any

class GroupAdminPlugin(star.Star):
    """AstrBot 群管插件 - 提供完整的群组管理功能"""

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self.context = context

    @filter.command("禁言")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def mute_command(self, event: AstrMessageEvent, args: List[str]):
        """禁言指定群成员

        用法: /禁言 @某人 分钟数
        示例: /禁言 @张三 1440 (代表禁言1天)
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        # 解析@的目标
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break

        if not at_segment:
            yield event.plain_result("请使用 @ 提及要禁言的成员")
            return

        target_qq = at_segment.qq

        # 解析时长（统一按分钟）
        duration_minutes = 10  # 默认10分钟
        if args:
            try:
                duration_minutes = int(args[0])
            except ValueError:
                yield event.plain_result("时长格式错误: 请输入纯数字的分钟数\n例如: 1440 (代表1天)")
                return

        duration_seconds = duration_minutes * 60

        # 执行禁言
        try:
            await self._mute_user(event.message_obj.group_id, target_qq, duration_seconds)
            yield event.plain_result(f"已禁言 @ qq={target_qq} {duration_minutes} 分钟")
        except Exception as e:
            yield event.plain_result(f"禁言失败: {str(e)}")

    @filter.command("解禁")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def unmute_command(self, event: AstrMessageEvent, args: List[str]):
        """解除禁言

        用法: /解禁 @某人
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        # 解析@的目标
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break

        if not at_segment:
            yield event.plain_result("请使用 @ 提及要解禁的成员")
            return

        target_qq = at_segment.qq

        # 执行解禁
        try:
            await self._unmute_user(event.message_obj.group_id, target_qq)
            yield event.plain_result(f"已解禁 @ qq={target_qq}")
        except Exception as e:
            yield event.plain_result(f"解禁失败: {str(e)}")

    @filter.command("踢人")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def kick_command(self, event: AstrMessageEvent, args: List[str]):
        """踢出指定群成员

        用法: /踢人 @某人 [拒绝加群]
        示例: /踢人 @张三 false (不拒绝加群)
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        # 解析@的目标
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break

        if not at_segment:
            yield event.plain_result("请使用 @ 提及要踢出的成员")
            return

        target_qq = at_segment.qq

        # 解析是否拒绝加群
        reject_add_request = True  # 默认拒绝
        if args and args[0].lower() in ('false', '0', 'no'):
            reject_add_request = False

        # 执行踢出
        try:
            await self._kick_user(event.message_obj.group_id, target_qq, reject_add_request)
            yield event.plain_result(f"已踢出 @ qq={target_qq}" + (" (已拒绝加群)" if reject_add_request else " (允许再次加群)"))
        except Exception as e:
            yield event.plain_result(f"踢出失败: {str(e)}")

    @filter.command("全员禁言")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def mute_all_command(self, event: AstrMessageEvent, args: List[str]):
        """设置全员禁言状态

        用法: /全员禁言 开启|关闭
        示例: /全员禁言 开启
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        if not args:
            yield event.plain_result("请指定操作: 开启 或 关闭\n用法: /全员禁言 开启|关闭")
            return

        action = args[0].lower()
        if action not in ('开启', '关闭', 'on', 'off', 'true', 'false', '1', '0'):
            yield event.plain_result("操作参数错误: 请使用 '开启' 或 '关闭'")
            return

        enable = action in ('开启', 'on', 'true', '1')

        try:
            await self._mute_all(event.message_obj.group_id, enable)
            yield event.plain_result(f"已{'开启' if enable else '关闭'}全员禁言")
        except Exception as e:
            yield event.plain_result(f"设置失败: {str(e)}")

    @filter.command("撤回")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def recall_command(self, event: AstrMessageEvent, args: List[str]):
        """撤回指定消息

        用法: /撤回 消息ID
        示例: /撤回 123456
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        if not args:
            yield event.plain_result("请提供要撤回的消息ID\n用法: /撤回 消息ID")
            return

        try:
            message_id = int(args[0])
        except ValueError:
            yield event.plain_result("消息ID格式错误: 请输入纯数字")
            return

        try:
            await self._recall_message(event.message_obj.group_id, message_id)
            yield event.plain_result(f"已尝试撤回消息 {message_id}")
        except Exception as e:
            yield event.plain_result(f"撤回失败: {str(e)}")

    @filter.command("设置管理")
    @filter.permission_type(filter.PermissionType.OWNER)
    async def set_admin_command(self, event: AstrMessageEvent, args: List[str]):
        """设置群管理员

        用法: /设置管理 @某人 设置/取消
        示例: /设置管理 @张三 设置
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        # 解析@的目标
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break

        if not at_segment:
            yield event.plain_result("请使用 @ 提及要设置的成员")
            return

        target_qq = at_segment.qq

        if not args:
            yield event.plain_result("请指定操作: 设置 或 取消\n用法: /设置管理 @某人 设置|取消")
            return

        action = args[0].lower()
        if action not in ('设置', '取消', 'set', 'unset', 'add', 'remove'):
            yield event.plain_result("操作参数错误: 请使用 '设置' 或 '取消'")
            return

        set_admin = action in ('设置', 'set', 'add')

        try:
            await self._set_admin(event.message_obj.group_id, target_qq, set_admin)
            yield event.plain_result(f"已{'设置' if set_admin else '取消'} @ qq={target_qq} 为管理员")
        except Exception as e:
            yield event.plain_result(f"设置失败: {str(e)}")

    @filter.command("群信息")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def group_info_command(self, event: AstrMessageEvent, args: List[str]):
        """获取群详细信息"""
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        try:
            group_info = await self._get_group_info(event.message_obj.group_id)
            info_str = f"群名称: {group_info.get('group_name', '未知')}\n"
            info_str += f"群号: {group_info.get('group_id', '未知')}\n"
            info_str += f"群主: {group_info.get('owner_id', '未知')}\n"
            info_str += f"成员数: {group_info.get('member_count', '未知')}\n"
            info_str += f"最大成员数: {group_info.get('max_member_count', '未知')}"
            yield event.plain_result(info_str)
        except Exception as e:
            yield event.plain_result(f"获取群信息失败: {str(e)}")

    @filter.command("成员信息")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def member_info_command(self, event: AstrMessageEvent, args: List[str]):
        """获取指定成员信息

        用法: /成员信息 @某人
        """
        if not event.message_obj.group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        # 解析@的目标
        at_segment = None
        for segment in event.message_obj.message:
            if isinstance(segment, At):
                at_segment = segment
                break

        if not at_segment:
            yield event.plain_result("请使用 @ 提及要查询的成员")
            return

        target_qq = at_segment.qq

        try:
            member_info = await self._get_member_info(event.message_obj.group_id, target_qq)
            info_str = f"昵称: {member_info.get('nickname', '未知')}\n"
            info_str += f"QQ号: {member_info.get('user_id', '未知')}\n"
            info_str += f"群名片: {member_info.get('card', '未知')}\n"
            info_str += f"群头衔: {member_info.get('title', '未知')}\n"
            info_str += f"管理员: {'是' if member_info.get('role') == 'admin' else '否'}\n"
            info_str += f"加群时间: {member_info.get('join_time', '未知')}\n"
            info_str += f"最后发言: {member_info.get('last_sent_time', '未知')}"
            yield event.plain_result(info_str)
        except Exception as e:
            yield event.plain_result(f"获取成员信息失败: {str(e)}")

    @filter.command("退群")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def leave_group_command(self, event: AstrMessageEvent, args: List[str]):
        """退出指定群聊

        用法: /退群 [群号]
        示例: /退群 123456789
        """
        # 如果提供了群号参数，则退出指定群，否则退出当前群
        group_id = None
        if args:
            try:
                group_id = int(args[0])
            except ValueError:
                yield event.plain_result("群号格式错误: 请输入纯数字")
                return
        elif event.message_obj.group_id:
            group_id = event.message_obj.group_id
        else:
            yield event.plain_result("此命令仅在群聊中可用，或需提供群号参数")
            return

        try:
            await self._leave_group(group_id)
            yield event.plain_result(f"已退出群 {group_id}")
        except Exception as e:
            yield event.plain_result(f"退群失败: {str(e)}")

    @filter.command("加群")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def join_group_command(self, event: AstrMessageEvent, args: List[str]):
        """添加机器人到指定群聊

        用法: /加群 群号
        示例: /加群 123456789
        """
        if not args:
            yield event.plain_result("请提供群号\n用法: /加群 群号")
            return

        try:
            group_id = int(args[0])
        except ValueError:
            yield event.plain_result("群号格式错误: 请输入纯数字")
            return

        try:
            await self._join_group(group_id)
            yield event.plain_result(f"已申请加入群 {group_id}")
        except Exception as e:
            yield event.plain_result(f"加群失败: {str(e)}")

    # 以下是内部实现方法

    async def _mute_user(self, group_id: int, user_id: int, duration: int):
        """内部方法: 禁言用户"""
        api = self.context.get_api()
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration
        }
        await api.call("set_group_ban", params)

    async def _unmute_user(self, group_id: int, user_id: int):
        """内部方法: 解除禁言"""
        api = self.context.get_api()
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "duration": 0  # 设置为0即解禁
        }
        await api.call("set_group_ban", params)

    async def _kick_user(self, group_id: int, user_id: int, reject_add_request: bool):
        """内部方法: 踢出用户"""
        api = self.context.get_api()
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "reject_add_request": reject_add_request
        }
        await api.call("set_group_kick", params)

    async def _mute_all(self, group_id: int, enable: bool):
        """内部方法: 设置全员禁言"""
        api = self.context.get_api()
        params = {
            "group_id": group_id,
            "enable": enable
        }
        await api.call("set_group_whole_ban", params)

    async def _recall_message(self, group_id: int, message_id: int):
        """内部方法: 撤回群消息"""
        api = self.context.get_api()
        params = {  # 第365行修复: 添加8空格缩进
            "group_id": group_id,
            "message_id": message_id
        }
        await api.call("delete_msg", params)

    async def _set_admin(self, group_id: int, user_id: int, enable: bool):
        """内部方法: 设置群管理员"""
        api = self.context.get_api()
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "enable": enable
        }
        await api.call("set_group_admin", params)

    async def _get_group_info(self, group_id: int) -> Dict[str, Any]:
        """内部方法: 获取群信息"""
        api = self.context.get_api()
        params = {
            "group_id": group_id
        }
        return await api.call("get_group_info", params)

    async def _get_member_info(self, group_id: int, user_id: int) -> Dict[str, Any]:
        """内部方法: 获取成员信息"""
        api = self.context.get_api()
        params = {
            "group_id": group_id,
            "user_id": user_id
        }
        return await api.call("get_group_member_info", params)

    async def _leave_group(self, group_id: int):
        """内部方法: 退出群"""
        api = self.context.get_api()
        params = {
            "group_id": group_id
        }
        await api.call("set_group_leave", params)

    async def _join_group(self, group_id: int):
        """内部方法: 加入群"""
        api = self.context.get_api()
        params = {
            "group_id": group_id
        }
        await api.call("set_group_add", params)