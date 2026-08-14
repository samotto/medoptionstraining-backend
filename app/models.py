from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('Admin', 'Basic', 'Pending')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="Basic", server_default="Basic")
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    update_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    create_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    update_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_logon_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lesson_title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class CourseLesson(Base):
    __tablename__ = "course_lessons"

    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class UserCourse(Base):
    __tablename__ = "user_courses"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    assigned_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class LessonCompletion(Base):
    __tablename__ = "user_courses_lessons"
    __table_args__ = (UniqueConstraint("user_id", "course_id", "lesson_id", name="uq_lesson_completion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    completion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class LookupList(Base):
    __tablename__ = "lookup_lists"
    __table_args__ = (
        CheckConstraint(
            "sort_mode IN ('Alphabetical', 'Sequence')",
            name="ck_lookup_lists_sort_mode",
        ),
        ForeignKeyConstraint(
            ["id", "default_item_value"],
            ["lookup_list_items.list_id", "lookup_list_items.list_item_value"],
            name="fk_lookup_lists_default_item",
            use_alter=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement="ignore_fk",
    )
    list_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_mode: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Alphabetical",
        server_default="Alphabetical",
    )
    default_item_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class LookupListItem(Base):
    __tablename__ = "lookup_list_items"
    __table_args__ = (
        CheckConstraint("sequence IS NULL OR sequence >= 0", name="ck_lookup_list_items_sequence"),
    )

    list_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lookup_lists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    list_item_value: Mapped[str] = mapped_column(Text, primary_key=True)
    list_item_text: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    create_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    update_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
