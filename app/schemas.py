from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


UserRole = Literal["Admin", "Basic", "Pending"]
ManagedUserRole = Literal["Admin", "Basic"]
LookupSortMode = Literal["Alphabetical", "Sequence"]


class HealthResponse(BaseModel):
    status: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class RegistrationResponse(BaseModel):
    message: str
    email: EmailStr


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=1)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class CompletePasswordResetRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)


class UserLoginResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserMeResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: ManagedUserRole = "Basic"


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    role: UserRole


class UserProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    create_time: datetime
    update_time: datetime | None
    create_id: int | None
    update_id: int | None
    last_logon_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=72)


class LessonSummary(BaseModel):
    id: int
    lesson_title: str
    url: str
    description: str | None
    sequence: int
    completed: bool = False
    completion_time: datetime | None = None


class CourseBase(BaseModel):
    course_title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(CourseBase):
    pass


class CourseResponse(CourseBase):
    id: int
    create_time: datetime
    update_time: datetime
    create_id: int
    update_id: int

    model_config = ConfigDict(from_attributes=True)


class CourseDetailResponse(CourseResponse):
    lessons: list[LessonSummary] = []
    assigned: bool = False
    completed_lessons: int = 0
    total_lessons: int = 0
    completion_time: datetime | None = None


class LessonBase(BaseModel):
    lesson_title: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=4000)


class LessonCreate(LessonBase):
    pass


class LessonUpdate(LessonBase):
    pass


class LessonResponse(LessonBase):
    id: int
    create_time: datetime
    update_time: datetime
    create_id: int
    update_id: int
    model_config = ConfigDict(from_attributes=True)


class CourseLessonCreate(BaseModel):
    lesson_id: int
    sequence: int = Field(default=1, ge=0)


class CourseLessonOrder(BaseModel):
    lesson_ids: list[int]


class CourseAssignmentResponse(BaseModel):
    user_id: int
    course_id: int
    assigned_time: datetime


class LessonCompletionResponse(BaseModel):
    user_id: int
    course_id: int
    lesson_id: int
    completion_time: datetime


class MessageResponse(BaseModel):
    message: str


class LookupListCreate(BaseModel):
    list_name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    sort_mode: LookupSortMode = "Alphabetical"
    default_item_value: str | None = Field(default=None, max_length=120)
    active: bool = True


class LookupListUpdate(LookupListCreate):
    pass


class LookupListResponse(BaseModel):
    id: int
    list_name: str
    description: str | None
    sort_mode: LookupSortMode
    default_item_value: str | None
    active: bool
    create_time: datetime
    update_time: datetime
    create_id: int
    update_id: int

    model_config = ConfigDict(from_attributes=True)


class LookupListItemCreate(BaseModel):
    list_item_value: str = Field(min_length=1, max_length=120)
    list_item_text: str = Field(min_length=1, max_length=200)
    sequence: int | None = Field(default=None, ge=0)
    active: bool = True


class LookupListItemUpdate(BaseModel):
    list_item_text: str = Field(min_length=1, max_length=200)
    sequence: int | None = Field(default=None, ge=0)
    active: bool = True


class LookupListItemResponse(BaseModel):
    list_id: int
    list_item_value: str
    list_item_text: str
    sequence: int | None
    active: bool
    create_time: datetime
    update_time: datetime
    create_id: int
    update_id: int

    model_config = ConfigDict(from_attributes=True)


class LookupListValuesResponse(BaseModel):
    id: int
    list_name: str
    sort_mode: LookupSortMode
    default_item_value: str | None
    items: list[LookupListItemResponse]


class AuditEntryResponse(BaseModel):
    activity_time: datetime
    user_id: int | None
    user_name: str
    user_email: str
    table_name: str
    record_id: str
    activity: Literal["Created", "Updated"]


class AuditSearchResponse(BaseModel):
    date: str
    timezone: str
    page: int
    page_size: int
    total: int
    total_pages: int
    items: list[AuditEntryResponse]
