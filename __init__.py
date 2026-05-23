import nonebot
from pathlib import Path
from nonebot.plugin import PluginMetadata, require

# =====================================================================
# 【关键修复】从导入列表中删除引发 ImportError 的 ScoreBaseImage
# ==========================================
from .command import *
from .config import Config, maiconfig, driver, ratingdir
from .libraries.maimaidx_api_data import maiApi
from .libraries.maimaidx_music import mai, update_daily
from nonebot.log import logger as log

# 注册并拉取定时计划任务组件
scheduler = require('nonebot_plugin_apscheduler')
from nonebot_plugin_apscheduler import scheduler

# =====================================================================
# 【Picmenu-Next 深度适配支持库】
# 声明面向多功能全量大菜单的元数据结构，使其能被图片菜单自动扫描并优雅排版
# =====================================================================
__plugin_meta__ = PluginMetadata(
    name='舞萌DX查分服务',
    description='基于 NoneBot2 完美适配水鱼与落雪双数据源的街机高并发中继查分系统',
        usage=(
        "【🎵 MaimaiDX 查分专属指令栏】\n"
        "· b50 : 生成 Best 50 个人成绩精美大图\n"
        "· ap50 : 生成纯 AP 状态的收曲成就大图\n"
        "· minfo <曲目ID> : 查询单谱面详细游玩成绩与分数线\n\n"
        "【⚙️ 个人中心与路由】\n"
        "· mai状态 : 诊断双端绑定，管理默认数据源\n"
        "· 切换数据源 <水鱼/落雪> : 切换默认输出端\n"
        "· mai曲线 : 【落雪特供】绘制 Rating 历史趋势走势折线图"
    ),

    type='application',
    config=Config,
    supported_adapters={'~onebot.v11'},
    extra={
        "menu_data": [
            {
                "category": " Arcade街机音游 ",
                "cmds": [
                    {"cmd": "b50", "desc": "生成 Best 50 个人成绩精美大图"},
                    {"cmd": "ap50", "desc": "生成纯 AP 状态的收曲成就大图"},
                    {"cmd": "mai状态", "desc": "诊断双端绑定，管理默认数据源"},
                    {"cmd": "切换数据源", "desc": "切换默认输出端为水鱼或落雪"},
                    {"cmd": "minfo", "desc": "查询单谱面详细游玩成绩与分数线"},
                    {"cmd": "mai曲线", "desc": "绘制个人 Rating 历史趋势走势折线图"}
                ]
            }
        ]
    }
)


@driver.on_startup
async def get_music():
    """
    Bot 启动生命周期钩子：
    执行独立的 Token 代理加载，并通过双端串联聚合完成零阻塞数据同步
    """
    # 初始化开放平台 Token 加载
    maiApi.load_token_proxy()
    log.info(f"MaimaiDX 数据服务总闸启动就绪。当前系统环境指配全局缺省路由为: [ {maiconfig.prober_source} ]")
    
    # 触发双源聚合全量同步（同时向落雪与水鱼拉取歌曲/别名，增量同步曲绘）
    log.info('执行远端全量歌曲大库、跨端特色别名库及本地曲绘自愈补全...')
    await mai.get_music()
    
    # 兼容处理老版本的 JSON 初始化
    if hasattr(mai, 'get_plate_json'):
        try:
            await mai.get_plate_json()
            log.info('同步全版本完工底板牌子 JSON 常量库...')
        except Exception:
            pass
    
    # 初始化群猜歌缓存
    if hasattr(mai, 'guess'):
        mai.guess()
        
    log.success('Maimai DX 本地增量游戏资产自愈自平衡初始化成功！')
    
    # 【关键修复】宽泛捕获预加载逻辑，避免无底座导致开机断流
    if maiconfig.saveinmem:
        try:
            from .libraries.maimaidx_best_50 import ScoreBaseImage
            ScoreBaseImage.load_image()
            log.success('全量核心 Best 50 UI 绘图背景资产成功常驻系统内存')
        except ImportError:
            log.warning('未检测到 ScoreBaseImage 模块，已跳过图片常驻内存步骤（不影响用户正常发指令查分）。')
        except Exception as e:
            log.warning(f'背景资产常驻内存失败，将采用实时读取模式运行: {e}')
    
    # 定数表检查降级提示
    if not list(ratingdir.iterdir()):
        log.warning('检测到定数表文件夹为空！可能导致完成表功能失效，请及时私聊管理员发送「更新定数表」进行生成。')


# 绑定计划任务：每天凌晨 04:00 准时强制触发双路数据源合流强同步，确保两端数据无时差
scheduler.add_job(update_daily, 'cron', hour=4)
