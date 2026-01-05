from typing import Dict, List, Tuple, Set, Optional
from backend.game.maze import MazeGenerator, Pathfinder
from backend.game.data_loader import DataLoader
import random
import json

class MapInstance:
    """单个地图实例"""
    
    def __init__(self, map_id: str, config: dict):
        self.map_id = map_id
        self.config = config
        
        # 主城使用特殊的开放地图，其他地图生成迷宫
        if config.get("is_safe") or map_id == "main_city":
            self.maze = self._generate_safe_city()
        else:
            self.maze = MazeGenerator().generate()
        
        self.monsters: Dict[Tuple[int, int], dict] = {}
        self.players: Dict[int, Tuple[int, int]] = {}
        self.revealed: Dict[int, Set[Tuple[int, int]]] = {}
        self.entrances: Dict[str, Tuple[int, int]] = {}
        
        self._init_entrances()
        self._spawn_monsters()
    
    def _generate_safe_city(self) -> list:
        """生成主城安全区 - 开放地图带随机装饰"""
        # 创建一个开放的24x24地图
        maze = [[0] * 24 for _ in range(24)]
        
        # 只在边界添加墙壁
        for x in range(24):
            maze[0][x] = 1
            maze[23][x] = 1
        for y in range(24):
            maze[y][0] = 1
            maze[y][23] = 1
        
        # 添加一些随机装饰性墙壁（密度15%，比普通地图少）
        for y in range(2, 22):
            for x in range(2, 22):
                if random.random() < 0.15:
                    maze[y][x] = 1
        
        return maze
    
    def _init_entrances(self):
        """初始化入口位置"""
        # 确保地图入口/出口位置可通行 - 扩大清空范围
        for y in range(1, 5):
            for x in range(1, 5):
                self.maze[y][x] = 0  # 左上角入口区域
        for y in range(19, 23):
            for x in range(19, 23):
                self.maze[y][x] = 0  # 右下角出口区域
        
        if entrances := self.config.get("entrances"):
            for entrance in entrances:
                pos = tuple(entrance["position"])
                if 0 <= pos[0] < 24 and 0 <= pos[1] < 24:
                    # 确保入口位置及周围3x3区域完全清空
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            nx, ny = pos[0] + dx, pos[1] + dy
                            if 0 <= nx < 24 and 0 <= ny < 24:
                                self.maze[ny][nx] = 0
                    self.entrances[entrance["id"]] = pos
    
    def _spawn_monsters(self):
        """生成怪物 - 简化版，不使用A*验证"""
        monster_count = self.config.get("monster_count", 60)
        monster_types = self.config.get("monsters", [])
        
        if not monster_types:
            return
        
        # 排除入口和出口附近的位置
        exclude_pos = set()
        for pos in [(2, 1), (21, 22)] + list(self.entrances.values()):
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    exclude_pos.add((pos[0] + dx, pos[1] + dy))
        
        # 收集所有可通行的格子
        empty_cells = []
        for y in range(1, 23):  # 避开边界
            for x in range(1, 23):
                if self.maze[y][x] == 0 and (x, y) not in exclude_pos:
                    # 检查周围是否有足够的通路
                    neighbor_count = 0
                    for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < 24 and 0 <= nx < 24 and self.maze[ny][nx] == 0:
                            neighbor_count += 1
                    # 至少有2个相邻通路才算合适的刷新点
                    if neighbor_count >= 2:
                        empty_cells.append((x, y))
        
        if not empty_cells:
            return
        
        random.shuffle(empty_cells)
        
        # 生成普通怪物
        spawn_count = min(monster_count, len(empty_cells) - 1)
        for i in range(spawn_count):
            if i >= len(empty_cells):
                break
            pos = empty_cells[i]
            monster_type = random.choice(monster_types)
            monster_info = DataLoader.get_monster(monster_type)
            monster_data = {"type": monster_type, "id": i}
            if monster_info and monster_info.get("is_boss"):
                monster_data["is_boss"] = True
            self.monsters[pos] = monster_data
        
        # 生成Boss
        if boss := self.config.get("boss"):
            if len(empty_cells) > spawn_count:
                entrance = (2, 1)
                farthest_pos = max(empty_cells[spawn_count:],
                                  key=lambda p: abs(p[0] - entrance[0]) + abs(p[1] - entrance[1]))
                self.monsters[farthest_pos] = {"type": boss, "id": -1, "is_boss": True}
    
    def enter(self, char_id: int, from_entrance: bool = True) -> Tuple[int, int]:
        """玩家进入地图"""
        # 主城使用中心位置，其他地图使用入口/出口
        if self.config.get("is_safe") or self.map_id == "main_city":
            pos = (12, 12)  # 主城中心位置
            self.players[char_id] = pos
            # 主城直接揭示全部区域，无迷雾
            self.revealed[char_id] = {(x, y) for x in range(24) for y in range(24)}
        else:
            pos = (2, 2) if from_entrance else (21, 21)  # 避开边界墙壁
            self.players[char_id] = pos
            self.revealed[char_id] = set()
            # 进入地图时使用更大的视野半径(5格)
            self.reveal_around(char_id, pos, radius=5)
        return pos
    
    def leave(self, char_id: int):
        """玩家离开地图"""
        self.players.pop(char_id, None)
        self.revealed.pop(char_id, None)
    
    def reveal_around(self, char_id: int, pos: Tuple[int, int], radius: int = 3):
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
                # 揭示怪物周围区域，让玩家能看到阻挡的怪物
                self.reveal_around(char_id, pos, radius=1)
                return {"success": False, "error": "有怪物阻挡", "monster_pos": pos, "monster": self.monsters[pos]}
        
        # 移动
        self.players[char_id] = target
        self.reveal_around(char_id, target)
        
        # 检查是否到达出口（适用于非主城地图）- 只在特定位置
        at_exit = (target[0] == 21 and target[1] == 21) and not self.config.get("is_safe")
        at_entrance = (target[0] == 2 and target[1] == 2) and not self.config.get("is_safe")
        
        return {"success": True, "path": path, "at_exit": at_exit, "at_entrance": at_entrance}
    
    def get_state(self, char_id: int) -> dict:
        """获取玩家视角的地图状态"""
        revealed = self.revealed.get(char_id, set())
        visible_monsters = {f"{pos[0]},{pos[1]}": m for pos, m in self.monsters.items() if pos in revealed}
        visible_players = {cid: pos for cid, pos in self.players.items() if pos in revealed and cid != char_id}
        
        # 获取可见的入口 - 修复返回格式
        visible_entrances = {}
        if self.config.get("entrances"):
            for entrance in self.config["entrances"]:
                pos = tuple(entrance["position"])
                if pos in revealed:
                    # 使用entrance的id作为key，完整entrance对象作为value
                    visible_entrances[entrance["id"]] = {
                        "id": entrance["id"],
                        "name": entrance["name"],
                        "position": entrance["position"],
                        "description": entrance.get("description", "")
                    }
        
        # 添加NPC信息（主城特有）
        npcs = []
        if self.config.get("is_safe"):
            npcs = [
                {"id": "weapon_shop", "name": "武器店", "position": [6, 8], "npc_name": "铁匠王大锤"},
                {"id": "armor_shop", "name": "防具店", "position": [10, 8], "npc_name": "裁缝李大娘"},
                {"id": "potion_shop", "name": "药店", "position": [14, 8], "npc_name": "药师孙老头"},
                {"id": "skill_shop", "name": "书店", "position": [18, 8], "npc_name": "书生张秀才"},
                {"id": "recycle_shop", "name": "回收商", "position": [6, 16], "npc_name": "收购商老周"},
                {"id": "warehouse", "name": "仓库", "position": [10, 16], "npc_name": "仓库管理员"}
            ]
        
        return {
            "map_id": self.map_id,
            "map_name": self.config.get("name", self.map_id),
            "maze": self.maze,
            "revealed": list(revealed),
            "position": self.players.get(char_id),
            "monsters": visible_monsters,
            "players": visible_players,
            "entrances": visible_entrances,
            "exits": self.config.get("exits", {}),
            "npcs": npcs
        }
    
    def remove_monster(self, pos: Tuple[int, int]) -> Optional[dict]:
        """移除怪物"""
        return self.monsters.pop(pos, None)
    
    def respawn_check(self):
        """检查并补充怪物 - 简化版"""
        monster_count = self.config.get("monster_count", 60)
        current = len([m for m in self.monsters.values() if not m.get("is_boss")])
        need_spawn = monster_count - current
        
        if need_spawn > 0:
            monster_types = self.config.get("monsters", [])
            if not monster_types:
                return
            
            # 排除入口、出口和已有怪物的位置
            exclude_pos = set(self.monsters.keys())
            for pos in [(2, 1), (21, 22)] + list(self.entrances.values()):
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        exclude_pos.add((pos[0] + dx, pos[1] + dy))
            
            # 收集可用位置
            empty_cells = []
            for y in range(1, 23):
                for x in range(1, 23):
                    if self.maze[y][x] == 0 and (x, y) not in exclude_pos:
                        neighbor_count = sum(1 for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]
                                           if 0 <= y + dy < 24 and 0 <= x + dx < 24
                                           and self.maze[y + dy][x + dx] == 0)
                        if neighbor_count >= 2:
                            empty_cells.append((x, y))
            
            if not empty_cells:
                return
            
            random.shuffle(empty_cells)
            
            # 补充怪物
            spawn_count = min(need_spawn, len(empty_cells))
            monster_id_base = max([m.get("id", 0) for m in self.monsters.values()
                                  if not m.get("is_boss")], default=0) + 1
            
            for i in range(spawn_count):
                pos = empty_cells[i]
                monster_type = random.choice(monster_types)
                monster_info = DataLoader.get_monster(monster_type)
                monster_data = {"type": monster_type, "id": monster_id_base + i}
                if monster_info and monster_info.get("is_boss"):
                    monster_data["is_boss"] = True
                self.monsters[pos] = monster_data


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
    
    def get_or_create_instance(self, map_id: str) -> Optional[MapInstance]:
        """获取或创建地图实例"""
        if map_id not in self.instances:
            config = self.map_configs.get(map_id)
            if not config:
                return None  # 地图配置不存在
            self.instances[map_id] = MapInstance(map_id, config)
        return self.instances[map_id]
    
    def enter_map(self, char_id: int, map_id: str, from_entrance: bool = True) -> dict:
        """玩家进入地图"""
        # 检查地图配置是否存在
        if map_id not in self.map_configs:
            return {"success": False, "error": f"地图 {map_id} 不存在"}
        
        # 离开当前地图
        if current_map := self.player_map.get(char_id):
            if current_map in self.instances:
                self.instances[current_map].leave(char_id)
        
        # 对于非主城地图，如果没有其他玩家，则重新生成
        if map_id != "main_city":
            if map_id in self.instances:
                instance = self.instances[map_id]
                if len(instance.players) == 0:
                    del self.instances[map_id]
        
        # 进入新地图
        instance = self.get_or_create_instance(map_id)
        if not instance:
            return {"success": False, "error": f"无法创建地图 {map_id}"}
        
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
        
        # 检查是否在入口位置(2,2)或出口位置(21,21)
        in_entrance_area = pos[0] == 2 and pos[1] == 2
        in_exit_area = pos[0] == 21 and pos[1] == 21
        
        # 根据区域找到对应的目标地图
        for target_map, exit_pos in exits.items():
            exit_pos_tuple = tuple(exit_pos) if isinstance(exit_pos, list) else exit_pos
            # 入口区域对应的出口通常在左上角
            if exit_type == "entrance" and in_entrance_area and exit_pos_tuple[0] <= 3:
                return self.enter_map(char_id, target_map, False)
            # 出口区域对应的出口通常在右下角
            if exit_type == "exit" and in_exit_area and exit_pos_tuple[0] >= 20:
                return self.enter_map(char_id, target_map, True)
        
        return {"success": False, "error": "不在出口位置"}


# 全局实例
map_manager = MapManager()