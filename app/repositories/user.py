from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    SEARCH_FIELDS = (User.email, User.full_name)
    SORT_FIELDS = {
        "created_at": User.created_at,
        "email": User.email,
        "full_name": User.full_name,
    }

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            self._select().where(User.email == email.lower())
        )
