import random
from typing import List, Tuple, Set

class MazeGenerator:
    """12x12迷宫生成器 - 使用递归回溯算法"""
    
    def __init__(self, width: int = 24, height: int = 24):
        self.width = width
        self.height = height
    
    def generate(self) -> List[List[int]]:
        """生成迷宫，0=通道，1=墙壁"""
        # 初始化全墙
        maze = [[1] * self.width for _ in range(self.height)]
        
        # 递归回溯生成
        self._carve(maze, 1, 1)
        
        # 设置入口和出口并确保可到达
        entrance = (1, 0)
        exit_pos = (self.width - 2, self.height - 1)
        
        # 确保入口和出口位置是通道
        maze[entrance[1]][entrance[0]] = 0
        maze[exit_pos[1]][exit_pos[0]] = 0
        
        # 确保入口和出口周围有通道连接
        # 入口向下连接
        if entrance[1] + 1 < self.height:
            maze[entrance[1] + 1][entrance[0]] = 0
        
        # 出口向上连接
        if exit_pos[1] - 1 >= 0:
            maze[exit_pos[1] - 1][exit_pos[0]] = 0
        
        return maze
    
    def _carve(self, maze: List[List[int]], x: int, y: int):
        """递归挖掘通道"""
        maze[y][x] = 0
        directions = [(0, -2), (0, 2), (-2, 0), (2, 0)]
        random.shuffle(directions)
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 < nx < self.width - 1 and 0 < ny < self.height - 1 and maze[ny][nx] == 1:
                maze[y + dy // 2][x + dx // 2] = 0
                self._carve(maze, nx, ny)


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