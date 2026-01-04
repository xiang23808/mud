from typing import Dict, List, Tuple, Set, Optional
from backend.game.maze import MazeGenerator, Pathfinder
import random
import json

class MapInstance:
    """单个地图实例"""
    
    def __init__(self, map_id: str, config: dict):
        self.map_id = map_id
        self.config = config
        self.maze = MazeGenerator().generate()
        self.monsters: Dict[Tuple[int, int], dict] = {}
        self.players: Dict[int, Tuple[int, int]] = {}  # char_id -> position
        self.revealed: Dict[int, Set[Tuple[int, int]]] = {}  # char_id -> revealed cells
        self.entrances: Dict[str, Tuple[int, int]] = {}  # 地图入口位置
        
        self._init_entrances()
        self._spawn_monsters()
    
    def _init_entrances(self):
        """初始化入口位置"""
        if entrances := self.config.get("entrances"):
            for entrance in entrances:
                pos = tuple(entrance["position"])
                self.entrances[entrance["id"]] = pos
    
    def _spawn_monsters(self):
        """生成怪物"""
        monster_count = self.config.get("monster_count", 60)
        monster_types = self.config.get("monsters", [])
        if not monster_types:
            return
        
        # 排除入口和出口位置
        exclude_pos = [(1, 0), (22, 23)] + list(self.entrances.values())
        
        # 只在可通行的区域生成怪物
        empty_cells = []
        for y in range(24):
            for x in range(24):
                if self.maze[y][x] == 0 and (x, y) not in exclude_pos:
                    # 确保该位置是可到达的(周围至少有一个可通行格子)
                    has_neighbor = False
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < 24 and 0 <= ny < 24 and self.maze[ny][nx] == 0:
                            has_neighbor = True
                            break
                    if has_neighbor:
                        empty_cells.append((x, y))
        
        random.shuffle(empty_cells)
        
        # 生成普通怪物
        spawn_count = min(monster_count, len(empty_cells) - 1)  # 保留一个位置给boss
        for i in range(spawn_count):
            if i >= len(empty_cells):
                break
            pos = empty_cells[i]
            monster_type = random.choice(monster_types)
            self.monsters[pos] = {"type": monster_type, "id": i}
        
        # 生成Boss在远离入口的位置
        if boss := self.config.get("boss"):
            if len(empty_cells) > spawn_count:
                # 选择离入口最远的位置
                entrance = (1, 0)
                farthest_pos = max(empty_cells[spawn_count:],
                                  key=lambda p: abs(p[0] - entrance[0]) + abs(p[1] - entrance[1]))
                self.monsters[farthest_pos] = {"type": boss, "id": -1, "is_boss": True}
    
    def enter(self, char_id: int, from_entrance: bool = True) -> Tuple[int, int]:
        """玩家进入地图"""
        pos = (1, 0) if from_entrance else (22, 23)
        self.players[char_id] = pos
        self.revealed[char_id] = set()
        self.reveal_around(char_id, pos)
        return pos
    
    def leave(self, char_id: int):
        """玩家离开地图"""
        self.players.pop(char_id, None)
        self.revealed.pop(char_id, None)
    
    def reveal_around(self, char_id: int, pos: Tuple[int, int], radius: int = 2):
        """揭示周围区域"""
        if char_id not in self.revealed:
            self.revealed[char_id] = set()
        
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = pos[0] + dx, pos[1] + dy
                if 0 <= nx < 24 and 0 <= ny < 24:
                    self.revealed[char_id].add((nx, ny))
    
    def move_to(self, char_id: int, target: Tuple[int, int]) -> dict:
        """移动到目标位置"""
        if char_id not in self.players:
            return {"success": False, "error": "不在地图中"}
        
        current = self.players[char_id]
        
        # 检查目标是否已揭示
        if target not in self.revealed.get(char_id, set()):
            return {"success": False, "error": "未探索区域"}
        
        # 检查是否是墙
        if self.maze[target[1]][target[0]] == 1:
            return {"success": False, "error": "无法通过"}
        
        # 寻路
        path = Pathfinder.find_path(self.maze, current, target)
        if not path:
            return {"success": False, "error": "无法到达"}
        
        # 检查路径上是否有怪物
        for pos in path[1:]:
            if pos in self.monsters:
                return {"success": False, "error": "有怪物阻挡", "monster_pos": pos, "monster": self.monsters[pos]}
        
        # 移动
        self.players[char_id] = target
        self.reveal_around(char_id, target)
        
        # 检查是否到达出口
        at_exit = target == (22, 23)
        at_entrance = target == (1, 0)
        
        return {"success": True, "path": path, "at_exit": at_exit, "at_entrance": at_entrance}
    
    def get_state(self, char_id: int) -> dict:
        """获取玩家视角的地图状态"""
        revealed = self.revealed.get(char_id, set())
        visible_monsters = {str(pos): m for pos, m in self.monsters.items() if pos in revealed}
        visible_players = {cid: pos for cid, pos in self.players.items() if pos in revealed and cid != char_id}
        
        # 获取可见的入口
        visible_entrances = {}
        if self.config.get("entrances"):
            for entrance in self.config["entrances"]:
                pos = tuple(entrance["position"])
                if pos in revealed:
                    visible_entrances[entrance["id"]] = entrance
        
        return {
            "map_id": self.map_id,
            "maze": self.maze,
            "revealed": list(revealed),
            "position": self.players.get(char_id),
            "monsters": visible_monsters,
            "players": visible_players,
            "entrances": visible_entrances,
            "exits": self.config.get("exits", {})
        }
    
    def remove_monster(self, pos: Tuple[int, int]) -> Optional[dict]:
        """移除怪物"""
        return self.monsters.pop(pos, None)
    
    def respawn_check(self):
        """检查并补充怪物"""
        monster_count = self.config.get("monster_count", 60)
        current = len([m for m in self.monsters.values() if not m.get("is_boss")])
        
        if current < monster_count:
            self._spawn_monsters()


class MapManager:
    """地图管理器"""
    
    def __init__(self):
        self.instances: Dict[str, MapInstance] = {}
        self.player_map: Dict[int, str] = {}  # char_id -> map_id
        self.map_configs = self._load_configs()
    
    def _load_configs(self) -> dict:
        """加载地图配置"""
        try:
            with open("data/maps/maps.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return self._default_configs()
    
    def _default_configs(self) -> dict:
        return {
            "main_city": {
                "name": "比奇省",
                "is_safe": True,
                "monsters": [],
                "entrances": [
                    {"id": "woma_forest", "name": "沃玛森林", "position": [10, 12], "description": "通往沃玛森林的传送门"},
                    {"id": "zombie_cave_1", "name": "僵尸洞", "position": [14, 12], "description": "通往僵尸洞的传送门"}
                ]
            },
            "woma_forest": {"name": "沃玛森林", "monster_count": 60, "monsters": ["chicken", "deer", "wolf"], "exits": {"main_city": [1, 0], "woma_temple_1": [22, 23]}},
            "woma_temple_1": {"name": "沃玛寺庙1层", "monster_count": 60, "monsters": ["woma_guard", "woma_warrior"], "exits": {"woma_forest": [1, 0], "woma_temple_2": [22, 23]}},
            "woma_temple_2": {"name": "沃玛寺庙2层", "monster_count": 60, "monsters": ["woma_warrior", "woma_mage"], "exits": {"woma_temple_1": [1, 0], "woma_temple_3": [22, 23]}},
            "woma_temple_3": {"name": "沃玛寺庙3层", "monster_count": 60, "monsters": ["woma_mage", "woma_elite"], "boss": "woma_leader", "exits": {"woma_temple_2": [1, 0]}},
            "zombie_cave_1": {"name": "僵尸洞1层", "monster_count": 60, "monsters": ["zombie", "zombie_warrior"], "exits": {"main_city": [1, 0], "zombie_cave_2": [22, 23]}},
            "zombie_cave_2": {"name": "僵尸洞2层", "monster_count": 60, "monsters": ["zombie_warrior", "zombie_mage"], "exits": {"zombie_cave_1": [1, 0], "zombie_cave_3": [22, 23]}},
            "zombie_cave_3": {"name": "僵尸洞3层", "monster_count": 60, "monsters": ["zombie_elite"], "boss": "corpse_king", "exits": {"zombie_cave_2": [1, 0]}},
        }
    
    def get_or_create_instance(self, map_id: str) -> MapInstance:
        """获取或创建地图实例"""
        if map_id not in self.instances:
            config = self.map_configs.get(map_id, {})
            self.instances[map_id] = MapInstance(map_id, config)
        return self.instances[map_id]
    
    def enter_map(self, char_id: int, map_id: str, from_entrance: bool = True) -> dict:
        """玩家进入地图"""
        # 离开当前地图
        if current_map := self.player_map.get(char_id):
            if current_map in self.instances:
                self.instances[current_map].leave(char_id)
        
        # 进入新地图
        instance = self.get_or_create_instance(map_id)
        pos = instance.enter(char_id, from_entrance)
        self.player_map[char_id] = map_id
        
        return {"map_id": map_id, "position": pos, "state": instance.get_state(char_id)}
    
    def move(self, char_id: int, target: Tuple[int, int]) -> dict:
        """玩家移动"""
        map_id = self.player_map.get(char_id)
        if not map_id or map_id not in self.instances:
            return {"success": False, "error": "不在任何地图中"}
        
        return self.instances[map_id].move_to(char_id, target)
    
    def get_state(self, char_id: int) -> Optional[dict]:
        """获取玩家当前地图状态"""
        map_id = self.player_map.get(char_id)
        if not map_id or map_id not in self.instances:
            return None
        return self.instances[map_id].get_state(char_id)
    
    def return_to_city(self, char_id: int) -> dict:
        """回城"""
        return self.enter_map(char_id, "main_city", True)
    
    def use_entrance(self, char_id: int, entrance_id: str) -> dict:
        """使用入口传送"""
        map_id = self.player_map.get(char_id)
        if not map_id:
            return {"success": False, "error": "不在任何地图中"}
        
        instance = self.instances.get(map_id)
        if not instance:
            return {"success": False, "error": "地图不存在"}
        
        pos = instance.players.get(char_id)
        entrance_pos = instance.entrances.get(entrance_id)
        
        if not entrance_pos or pos != entrance_pos:
            return {"success": False, "error": "不在入口位置"}
        
        return self.enter_map(char_id, entrance_id, True)
    
    def use_exit(self, char_id: int, exit_type: str) -> dict:
        """使用出口/入口"""
        map_id = self.player_map.get(char_id)
        if not map_id:
            return {"success": False, "error": "不在任何地图中"}
        
        instance = self.instances.get(map_id)
        if not instance:
            return {"success": False, "error": "地图不存在"}
        
        pos = instance.players.get(char_id)
        config = self.map_configs.get(map_id, {})
        exits = config.get("exits", {})
        
        # 检查是否在出口位置
        for target_map, exit_pos in exits.items():
            if pos == exit_pos or (exit_type == "entrance" and pos == (1, 0)) or (exit_type == "exit" and pos == (22, 23)):
                from_entrance = exit_type == "exit"
                return self.enter_map(char_id, target_map, from_entrance)
        
        return {"success": False, "error": "不在出口位置"}


# 全局实例
map_manager = MapManager()