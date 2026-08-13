from datetime import date as Date, datetime, time, timedelta, timezone
from math import ceil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Course, CourseLesson, Lesson, LessonCompletion, LookupList, LookupListItem, User, UserCourse
from app.schemas import AuditEntryResponse, AuditSearchResponse


router = APIRouter(prefix="/admin/audit", tags=["audit administration"])
settings = get_settings()
PAGE_SIZE = 100

AUDIT_MODELS = {
    "lookup_list_items": LookupListItem,
    "lookup_lists": LookupList,
    "courses": Course,
    "lessons": Lesson,
    "course_lessons": CourseLesson,
    "user_courses": UserCourse,
    "lesson_completions": LessonCompletion,
    "users": User,
}


def require_admin(user: User) -> None:
    if user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def active_audit_tables(db: Session) -> list[str]:
    configured = (
        db.query(LookupListItem.list_item_value)
        .join(LookupList, LookupList.id == LookupListItem.list_id)
        .filter(
            func.lower(LookupList.list_name) == "dbtables",
            LookupList.active.is_(True),
            LookupListItem.active.is_(True),
        )
        .all()
    )
    return [value for (value,) in configured if value in AUDIT_MODELS]


def record_id_for(table_name: str, record: object) -> str:
    if table_name == "lookup_list_items":
        return f"{record.list_id} / {record.list_item_value}"
    if table_name == "course_lessons":
        return f"{record.course_id} / {record.lesson_id}"
    if table_name == "user_courses":
        return f"{record.user_id} / {record.course_id}"
    return str(record.id)


def query_table(
    db: Session,
    table_name: str,
    start_utc: datetime,
    end_utc: datetime,
    user_name: str | None,
    user_email: str | None,
) -> list[AuditEntryResponse]:
    model = AUDIT_MODELS[table_name]
    actor = aliased(User)
    activity_time = func.coalesce(model.update_time, model.create_time)
    actor_id = func.coalesce(model.update_id, model.create_id)
    query = (
        db.query(model, actor)
        .outerjoin(actor, actor.id == actor_id)
        .filter(activity_time >= start_utc, activity_time < end_utc)
    )
    if user_name:
        query = query.filter(func.lower(actor.name).contains(user_name.lower()))
    if user_email:
        query = query.filter(func.lower(actor.email).contains(user_email.lower()))

    entries: list[AuditEntryResponse] = []
    for record, acting_user in query.all():
        record_activity_time = record.update_time or record.create_time
        was_updated = bool(
            record.update_time
            and record.create_time
            and record.update_time > record.create_time
        )
        entries.append(
            AuditEntryResponse(
                activity_time=record_activity_time,
                user_id=acting_user.id if acting_user else None,
                user_name=acting_user.name if acting_user else "Deleted user",
                user_email=acting_user.email if acting_user else "",
                table_name=table_name,
                record_id=record_id_for(table_name, record),
                activity="Updated" if was_updated else "Created",
            )
        )
    return entries


@router.get("", response_model=AuditSearchResponse)
def search_audit_entries(
    date: Date = Query(..., description="Calendar date in the configured application timezone"),
    user_name: str | None = Query(default=None, max_length=120),
    user_email: str | None = Query(default=None, max_length=254),
    table_name: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditSearchResponse:
    require_admin(current_user)
    try:
        application_timezone = ZoneInfo(settings.app_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_TIMEZONE is not a valid IANA timezone",
        ) from exc

    start_local = datetime.combine(date, time.min, tzinfo=application_timezone)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    enabled_tables = active_audit_tables(db)
    if table_name:
        if table_name not in enabled_tables:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected table is not enabled for audit searching",
            )
        tables_to_query = [table_name]
    else:
        tables_to_query = enabled_tables

    cleaned_name = user_name.strip() if user_name and user_name.strip() else None
    cleaned_email = user_email.strip() if user_email and user_email.strip() else None
    entries: list[AuditEntryResponse] = []
    for enabled_table in tables_to_query:
        entries.extend(
            query_table(
                db,
                enabled_table,
                start_utc,
                end_utc,
                cleaned_name,
                cleaned_email,
            )
        )

    entries.sort(key=lambda entry: entry.activity_time, reverse=True)
    total = len(entries)
    total_pages = ceil(total / PAGE_SIZE) if total else 0
    offset = (page - 1) * PAGE_SIZE
    return AuditSearchResponse(
        date=date.isoformat(),
        timezone=settings.app_timezone,
        page=page,
        page_size=PAGE_SIZE,
        total=total,
        total_pages=total_pages,
        items=entries[offset : offset + PAGE_SIZE],
    )
