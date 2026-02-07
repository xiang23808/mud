"""Migration: Add runeword system columns to inventory_items and equipment tables"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def migrate():
    """Add runeword columns to database tables"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return

    engine = create_async_engine(database_url, echo=True)

    async with engine.begin() as conn:
        # Check and add columns to inventory_items
        result = await conn.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_items' AND COLUMN_NAME = 'sockets'
        """))
        if not result.fetchone():
            print("Adding columns to inventory_items...")
            await conn.execute(text("ALTER TABLE inventory_items ADD COLUMN sockets INT DEFAULT 0"))
            await conn.execute(text("ALTER TABLE inventory_items ADD COLUMN socketed_runes JSON"))
            await conn.execute(text("ALTER TABLE inventory_items ADD COLUMN runeword_id VARCHAR(50)"))
            print("inventory_items columns added!")
        else:
            print("inventory_items already has runeword columns")

        # Check and add columns to equipment
        result = await conn.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'equipment' AND COLUMN_NAME = 'sockets'
        """))
        if not result.fetchone():
            print("Adding columns to equipment...")
            await conn.execute(text("ALTER TABLE equipment ADD COLUMN sockets INT DEFAULT 0"))
            await conn.execute(text("ALTER TABLE equipment ADD COLUMN socketed_runes JSON"))
            await conn.execute(text("ALTER TABLE equipment ADD COLUMN runeword_id VARCHAR(50)"))
            print("equipment columns added!")
        else:
            print("equipment already has runeword columns")

    await engine.dispose()
    print("Migration completed!")


if __name__ == "__main__":
    asyncio.run(migrate())
