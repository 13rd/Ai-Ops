import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.base import AsyncSessionLocal
from app.models.user import User, UserRole

async def seed_users():

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            admin_user = User(
                email="admin@example.com",
                username="admin",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin_user)
            print("✓ Created admin user (username: admin, password: admin123)")
        else:
            print("✓ Admin user already exists")

        result = await db.execute(select(User).where(User.username == "operator"))
        operator_user = result.scalar_one_or_none()

        if not operator_user:
            operator_user = User(
                email="operator@example.com",
                username="operator",
                hashed_password=get_password_hash("operator123"),
                role=UserRole.OPERATOR,
                is_active=True,
            )
            db.add(operator_user)
            print("✓ Created operator user (username: operator, password: operator123)")
        else:
            print("✓ Operator user already exists")

        await db.commit()
        print("\n✓ Database seeded successfully!")

if __name__ == "__main__":
    print("Seeding database...")
    asyncio.run(seed_users())
