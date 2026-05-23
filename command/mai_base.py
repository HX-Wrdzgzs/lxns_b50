import json
import time
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from ..libraries.maimaidx_api_data import maiApi, user_source_route, maiconfig
from ..libraries.tool import run_chrome_to_base64

# 指令注册总览
maimaidxhelp = on_command('mai帮助', aliases={'帮助maimaiDX', '帮助maimaidx'})
switch_source = on_command('切换数据源')
user_profile = on_command('mai状态', aliases={'详细信息', 'mai个人中心'})
render_curve = on_command('mai曲线')


@switch_source.handle()
async def _(event: MessageEvent, message: Message = CommandArg()):
    """
    动态修改玩家在内存字典中指定的默认输出查分数据源
    """
    arg = message.extract_plain_text().strip().lower()
    qqid = event.user_id
    if arg in ['落雪', 'lxns']:
        user_source_route[qqid] = 'lxns'
        await switch_source.finish("已成功为您指定查分默认输出为：❄️ 落雪 (LXNS)", reply_message=True)
    elif arg in ['水鱼', 'diving-fish', 'df']:
        user_source_route[qqid] = 'diving-fish'
        await switch_source.finish("已成功为您指定查分默认输出为：🔮 水鱼 (Diving-Fish)", reply_message=True)
    else:
        await switch_source.finish("参数有误，支持：「切换数据源 水鱼」或「切换数据源 落雪」", reply_message=True)


@maimaidxhelp.handle()
async def _(bot: Bot, event: MessageEvent):
    """
    【核心帮助菜单】
    针对官方机器人(3889004352)下发含有动态源切换按钮和Markdown超链接的菜单；
    针对常规Bot或picmenu-next捕获链，则干净输出纯文本，方便多功能菜单整合。
    """
    qqid = event.user_id
    current_source = user_source_route.get(qqid, maiconfig.prober_source.lower())
    source_title = "❄️ 落雪 (LXNS)" if current_source == 'lxns' else "🔮 水鱼 (Diving-Fish)"

    # 1. 针对官方开放平台设计的结构化高亮 Markdown 文本
    md_help = (
        f"### 🎵 MaimaiDX 查分官方助手\n"
        f"> 当前为您生效的默认输出端：**{source_title}**\n\n"
        "**📊 成绩核心查分**\n"
        "• `b50` : 生成 Best 50 个人综合成绩面板\n"
        "• `ap50` : 生成 AP 50 纯收曲全成就图\n"
        "• `minfo <ID>` : 查询单曲游玩详情与分数线\n\n"
        "**🔍 曲目高效检索**\n"
        "• `查歌 <关键词>` : 全局模糊检索歌曲名\n"
        "• `id <曲目ID>` : 调取目标谱面核心底标参数\n\n"
        "**⚙️ 账户与路由中心**\n"
        "• `mai状态` : 诊断您的双端绑定状态与档案大盘\n"
        "• `切换数据源 水鱼/落雪` : 实时修改输出端\n\n"
        "💡 *提示：点击下方对应快捷按钮，即可一键发送对应查分指令或就地切置默认输出！*"
    )

    # 2. 针对普通私有部署以及 picmenu 图片菜单插件解析的纯文本标准格式
    plain_help = (
        f"【MaimaiDX 查分器指令字典】\n"
        f"当前为您生效的数据源：{source_title}\n\n"
        "· b50 : 生成 Best 50 成绩图\n"
        "· ap50 : 生成 AP 50 成绩图\n"
        "· mai状态 : 诊断查分器双端绑定状态\n"
        "· 切换数据源 <水鱼/落雪> : 修改输出端\n"
        "· minfo <曲目ID> : 查询单曲游玩详情\n"
        "· id <曲目ID> : 查看谱面详细底标"
    )

    # 交互式内嵌键盘按钮组 (2行2列)
    inline_keyboard = {
        "rows": [
            {
                "buttons": [
                    {"id": "b50", "render_data": {"label": "📊 生成我的 B50", "style": 1}, "action": {"type": 2, "permission": {"type": 0}, "data": "b50", "enter": True}},
                    {"id": "profile", "render_data": {"label": "👤 个人状态大盘", "style": 1}, "action": {"type": 2, "permission": {"type": 0}, "data": "mai状态", "enter": True}}
                ]
            },
            {
                "buttons": [
                    {"id": "to_lx", "render_data": {"label": "❄️ 默认切至落雪", "style": 2}, "action": {"type": 2, "permission": {"type": 0}, "data": "切换数据源 落雪", "enter": True}},
                    {"id": "to_fi", "render_data": {"label": "🔮 默认切至水鱼", "style": 2}, "action": {"type": 2, "permission": {"type": 0}, "data": "切换数据源 水鱼", "enter": True}}
                ]
            }
        ]
    }

    # 智能判别分流
    if str(bot.self_id) == "3889004352":
        await bot.send(event=event, message=md_help, extra={"markdown": True, "keyboard": inline_keyboard})
    else:
        await maimaidxhelp.finish(plain_help, reply_message=True)


@user_profile.handle()
async def _(bot: Bot, event: MessageEvent):
    """
    【详细信息：个人中心大盘】
    同步探测玩家落雪和水鱼的绑定和注册细节，并送出官方跳转和一键切换机制
    """
    qqid = event.user_id
    bind = await maiApi.check_bind_status(qqid)
    lx_ind = "🟢 已同步绑定" if bind["lxns"] else "🔴 未绑定"
    fi_ind = "🟢 已同步绑定" if bind["diving_fish"] else "🔴 未绑定"
    
    current_source = user_source_route.get(qqid, maiconfig.prober_source.lower())
    source_title = "❄️ 落雪 (LXNS)" if current_source == 'lxns' else "🔮 水鱼 (Diving-Fish)"

    # 档案卡 Markdown 规范格式
    md_profile = (
        f"### 👤 MaimaiDX 玩家档案大盘\n"
        f"针对您的 QQ 账户：`{qqid}` 诊断报告：\n\n"
        f"**⚙️ 当前默认输出端**\n"
        f"• 正在使用：**{source_title}**\n\n"
        f"**🔗 全端数据同步状态检测**\n"
        f"• ❄️ 落雪查分器：{lx_ind}\n"
        f"• 🔮 水鱼查分器：{fi_ind}\n\n"
        f"💡 *管理建议：如若两端有未完成绑定的账户，请点击最下方对应官方传送链快速授权绑定；点击切置按钮直接变更输出。*"
    )

    # 档案卡 纯文本/picmenu 兼容版
    plain_profile = (
        f"【MaimaiDX 个人中心详细档案】\n"
        f"用户 QQ：{qqid}\n\n"
        f"当前默认输出端：{source_title}\n"
        f"落雪查分器绑定状态：{'[已绑定]' if bind['lxns'] else '[未绑定]'}\n"
        f"水鱼查分器绑定状态：{'[已绑定]' if bind['diving_fish'] else '[未绑定]'}\n\n"
        f"• 提示：落雪源用户可发送「mai曲线」调取Rating历史走势。"
    )

    # 进阶控制键盘（支持跳转与就地无感绑定切换）
    inline_keyboard = {
        "rows": [
            {
                "buttons": [
                    {"id": "set_lxns", "render_data": {"label": "❄️ 默认设为落雪", "style": 2}, "action": {"type": 2, "permission": {"type": 0}, "data": "切换数据源 落雪", "enter": True}},
                    {"id": "set_fish", "render_data": {"label": "🔮 默认设为水鱼", "style": 2}, "action": {"type": 2, "permission": {"type": 0}, "data": "切换数据源 水鱼", "enter": True}}
                ]
            },
            {
                "buttons": [
                    {"id": "v_curve", "render_data": {"label": "📈 趋势折线走势图", "style": 1}, "action": {"type": 2, "permission": {"type": 0}, "data": "mai曲线", "enter": True}}
                ]
            },
            {
                "buttons": [
                    {"id": "lnk_lx", "render_data": {"label": "🌐 落雪主页传送", "style": 0}, "action": {"type": 0, "permission": {"type": 0}, "data": "https://maimai.lxns.net/user/profile?tab=profile"}},
                    {"id": "lnk_fi", "render_data": {"label": "🌐 水鱼主页传送", "style": 0}, "action": {"type": 0, "permission": {"type": 0}, "data": "https://www.diving-fish.com/maimaidx/prober/"}}
                ]
            }
        ]
    }

    if str(bot.self_id) == "3889004352":
        await bot.send(event=event, message=md_profile, extra={"markdown": True, "keyboard": inline_keyboard})
    else:
        await user_profile.finish(plain_profile, reply_message=True)


@render_curve.handle()
async def _(bot: Bot, event: MessageEvent):
    """
    【向外拓展：Rating 历史变动趋势折线图】
    仅在用户将当前输出源切换为落雪时提供支持
    """
    qqid = event.user_id
    current_source = user_source_route.get(qqid, maiconfig.prober_source.lower())
    if current_source != 'lxns':
        await render_curve.finish("⚠️ 趋势历史曲线功能目前由落雪API独占特供，请先切换默认输出端为落雪查分器！", reply_message=True)
        
    curves = await maiApi.get_lxns_rating_curves(qqid)
    if not curves:
        await render_curve.finish("❌ 未在落雪官网检测到您的 Rating 变动轨迹，请确保您在落雪同步并积累了大于一次的有效成绩！", reply_message=True)

    try:
        import pyecharts.options as opts
        from pyecharts.charts import Line
        from ..config import pie_html_file
        
        timestamps = [time.strftime("%m-%d", time.localtime(c["time"])) for c in curves]
        ratings = [c["rating"] for c in curves]
        
        line = Line(init_opts=opts.InitOpts(width="1000px", height="600px", bg_color="#fff"))
        line.add_xaxis(xaxis_data=timestamps)
        line.add_yaxis(
            series_name="Rating变动走势",
            y_axis=ratings,
            is_smooth=True,
            label_opts=opts.LabelOpts(is_show=True),
        )
        line.set_global_opts(title_opts=opts.TitleOpts(title="📈 MaimaiDX 个人历史 Rating 演变折线图", pos_left="center"))
        line.render(str(pie_html_file))
        
        base64_img = await run_chrome_to_base64()
        await render_curve.finish(MessageSegment.image(base64_img), reply_message=True)
    except:
        await render_curve.finish("⚠️ 历史战绩画布高级组件渲染失败，请联系Bot管理员检修服务器配置环境。", reply_message=True)
