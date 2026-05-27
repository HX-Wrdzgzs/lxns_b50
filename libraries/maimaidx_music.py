import asyncio
import json
import httpx
import aiofiles
from typing import Dict, Any, List, Optional
from loguru import logger as log
from ..config import maiconfig, music_file, coverdir, guess_file

from .maimaidx_api_data import maiApi

class Music(dict):
    def __getattr__(self, item):
        return self.get(item)
    def __setattr__(self, key, value):
        self[key] = value

class MusicList(list):
    def by_id(self, music_id: str) -> Optional[Music]:
        for music in self:
            if str(music.id) == str(music_id):
                return music
        return None

    def by_title(self, title: str) -> Optional[Music]:
        for music in self:
            if music.title == title:
                return music
        return None


class MaiMusic:
    def __init__(self) -> None:
        self.total_list: MusicList = MusicList()
        self.total_alias_list: Dict[str, List[str]] = {}
        self.guess_data: List[Music] = []

    # ==========================================
    # 动态生成按定数等级分类的歌曲字典，兼容定数表调用
    # ==========================================
    @property
    def total_level_data(self) -> Dict[str, MusicList]:
        res = {}
        for music in self.total_list:
            for lv in music.get('level', []):
                if lv not in res:
                    res[lv] = MusicList()
                if music not in res[lv]:
                    res[lv].append(music)
        return res

    async def get_music(self) -> None:
        log.info("开始拉取双数据源进行强同步合流...")
        lxns_music: List[Dict] = []
        fish_music: List[Dict] = []
        lxns_aliases: Dict[str, List[str]] = {}
        fish_aliases: Dict[str, List[str]] = {}

        async with httpx.AsyncClient(timeout=30) as client:
            if maiconfig.lxnstoken:
                try:
                    headers = {"Authorization": maiconfig.lxnstoken}
                    res = await client.get("https://maimai.lxns.net/api/v0/maimai/song/list", headers=headers)
                    if res.status_code == 200:
                        res_json = res.json()
                        if isinstance(res_json, dict) and "data" in res_json:
                            lxns_music = res_json["data"]
                        elif isinstance(res_json, list):
                            lxns_music = res_json
                            
                        for song in lxns_music:
                            if isinstance(song, dict) and 'id' in song:
                                sid = str(song['id'])
                                lxns_aliases[sid] = song.get('aliases', [])
                except Exception as e:
                    log.error(f"同步拉取落雪数据源发生异常: {e}")

            try:
                res = await client.get("https://www.diving-fish.com/api/maimaidxprober/music_data")
                if res.status_code == 200:
                    res_json = res.json()
                    fish_music = res_json if isinstance(res_json, list) else []
                
                alias_res = await client.get("https://www.diving-fish.com/api/maimaidxprober/side_api/alias")
                if alias_res.status_code == 200:
                    alias_json = alias_res.json()
                    fish_aliases = alias_json if isinstance(alias_json, dict) else {}
            except Exception as e:
                log.error(f"同步拉取水鱼数据源发生异常: {e}")

        if not fish_music and not lxns_music:
            log.error("双路数据源全部同步失败！正在紧急维持本地历史缓存资产。")
            return

        combined_music = {}
        for m in fish_music:
            if isinstance(m, dict) and 'id' in m:
                combined_music[str(m['id'])] = Music(m)
                
        for m in lxns_music:
            if isinstance(m, dict) and 'id' in m:
                sid = str(m['id'])
                if sid not in combined_music:
                    combined_music[sid] = Music(m)

        self.total_list = MusicList(combined_music.values())

        all_sids = set(lxns_aliases.keys()) | set(fish_aliases.keys()) | set(combined_music.keys())
        for sid in all_sids:
            lx_list = lxns_aliases.get(sid, [])
            fi_list = fish_aliases.get(sid, [])
            
            merged_set = set()
            for alias in (lx_list + fi_list):
                if alias:
                    merged_set.add(str(alias).strip().lower())
            
            if not merged_set and sid in combined_music:
                title = combined_music[sid].get('title')
                if title:
                    merged_set.add(title.lower())
                
            self.total_alias_list[sid] = list(merged_set)

        try:
            async with aiofiles.open(music_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.total_list, ensure_ascii=False, indent=4))
        except Exception:
            pass

        asyncio.create_task(self.download_missing_covers())

    async def download_missing_covers(self):
        base_url = "https://assets2.lxns.net/maimai/jacket/{}.png"
        async with httpx.AsyncClient(timeout=30) as client:
            for music in self.total_list:
                song_id = int(music.get('id', 0))
                if song_id > 100000:
                    song_id %= 100000
                cover_path = coverdir / f'{song_id}.png'
                
                if not cover_path.exists():
                    try:
                        res = await client.get(base_url.format(song_id))
                        if res.status_code == 200:
                            async with aiofiles.open(cover_path, 'wb') as f:
                                await f.write(res.content)
                        await asyncio.sleep(0.1)
                    except:
                        pass

mai = MaiMusic()

async def update_daily():
    log.info("触发每日凌晨定时双源强同步合流任务...")
    await mai.get_music()

async def update_local_alias(*args, **kwargs):
    log.info("检测到老版本别名系统更新请求，已重定向至最新双源强同步通道...")
    await mai.get_music()
    return True

class Guess:
    Group: Dict[str, Dict[str, Any]] = {}

    def __init__(self) -> None:
        if guess_file.exists():
            self.config = [line.strip() for line in guess_file.read_text(encoding='utf-8').split('\n') if line.strip()]
        else:
            self.config = []

    def add(self, gid: str):
        if gid not in self.config:
            self.config.append(gid)
            guess_file.write_text('\n'.join(self.config), encoding='utf-8')

    def remove(self, gid: str):
        if gid in self.config:
            self.config.remove(gid)
            guess_file.write_text('\n'.join(self.config), encoding='utf-8')

    def start(self, gid: str, music: Any, cycle: int = 0):
        self.Group[gid] = {
            'music': music,
            'cycle': cycle
        }

    def end(self, gid: str):
        if gid in self.Group:
            del self.Group[gid]

guess = Guess()
