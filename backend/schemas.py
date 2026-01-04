from typing import Optional
from pydantic import BaseModel
from backend.models.character import CharacterClass

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str
    user_id: int

class CharacterCreate(BaseModel):
    name: str
    char_class: CharacterClass

class CharacterResponse(BaseModel):
    id: int
    name: str
    char_class: CharacterClass
    level: int
    exp: int
    gold: int
    yuanbao: int
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    attack: int
    defense: int
    luck: int
    map_id: str
    pos_x: int
    pos_y: int

    class Config:
        from_attributes = True