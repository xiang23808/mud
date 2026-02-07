from sqlalchemy import Column, Integer, String, ForeignKey, Enum, JSON
from backend.database import Base
import enum

class StorageType(str, enum.Enum):
    INVENTORY = "inventory"
    WAREHOUSE = "warehouse"

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 仓库共享用
    storage_type = Column(Enum(StorageType), default=StorageType.INVENTORY)
    item_id = Column(String(50), nullable=False)
    quality = Column(String(20), default="white")
    slot = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    # 新增：装备随机属性存储
    random_attrs = Column(JSON, nullable=True)  # 存储格式: {"attack_min": 12, "attack_max": 18, "multiplier": 1.05, ...}
    # 符文之语系统
    sockets = Column(Integer, default=0)  # 孔数量 (0-6)
    socketed_runes = Column(JSON, nullable=True)  # 已镶嵌符文 ["rune_tir", "rune_el"]
    runeword_id = Column(String(50), nullable=True)  # 完成的符文之语ID


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)
    slot = Column(String(20), nullable=False)  # weapon, head, body, boots, ring, necklace
    item_id = Column(String(50), nullable=False)
    quality = Column(String(20), default="white")
    # 新增：装备随机属性存储
    random_attrs = Column(JSON, nullable=True)  # 存储格式: {"attack_min": 12, "attack_max": 18, "multiplier": 1.05, ...}
    # 符文之语系统
    sockets = Column(Integer, default=0)  # 孔数量 (0-6)
    socketed_runes = Column(JSON, nullable=True)  # 已镶嵌符文 ["rune_tir", "rune_el"]
    runeword_id = Column(String(50), nullable=True)  # 完成的符文之语ID


class CharacterSkill(Base):
    __tablename__ = "character_skills"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)
    skill_id = Column(String(50), nullable=False)
    level = Column(Integer, default=1)
    proficiency = Column(Integer, default=0)  # 熟练度 0-1000
