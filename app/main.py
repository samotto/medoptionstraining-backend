from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.routers.audit_routes import router as audit_router
from app.routers.auth_routes import router as auth_router
from app.routers.lookup_list_routes import admin_router as lookup_list_admin_router
from app.routers.lookup_list_routes import router as lookup_list_router
from app.routers.training_routes import router as training_router
from app.routers.user_routes import router as user_router
from app.schemas import HealthResponse


settings = get_settings()
app = FastAPI(title="Med Options Training Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    # Running this query verifies that the database connection and users table
    # are available. An empty users table is still considered healthy.
    db.execute(select(User.id).limit(1)).first()
    return HealthResponse(status="ok")


app.include_router(auth_router)
app.include_router(lookup_list_router)
app.include_router(lookup_list_admin_router)
app.include_router(audit_router)
app.include_router(training_router)
app.include_router(user_router)
