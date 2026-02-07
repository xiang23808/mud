-- Migration: Add runeword system columns to inventory_items and equipment tables
-- Run this script to add the new columns for the runeword system

-- Add columns to inventory_items table
ALTER TABLE inventory_items
ADD COLUMN IF NOT EXISTS sockets INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS socketed_runes JSON,
ADD COLUMN IF NOT EXISTS runeword_id VARCHAR(50);

-- Add columns to equipment table
ALTER TABLE equipment
ADD COLUMN IF NOT EXISTS sockets INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS socketed_runes JSON,
ADD COLUMN IF NOT EXISTS runeword_id VARCHAR(50);
