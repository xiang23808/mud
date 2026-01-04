import asyncio
from backend.game.map_manager import map_manager

class MonsterSpawner:
    """怪物刷新器"""
    
    def __init__(self, interval: int = 60):
        self.interval = interval
        self.running = False
    
    async def start(self):
        """启动刷新循环"""
        self.running = True
        while self.running:
            await asyncio.sleep(self.interval)
            self.respawn_all()
    
    def stop(self):
        """停止刷新"""
        self.running = False
    
    def respawn_all(self):
        """刷新所有地图的怪物"""
        for map_id, instance in map_manager.instances.items():
            instance.respawn_check()


spawner = MonsterSpawner()