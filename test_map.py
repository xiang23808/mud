"""测试地图系统"""
from backend.game.maze import MazeGenerator
from backend.game.map_manager import MapInstance
import json

# 测试迷宫生成
print("=== 测试迷宫生成 ===")
gen = MazeGenerator()
maze = gen.generate()

# 统计通路数量
passable = sum(1 for row in maze for cell in row if cell == 0)
total = 24 * 24
print(f"通路格子数: {passable}/{total} ({passable/total*100:.1f}%)")

# 检查入口和出口
entrance = (1, 0)
exit_pos = (22, 23)
print(f"入口 {entrance} 是否可通行: {maze[entrance[1]][entrance[0]] == 0}")
print(f"出口 {exit_pos} 是否可通行: {maze[exit_pos[1]][exit_pos[0]] == 0}")

# 测试地图实例
print("\n=== 测试地图实例 ===")
with open("data/maps/maps.json", "r", encoding="utf-8") as f:
    maps_config = json.load(f)

# 测试沃玛森林
woma_config = maps_config.get("woma_forest", {})
print(f"沃玛森林配置: {woma_config.get('name')}")
print(f"怪物类型: {woma_config.get('monsters')}")
print(f"怪物数量: {woma_config.get('monster_count')}")

instance = MapInstance("woma_forest", woma_config)
print(f"实际生成怪物数量: {len([m for m in instance.monsters.values() if not m.get('is_boss')])}")
print(f"Boss数量: {len([m for m in instance.monsters.values() if m.get('is_boss')])}")
print(f"总怪物数: {len(instance.monsters)}")

# 显示怪物分布
if instance.monsters:
    print(f"怪物位置示例（前5个）:")
    for i, (pos, monster) in enumerate(list(instance.monsters.items())[:5]):
        print(f"  {pos}: {monster['type']} (Boss: {monster.get('is_boss', False)})")

print("\n测试完成！")