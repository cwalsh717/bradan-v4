from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models so Alembic can detect them
from app.models.dashboard import *  # noqa: E402, F401, F403
from app.models.stocks import *  # noqa: E402, F401, F403
from app.models.dcf import *  # noqa: E402, F401, F403
from app.models.users import *  # noqa: E402, F401, F403
from app.models.shared import *  # noqa: E402, F401, F403
