import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.database import SessionLocal
from app.models import Course, CourseLesson, Lesson, LookupList, LookupListItem, User


settings = get_settings()


def load_seed_data() -> dict:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "seed_training.json"
    with seed_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def ensure_admin_user(db: Session) -> User:
    admin_email = settings.seed_admin_email.strip().lower()
    admin = db.query(User).filter(func.lower(User.email) == admin_email).first()
    if admin:
        # If the seed address was registered before initial seeding, promote it
        # and establish the seed password once. Later password changes survive
        # normal application restarts because an existing admin is left alone.
        needs_promotion = admin.role != "Admin"
        if needs_promotion:
            admin.role = "Admin"
        if needs_promotion or settings.seed_admin_force_password_reset:
            admin.password_hash = hash_password(settings.seed_admin_password)
        if admin.last_logon_time is None:
            admin.last_logon_time = datetime.now(timezone.utc)
        if admin.create_id is None:
            admin.create_id = admin.id
        if admin.update_id is None:
            admin.update_id = admin.id
        if admin.update_time is None:
            admin.update_time = admin.create_time
        if needs_promotion or settings.seed_admin_force_password_reset:
            admin.update_time = datetime.now(timezone.utc)
            admin.update_id = admin.id
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin

    now = datetime.now(timezone.utc)
    admin = User(
        name="Sam Otto" if admin_email == "sam@overturegroup.com" else admin_email.split("@", 1)[0],
        email=admin_email,
        role="Admin",
        password_hash=hash_password(settings.seed_admin_password),
        google_id=None,
        create_time=now,
        update_time=now,
        last_logon_time=now,
    )
    db.add(admin)
    db.flush()
    admin.create_id = admin.id
    admin.update_id = admin.id
    db.commit()
    db.refresh(admin)
    return admin


def seed_training(db: Session, admin_user: User) -> tuple[int, int]:
    data = load_seed_data(); now = datetime.now(timezone.utc); course_count = lesson_count = 0
    lessons_by_title = {}
    for item in data.get("lessons", []):
        lesson = db.query(Lesson).filter(func.lower(Lesson.lesson_title) == item["lesson_title"].lower()).first()
        if not lesson:
            lesson = Lesson(**item, create_time=now, update_time=now, create_id=admin_user.id, update_id=admin_user.id)
            db.add(lesson); db.flush(); lesson_count += 1
        lessons_by_title[item["lesson_title"]] = lesson
    for item in data.get("courses", []):
        course = db.query(Course).filter(func.lower(Course.course_title) == item["course_title"].lower()).first()
        if not course:
            course = Course(course_title=item["course_title"], description=item.get("description"), create_time=now,
                            update_time=now, create_id=admin_user.id, update_id=admin_user.id)
            db.add(course); db.flush(); course_count += 1
        for sequence, title in enumerate(item.get("lessons", []), 1):
            lesson = lessons_by_title[title]
            if not db.get(CourseLesson, (course.id, lesson.id)):
                db.add(CourseLesson(course_id=course.id, lesson_id=lesson.id, sequence=sequence, create_time=now,
                                    update_time=now, create_id=admin_user.id, update_id=admin_user.id))
    db.commit(); return course_count, lesson_count


def seed_role_lookup_list(db: Session, admin_user: User) -> int:
    lookup_list = db.query(LookupList).filter(func.lower(LookupList.list_name) == "role").first()
    now = datetime.now(timezone.utc)
    if not lookup_list:
        lookup_list = LookupList(
            list_name="Role",
            description="Application user roles",
            sort_mode="Alphabetical",
            default_item_value=None,
            active=True,
            create_time=now,
            update_time=now,
            create_id=admin_user.id,
            update_id=admin_user.id,
        )
        db.add(lookup_list)
        db.flush()
    else:
        list_changed = (
            lookup_list.sort_mode != "Alphabetical"
            or not lookup_list.active
        )
        if list_changed:
            lookup_list.sort_mode = "Alphabetical"
            lookup_list.active = True
            lookup_list.update_time = now
            lookup_list.update_id = admin_user.id
            db.add(lookup_list)

    inserted_count = 0
    for value in ("Admin", "Basic", "Pending"):
        existing = (
            db.query(LookupListItem)
            .filter(
                LookupListItem.list_id == lookup_list.id,
                LookupListItem.list_item_value == value,
            )
            .first()
        )
        if existing:
            item_changed = (
                existing.list_item_text != value
                or existing.sequence != 0
                or not existing.active
            )
            if item_changed:
                existing.list_item_text = value
                existing.sequence = 0
                existing.active = True
                existing.update_time = now
                existing.update_id = admin_user.id
                db.add(existing)
        else:
            db.add(LookupListItem(
                list_id=lookup_list.id,
                list_item_value=value,
                list_item_text=value,
                sequence=0,
                active=True,
                create_time=now,
                update_time=now,
                create_id=admin_user.id,
                update_id=admin_user.id,
            ))
            inserted_count += 1
    db.flush()
    if lookup_list.default_item_value != "Basic":
        lookup_list.default_item_value = "Basic"
        lookup_list.update_time = now
        lookup_list.update_id = admin_user.id
        db.add(lookup_list)
    db.commit()
    return inserted_count


def seed_db_tables_lookup_list(db: Session, admin_user: User) -> int:
    lookup_list = db.query(LookupList).filter(func.lower(LookupList.list_name) == "dbtables").first()
    now = datetime.now(timezone.utc)
    if not lookup_list:
        lookup_list = LookupList(
            list_name="DBTables",
            description="Database tables included in the lightweight audit search",
            sort_mode="Alphabetical",
            default_item_value=None,
            active=True,
            create_time=now,
            update_time=now,
            create_id=admin_user.id,
            update_id=admin_user.id,
        )
        db.add(lookup_list)
        db.flush()

    inserted_count = 0
    for table_name in ("course_lessons", "courses", "lessons", "lookup_list_items", "lookup_lists", "user_courses", "user_courses_lessons", "users"):
        existing = (
            db.query(LookupListItem)
            .filter(
                LookupListItem.list_id == lookup_list.id,
                LookupListItem.list_item_value == table_name,
            )
            .first()
        )
        if existing:
            continue
        db.add(
            LookupListItem(
                list_id=lookup_list.id,
                list_item_value=table_name,
                list_item_text=table_name,
                sequence=0,
                active=True,
                create_time=now,
                update_time=now,
                create_id=admin_user.id,
                update_id=admin_user.id,
            )
        )
        inserted_count += 1
    db.commit()
    return inserted_count


def run_seed() -> None:
    db = SessionLocal()
    try:
        admin_user = ensure_admin_user(db)
        inserted_roles = seed_role_lookup_list(db, admin_user)
        inserted_tables = seed_db_tables_lookup_list(db, admin_user)
        courses, lessons = seed_training(db, admin_user)
        print(
            f"Seed complete. Inserted {inserted_roles} role values, "
            f"{inserted_tables} audit table values, {courses} courses, and {lessons} lessons."
        )
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
