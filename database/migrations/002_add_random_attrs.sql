-- 装备随机属性系统迁移
-- 为 inventory_items 和 equipment 表添加 random_attrs 字段

-- 为 inventory_items 表添加随机属性字段
ALTER TABLE inventory_items ADD COLUMN random_attrs JSON NULL COMMENT '装备随机生成的实际属性值';

-- 为 equipment 表添加随机属性字段
ALTER TABLE equipment ADD COLUMN random_attrs JSON NULL COMMENT '装备随机生成的实际属性值';
