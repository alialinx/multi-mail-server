from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    quota: Mapped[int] = mapped_column(BigInteger, default=0)
    autoreply_active: Mapped[bool] = mapped_column(Boolean, default=False)
    autoreply_subject: Mapped[str] = mapped_column(String(255), default="")
    autoreply_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alias(Base):
    __tablename__ = "aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"))
    address: Mapped[str] = mapped_column(String(255))
    goto_address: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MailStat(Base):
    __tablename__ = "mail_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[str] = mapped_column(String(10))        # YYYY-MM-DD
    domain: Mapped[str] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(10))  # in | out | bounce
    count: Mapped[int] = mapped_column(Integer, default=0)


def init_db():
    try:
        Base.metadata.create_all(engine)
    except (IntegrityError, ProgrammingError):
        # The API startup thread and the bootstrap step can both create the
        # tables at the same time; the definitions are identical, so a
        # duplicate-table race here is safe to ignore.
        pass
