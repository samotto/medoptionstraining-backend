from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Course, CourseLesson, Lesson, LessonCompletion, User, UserCourse
from app.schemas import (
    CourseAssignmentResponse, CourseCreate, CourseDetailResponse, CourseLessonCreate,
    CourseResponse, CourseUpdate, CourseLessonOrder, LessonCompletionResponse, LessonCreate,
    LessonResponse, LessonSummary, LessonUpdate, MessageResponse,
)

router = APIRouter(tags=["training"])


def require_admin(user: User) -> None:
    if user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def get_course_or_404(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def get_lesson_or_404(db: Session, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.get("/courses", response_model=list[CourseDetailResponse])
def list_courses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    courses = db.query(Course).order_by(func.lower(Course.course_title)).all()
    assigned_ids = set()
    completed = set()
    if current_user.role != "Admin":
        assigned_ids = {row.course_id for row in db.query(UserCourse).filter(UserCourse.user_id == current_user.id)}
        courses = [course for course in courses if course.id in assigned_ids]
        completed = {(row.course_id, row.lesson_id) for row in db.query(LessonCompletion).filter(LessonCompletion.user_id == current_user.id)}
    results = []
    for course in courses:
        rows = (
            db.query(CourseLesson, Lesson)
            .join(Lesson, Lesson.id == CourseLesson.lesson_id)
            .filter(CourseLesson.course_id == course.id)
            .order_by(CourseLesson.sequence, func.lower(Lesson.lesson_title))
            .all()
        )
        lessons = [LessonSummary(id=l.id, lesson_title=l.lesson_title, url=l.url, description=l.description,
                                 sequence=cl.sequence, completed=(course.id, l.id) in completed) for cl, l in rows]
        base = CourseResponse.model_validate(course).model_dump()
        results.append(CourseDetailResponse(**base, lessons=lessons, assigned=course.id in assigned_ids,
                                            completed_lessons=sum(item.completed for item in lessons), total_lessons=len(lessons)))
    return results


@router.post("/courses", response_model=CourseResponse, status_code=201)
def create_course(payload: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    now = datetime.now(timezone.utc)
    course = Course(**payload.model_dump(), create_time=now, update_time=now, create_id=current_user.id, update_id=current_user.id)
    db.add(course); db.commit(); db.refresh(course)
    return course


@router.put("/courses/{course_id}", response_model=CourseResponse)
def update_course(course_id: int, payload: CourseUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); course = get_course_or_404(db, course_id)
    course.course_title = payload.course_title; course.description = payload.description
    course.update_time = datetime.now(timezone.utc); course.update_id = current_user.id
    db.commit(); db.refresh(course); return course


@router.delete("/courses/{course_id}", response_model=MessageResponse)
def delete_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); course = get_course_or_404(db, course_id)
    db.delete(course); db.commit(); return MessageResponse(message="course deleted")


@router.get("/lessons", response_model=list[LessonResponse])
def list_lessons(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Lesson).order_by(func.lower(Lesson.lesson_title)).all()


@router.post("/lessons", response_model=LessonResponse, status_code=201)
def create_lesson(payload: LessonCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); now = datetime.now(timezone.utc)
    lesson = Lesson(**payload.model_dump(), create_time=now, update_time=now, create_id=current_user.id, update_id=current_user.id)
    db.add(lesson); db.commit(); db.refresh(lesson); return lesson


@router.put("/lessons/{lesson_id}", response_model=LessonResponse)
def update_lesson(lesson_id: int, payload: LessonUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); lesson = get_lesson_or_404(db, lesson_id)
    lesson.lesson_title = payload.lesson_title; lesson.url = payload.url; lesson.description = payload.description
    lesson.update_time = datetime.now(timezone.utc); lesson.update_id = current_user.id
    db.commit(); db.refresh(lesson); return lesson


@router.delete("/lessons/{lesson_id}", response_model=MessageResponse)
def delete_lesson(lesson_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); lesson = get_lesson_or_404(db, lesson_id)
    db.delete(lesson); db.commit(); return MessageResponse(message="lesson deleted")


@router.post("/courses/{course_id}/lessons", response_model=LessonSummary, status_code=201)
def add_course_lesson(course_id: int, payload: CourseLessonCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); get_course_or_404(db, course_id); lesson = get_lesson_or_404(db, payload.lesson_id)
    if db.get(CourseLesson, (course_id, payload.lesson_id)):
        raise HTTPException(status_code=409, detail="Lesson is already in this course")
    now = datetime.now(timezone.utc)
    row = CourseLesson(course_id=course_id, lesson_id=payload.lesson_id, sequence=payload.sequence,
                       create_time=now, update_time=now, create_id=current_user.id, update_id=current_user.id)
    db.add(row); db.commit()
    return LessonSummary(id=lesson.id, lesson_title=lesson.lesson_title, url=lesson.url, description=lesson.description, sequence=row.sequence)


@router.delete("/courses/{course_id}/lessons/{lesson_id}", response_model=MessageResponse)
def remove_course_lesson(course_id: int, lesson_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); row = db.get(CourseLesson, (course_id, lesson_id))
    if not row: raise HTTPException(status_code=404, detail="Course lesson not found")
    db.delete(row); db.commit(); return MessageResponse(message="lesson removed from course")


@router.put("/courses/{course_id}/lessons/order", response_model=MessageResponse)
def reorder_course_lessons(course_id: int, payload: CourseLessonOrder, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); get_course_or_404(db, course_id)
    rows = db.query(CourseLesson).filter(CourseLesson.course_id == course_id).all()
    if len(payload.lesson_ids) != len(set(payload.lesson_ids)) or set(payload.lesson_ids) != {row.lesson_id for row in rows}:
        raise HTTPException(status_code=422, detail="Lesson order must contain every course lesson exactly once")
    now = datetime.now(timezone.utc); by_lesson = {row.lesson_id: row for row in rows}
    for sequence, lesson_id in enumerate(payload.lesson_ids, 1):
        row = by_lesson[lesson_id]; row.sequence = sequence; row.update_time = now; row.update_id = current_user.id
    db.commit(); return MessageResponse(message="lesson order updated")


@router.get("/users/{user_id}/courses", response_model=list[CourseDetailResponse])
def user_courses(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "Admin" and current_user.id != user_id: raise HTTPException(status_code=403, detail="Access denied")
    if not db.get(User, user_id): raise HTTPException(status_code=404, detail="User not found")
    # Reuse the same response shape while explicitly querying the requested user.
    assignments = db.query(UserCourse).filter(UserCourse.user_id == user_id).all()
    completed = {(r.course_id, r.lesson_id) for r in db.query(LessonCompletion).filter(LessonCompletion.user_id == user_id)}
    output = []
    for assignment in assignments:
        course = get_course_or_404(db, assignment.course_id)
        rows = db.query(CourseLesson, Lesson).join(Lesson).filter(CourseLesson.course_id == course.id).order_by(CourseLesson.sequence).all()
        lessons = [LessonSummary(id=l.id, lesson_title=l.lesson_title, url=l.url, description=l.description, sequence=cl.sequence,
                                 completed=(course.id, l.id) in completed) for cl, l in rows]
        output.append(CourseDetailResponse(**CourseResponse.model_validate(course).model_dump(), lessons=lessons, assigned=True,
                                           completed_lessons=sum(x.completed for x in lessons), total_lessons=len(lessons)))
    return output


@router.post("/users/{user_id}/courses/{course_id}", response_model=CourseAssignmentResponse, status_code=201)
def assign_course(user_id: int, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); get_course_or_404(db, course_id)
    if not db.get(User, user_id): raise HTTPException(status_code=404, detail="User not found")
    if db.get(UserCourse, (user_id, course_id)): raise HTTPException(status_code=409, detail="Course is already assigned")
    now = datetime.now(timezone.utc); row = UserCourse(user_id=user_id, course_id=course_id, assigned_time=now,
        create_time=now, update_time=now, create_id=current_user.id, update_id=current_user.id)
    db.add(row); db.commit(); return CourseAssignmentResponse(user_id=user_id, course_id=course_id, assigned_time=now)


@router.delete("/users/{user_id}/courses/{course_id}", response_model=MessageResponse)
def unassign_course(user_id: int, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user); row = db.get(UserCourse, (user_id, course_id))
    if not row: raise HTTPException(status_code=404, detail="Course assignment not found")
    db.query(LessonCompletion).filter(LessonCompletion.user_id == user_id, LessonCompletion.course_id == course_id).delete()
    db.delete(row); db.commit(); return MessageResponse(message="course unassigned")


@router.put("/users/{user_id}/courses/{course_id}/lessons/{lesson_id}/completion", response_model=LessonCompletionResponse)
def complete_lesson(user_id: int, course_id: int, lesson_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "Admin" and current_user.id != user_id: raise HTTPException(status_code=403, detail="Access denied")
    if not db.get(UserCourse, (user_id, course_id)): raise HTTPException(status_code=404, detail="Course is not assigned")
    if not db.get(CourseLesson, (course_id, lesson_id)): raise HTTPException(status_code=404, detail="Lesson is not in this course")
    now = datetime.now(timezone.utc)
    row = db.query(LessonCompletion).filter_by(user_id=user_id, course_id=course_id, lesson_id=lesson_id).first()
    if not row:
        row = LessonCompletion(user_id=user_id, course_id=course_id, lesson_id=lesson_id, completion_time=now,
            create_time=now, update_time=now, create_id=current_user.id, update_id=current_user.id); db.add(row)
    else:
        row.completion_time=now; row.update_time=now; row.update_id=current_user.id
    db.commit(); return LessonCompletionResponse(user_id=user_id, course_id=course_id, lesson_id=lesson_id, completion_time=now)
