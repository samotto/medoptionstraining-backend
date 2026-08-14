"""Rename completion table to the user-course-lesson contract name.

Revision ID: 0002_completion_table
Revises: 0001_initial
"""
from alembic import op


revision = "0002_completion_table"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("lesson_completions", "user_courses_lessons")


def downgrade():
    op.rename_table("user_courses_lessons", "lesson_completions")
