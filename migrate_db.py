import asyncio
from backend.database import engine
from sqlalchemy import text

async def migrate():
    async with engine.begin() as conn:
        # 检查字段是否存在
        try:
            await conn.execute(text("""
                ALTER TABLE character_skills
                ADD COLUMN proficiency INTEGER DEFAULT 0
            """))
            print("已添加proficiency字段")
        except Exception as e:
            if "Duplicate column" in str(e) or "duplicate column" in str(e).lower():
                print("proficiency字段已存在，跳过添加")
            else:
                raise
        
        # 更新现有记录
        await conn.execute(text("""
            UPDATE character_skills
            SET proficiency = 0
            WHERE proficiency IS NULL
        """))
        
        print("数据库迁移完成!")

if __name__ == "__main__":
    asyncio.run(migrate())