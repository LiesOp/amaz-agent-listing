from sqlalchemy.ext.asyncio import AsyncSession


async def seed_reference_data(session: AsyncSession) -> None:
    """No fixed rule-source seed data is needed for manual rule management."""
    await session.commit()
