from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base
import enum

class GuildRank(str, enum.Enum):
    LEADER = "leader"
    VICE_LEADER = "vice_leader"
    ELDER = "elder"
    MEMBER = "member"

class Guild(Base):
    __tablename__ = "guilds"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    leader_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    level = Column(Integer, default=1)
    gold = Column(Integer, default=0)
    notice = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    members = relationship("GuildMember", back_populates="guild")


class GuildMember(Base):
    __tablename__ = "guild_members"
    
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(Integer, ForeignKey("guilds.id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, unique=True)
    rank = Column(Enum(GuildRank), default=GuildRank.MEMBER)
    contribution = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    guild = relationship("Guild", back_populates="members")