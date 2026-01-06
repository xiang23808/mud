-- 添加魔法和魔御属性到角色表
ALTER TABLE characters ADD COLUMN magic INTEGER DEFAULT 0;
ALTER TABLE characters ADD COLUMN magic_defense INTEGER DEFAULT 0;