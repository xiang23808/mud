-- 添加技能熟练度字段
ALTER TABLE character_skills ADD COLUMN proficiency INTEGER DEFAULT 0 COMMENT '技能熟练度 0-1000，每1000升1级';

-- 更新现有技能的熟练度为0
UPDATE character_skills SET proficiency = 0 WHERE proficiency IS NULL;
