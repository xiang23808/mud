from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.database import Base
import enum

class CharacterClass(str, enum.Enum):
    WARRIOR = "warrior"
    MAGE = "mage"
    TAOIST = "taoist"

class Character(Base):
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(50), unique=True, index=True, nullable=False)
    char_class = Column(Enum(CharacterClass), nullable=False)
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    gold = Column(Integer, default=0)
    yuanbao = Column(Integer, default=0)
    
    # 属性
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
    mp = Column(Integer, default=50)
    max_mp = Column(Integer, default=50)
    attack = Column(Integer, default=10)
    defense = Column(Integer, default=5)
    luck = Column(Integer, default=0)
    pk_value = Column(Integer, default=0)
    
    # 位置
    map_id = Column(String(50), default="main_city")
    pos_x = Column(Integer, default=0)
    pos_y = Column(Integer, default=0)
    
    user = relationship("User", back_populates="characters")