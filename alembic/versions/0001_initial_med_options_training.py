"""Initial Med Options Training schema.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def audit_columns(nullable_actor=False):
    return [
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("create_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=nullable_actor),
        sa.Column("update_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=nullable_actor),
    ]


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False), sa.Column("role", sa.Text(), nullable=False, server_default="Basic"),
        sa.Column("password_hash", sa.Text()), sa.Column("google_id", sa.Text()),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False), sa.Column("update_time", sa.DateTime(timezone=True)),
        sa.Column("create_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("update_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("last_logon_time", sa.DateTime(timezone=True)),
        sa.CheckConstraint("role IN ('Admin', 'Basic', 'Pending')", name="ck_users_role"))
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("ix_users_name_lower", "users", [sa.text("lower(name)")], unique=True)

    op.create_table("courses", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_title", sa.Text(), nullable=False), sa.Column("description", sa.Text()), *audit_columns())
    op.create_index("ix_courses_course_title", "courses", ["course_title"])
    op.create_table("lessons", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_title", sa.Text(), nullable=False), sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()), *audit_columns())
    op.create_index("ix_lessons_lesson_title", "lessons", ["lesson_title"])
    op.create_table("course_lessons", sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"), *audit_columns())
    op.create_table("user_courses", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_time", sa.DateTime(timezone=True), nullable=False), *audit_columns())
    op.create_table("lesson_completions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completion_time", sa.DateTime(timezone=True), nullable=False), *audit_columns(),
        sa.UniqueConstraint("user_id", "course_id", "lesson_id", name="uq_lesson_completion"))

    op.create_table("lookup_lists", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("list_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("sort_mode", sa.Text(), nullable=False, server_default="Alphabetical"),
        sa.Column("default_item_value", sa.Text()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), *audit_columns(),
        sa.CheckConstraint("sort_mode IN ('Alphabetical', 'Sequence')", name="ck_lookup_lists_sort_mode"))
    op.create_table("lookup_list_items", sa.Column("list_id", sa.Integer(), sa.ForeignKey("lookup_lists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("list_item_value", sa.Text(), primary_key=True), sa.Column("list_item_text", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), *audit_columns(),
        sa.CheckConstraint("sequence IS NULL OR sequence >= 0", name="ck_lookup_list_items_sequence"))
    op.create_foreign_key("fk_lookup_lists_default_item", "lookup_lists", "lookup_list_items",
                          ["id", "default_item_value"], ["list_id", "list_item_value"], use_alter=True)


def downgrade():
    op.drop_constraint("fk_lookup_lists_default_item", "lookup_lists", type_="foreignkey")
    for table in ("lookup_list_items", "lookup_lists", "lesson_completions", "user_courses", "course_lessons", "lessons", "courses", "users"):
        op.drop_table(table)
