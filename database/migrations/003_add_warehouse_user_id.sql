-- 添加user_id字段用于仓库共享 (MySQL语法)
ALTER TABLE inventory_items ADD COLUMN user_id INTEGER NULL;

-- 添加外键约束
ALTER TABLE inventory_items ADD CONSTRAINT fk_inventory_user FOREIGN KEY (user_id) REFERENCES users(id);

-- 创建索引
CREATE INDEX idx_inventory_items_user_id ON inventory_items(user_id);

-- 迁移现有仓库数据：将character_id对应的user_id填入
UPDATE inventory_items i
JOIN characters c ON c.id = i.character_id
SET i.user_id = c.user_id
WHERE i.storage_type = 'warehouse' AND i.user_id IS NULL;