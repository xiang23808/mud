import random
from typing import List, Tuple, Set

class MazeGenerator:
    """24x24迷宫生成器 - 优化版，生成更开放的地图"""
    
    def __init__(self, width: int = 24, height: int = 24):
        self.width = width
        self.height = height
    
    def generate(self) -> List[List[int]]:
        """生成迷宫，0=通道，1=墙壁"""
        # 初始化全部为通道，然后添加墙壁
        maze = [[0] * self.width for _ in range(self.height)]
        
        # 添加边界墙
        for x in range(self.width):
            maze[0][x] = 1
            maze[self.height - 1][x] = 1
        for y in range(self.height):
            maze[y][0] = 1
            maze[y][self.width - 1] = 1
        
        # 随机添加一些墙壁作为障碍，但保持大部分区域可通行
        # 墙壁密度约30%
        for y in range(2, self.height - 2):
            for x in range(2, self.width - 2):
                if random.random() < 0.3:
                    maze[y][x] = 1
        
        # 确保入口和出口区域清空
        entrance = (1, 0)
        exit_pos = (self.width - 2, self.height - 1)
        
        # 清空入口区域（3x3）
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = entrance[0] + dx, entrance[1] + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    maze[ny][nx] = 0
        
        # 清空出口区域（3x3）
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = exit_pos[0] + dx, exit_pos[1] + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    maze[ny][nx] = 0
        
        # 确保从入口到出口有明确的通路
        self._ensure_path(maze, entrance, exit_pos)
        
        return maze
    
    def _ensure_path(self, maze: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]):
        """确保从起点到终点有通路"""
        # 使用简单的直线路径，然后添加一些随机转折
        current_x, current_y = start
        target_x, target_y = end
        
        while current_y < target_y:
            maze[current_y][current_x] = 0
            # 确保路径宽度为2
            if current_x + 1 < self.width:
                maze[current_y][current_x + 1] = 0
            current_y += 1
            
            # 随机左右移动
            if current_x < target_x and random.random() < 0.3:
                current_x += 1
            elif current_x > target_x and random.random() < 0.3:
                current_x -= 1
            
            current_x = max(1, min(self.width - 2, current_x))
        
        # 确保到达目标点
        while current_x != target_x:
            maze[current_y][current_x] = 0
            if current_x + 1 < self.width:
                maze[current_y][current_x + 1] = 0
            if current_x < target_x:
                current_x += 1
            else:
                current_x -= 1


class Pathfinder:
    """A*寻路算法"""
    
    @staticmethod
    def find_path(maze: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """寻找从start到end的路径"""
        if maze[start[1]][start[0]] == 1 or maze[end[1]][end[0]] == 1:
            return []
        
        open_set = {start}
        came_from = {}
        g_score = {start: 0}
        f_score = {start: Pathfinder._heuristic(start, end)}
        
        while open_set:
            current = min(open_set, key=lambda p: f_score.get(p, float('inf')))
            
            if current == end:
                return Pathfinder._reconstruct_path(came_from, current)
            
            open_set.remove(current)
            
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)
                
                if not (0 <= neighbor[0] < len(maze[0]) and 0 <= neighbor[1] < len(maze)):
                    continue
                if maze[neighbor[1]][neighbor[0]] == 1:
                    continue
                
                tentative_g = g_score[current] + 1
                
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + Pathfinder._heuristic(neighbor, end)
                    open_set.add(neighbor)
        
        return []
    
    @staticmethod
    def _heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    
    @staticmethod
    def _reconstruct_path(came_from: dict, current: Tuple[int, int]) -> List[Tuple[int, int]]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return path[::-1]