import json
from pathlib import Path
from typing import Dict, Any

class DataLoader:
    """游戏数据加载器"""
    
    _cache: Dict[str, Any] = {}
    
    @classmethod
    def load(cls, path: str) -> dict:
        """加载JSON数据文件"""
        if path in cls._cache:
            return cls._cache[path]
        
        try:
            with open(Path("data") / path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cls._cache[path] = data
                return data
        except FileNotFoundError:
            return {}
    
    @classmethod
    def get_monster(cls, monster_id: str) -> dict:
        """获取怪物数据"""
        monsters = cls.load("monsters/monsters.json")
        return monsters.get(monster_id, {})
    
    @classmethod
    def get_item(cls, item_id: str) -> dict:
        """获取物品数据"""
        # 搜索所有物品文件
        for file in ["items/weapons.json", "items/armors.json", "items/consumables.json", "items/accessories.json"]:
            items = cls.load(file)
            if item_id in items:
                return items[item_id]
        return {}
    
    @classmethod
    def get_skill(cls, skill_id: str, char_class: str = None) -> dict:
        """获取技能数据"""
        if char_class:
            skills = cls.load(f"skills/{char_class}.json")
            if skill_id in skills:
                return skills[skill_id]
        
        # 搜索所有职业
        for cls_name in ["warrior", "mage", "taoist"]:
            skills = cls.load(f"skills/{cls_name}.json")
            if skill_id in skills:
                return skills[skill_id]
        return {}
    
    @classmethod
    def get_quality(cls, quality: str) -> dict:
        """获取品质配置"""
        qualities = cls.load("config/quality.json")
        return qualities.get(quality, qualities.get("white", {}))
    
    @classmethod
    def get_all_skills(cls, char_class: str) -> dict:
        """获取职业所有技能"""
        return cls.load(f"skills/{char_class}.json")
    
    @classmethod
    def get_shop_items(cls, shop_type: str) -> dict:
        """获取商店物品"""
        if shop_type == "weapon":
            items = cls.load("items/weapons.json")
        elif shop_type == "armor":
            items = cls.load("items/armors.json")
        elif shop_type == "consumable":
            items = cls.load("items/consumables.json")
        elif shop_type == "skill":
            # 返回所有技能（包括掉落获取的）
            all_skills = {}
            for cls_name in ["warrior", "mage", "taoist"]:
                skills = cls.load(f"skills/{cls_name}.json")
                for sid, skill in skills.items():
                    all_skills[sid] = skill
            return all_skills
        else:
            return {}
        
        # 过滤可购买物品
        return {k: v for k, v in items.items() if v.get("buy_price", 0) > 0}
    
    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        cls._cache.clear()