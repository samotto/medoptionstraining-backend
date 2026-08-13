from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import LookupList, LookupListItem, User
from app.schemas import (
    LookupListCreate,
    LookupListItemCreate,
    LookupListItemResponse,
    LookupListItemUpdate,
    LookupListResponse,
    LookupListUpdate,
    LookupListValuesResponse,
)


router = APIRouter(prefix="/lookup-lists", tags=["lookup lists"])
admin_router = APIRouter(prefix="/admin/lookup-lists", tags=["lookup list administration"])


def require_admin(user: User) -> None:
    if user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} cannot be blank",
        )
    return cleaned


def get_list_or_404(db: Session, list_id: int) -> LookupList:
    lookup_list = db.query(LookupList).filter(LookupList.id == list_id).first()
    if not lookup_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lookup list not found")
    return lookup_list


def get_item_or_404(db: Session, list_id: int, list_item_value: str) -> LookupListItem:
    item = (
        db.query(LookupListItem)
        .filter(
            LookupListItem.list_id == list_id,
            LookupListItem.list_item_value == list_item_value,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lookup list item not found")
    return item


def ordered_items_query(db: Session, lookup_list: LookupList, *, active_only: bool):
    query = db.query(LookupListItem).filter(LookupListItem.list_id == lookup_list.id)
    if active_only:
        query = query.filter(LookupListItem.active.is_(True))
    if lookup_list.sort_mode == "Sequence":
        return query.order_by(
            LookupListItem.sequence.asc().nullslast(),
            func.lower(LookupListItem.list_item_text).asc(),
        )
    return query.order_by(
        func.lower(LookupListItem.list_item_text).asc(),
        func.lower(LookupListItem.list_item_value).asc(),
    )


def require_sequence_for_sequenced_list(lookup_list: LookupList, sequence: int | None) -> None:
    if lookup_list.sort_mode == "Sequence" and sequence is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A sequence number is required for a Sequence-sorted list",
        )


def validate_default_item(
    db: Session,
    lookup_list: LookupList,
    default_item_value: str | None,
) -> str | None:
    if default_item_value is None:
        return None
    cleaned = clean_required(default_item_value, "Default value")
    item = (
        db.query(LookupListItem)
        .filter(
            LookupListItem.list_id == lookup_list.id,
            LookupListItem.list_item_value == cleaned,
            LookupListItem.active.is_(True),
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The default value must be an active value in this list",
        )
    return item.list_item_value


def require_not_default_item(lookup_list: LookupList, item: LookupListItem) -> None:
    if lookup_list.default_item_value == item.list_item_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose or clear a different default value before deactivating this value",
        )


@router.get("/{list_name}", response_model=LookupListValuesResponse)
def get_lookup_list_values(
    list_name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LookupListValuesResponse:
    lookup_list = (
        db.query(LookupList)
        .filter(func.lower(LookupList.list_name) == list_name.strip().lower(), LookupList.active.is_(True))
        .first()
    )
    if not lookup_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active lookup list not found")
    items = ordered_items_query(db, lookup_list, active_only=True).all()
    return LookupListValuesResponse(
        id=lookup_list.id,
        list_name=lookup_list.list_name,
        sort_mode=lookup_list.sort_mode,
        default_item_value=lookup_list.default_item_value,
        items=[LookupListItemResponse.model_validate(item) for item in items],
    )


@admin_router.get("", response_model=list[LookupListResponse])
def list_lookup_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LookupListResponse]:
    require_admin(current_user)
    lists = db.query(LookupList).order_by(func.lower(LookupList.list_name).asc()).all()
    return [LookupListResponse.model_validate(item) for item in lists]


@admin_router.post("", response_model=LookupListResponse, status_code=status.HTTP_201_CREATED)
def create_lookup_list(
    payload: LookupListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LookupListResponse:
    require_admin(current_user)
    list_name = clean_required(payload.list_name, "List name")
    duplicate = db.query(LookupList).filter(func.lower(LookupList.list_name) == list_name.lower()).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A list with this name already exists")
    if payload.default_item_value is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Create the list and its values before choosing a default value",
        )
    now = datetime.now(timezone.utc)
    lookup_list = LookupList(
        list_name=list_name,
        description=payload.description.strip() if payload.description else None,
        sort_mode=payload.sort_mode,
        default_item_value=None,
        active=payload.active,
        create_time=now,
        update_time=now,
        create_id=current_user.id,
        update_id=current_user.id,
    )
    db.add(lookup_list)
    db.commit()
    db.refresh(lookup_list)
    return LookupListResponse.model_validate(lookup_list)


@admin_router.put("/{list_id}", response_model=LookupListResponse)
def update_lookup_list(
    list_id: int,
    payload: LookupListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LookupListResponse:
    require_admin(current_user)
    lookup_list = get_list_or_404(db, list_id)
    list_name = clean_required(payload.list_name, "List name")
    duplicate = (
        db.query(LookupList)
        .filter(func.lower(LookupList.list_name) == list_name.lower(), LookupList.id != list_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A list with this name already exists")
    if payload.sort_mode == "Sequence":
        missing_sequence = (
            db.query(LookupListItem)
            .filter(LookupListItem.list_id == list_id, LookupListItem.sequence.is_(None))
            .first()
        )
        if missing_sequence:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Every list value needs a sequence number before changing to Sequence sorting",
            )
    default_item_value = validate_default_item(db, lookup_list, payload.default_item_value)
    lookup_list.list_name = list_name
    lookup_list.description = payload.description.strip() if payload.description else None
    lookup_list.sort_mode = payload.sort_mode
    lookup_list.default_item_value = default_item_value
    lookup_list.active = payload.active
    lookup_list.update_time = datetime.now(timezone.utc)
    lookup_list.update_id = current_user.id
    db.add(lookup_list)
    db.commit()
    db.refresh(lookup_list)
    return LookupListResponse.model_validate(lookup_list)


@admin_router.delete("/{list_id}", response_model=LookupListResponse)
def deactivate_lookup_list(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LookupListResponse:
    require_admin(current_user)
    lookup_list = get_list_or_404(db, list_id)
    lookup_list.active = False
    lookup_list.update_time = datetime.now(timezone.utc)
    lookup_list.update_id = current_user.id
    db.add(lookup_list)
    db.commit()
    db.refresh(lookup_list)
    return LookupListResponse.model_validate(lookup_list)


@admin_router.get("/{list_id}/items", response_model=list[LookupListItemResponse])
def list_lookup_list_items(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LookupListItemResponse]:
    require_admin(current_user)
    lookup_list = get_list_or_404(db, list_id)
    items = ordered_items_query(db, lookup_list, active_only=False).all()
    return [LookupListItemResponse.model_validate(item) for item in items]


@admin_router.post(
    "/{list_id}/items",
    response_model=LookupListItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lookup_list_item(
    list_id: int,
    payload: LookupListItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LookupListItemResponse:
    require_admin(current_user)
    lookup_list = get_list_or_404(db, list_id)
    item_value = clean_required(payload.list_item_value, "List item value")
    item_text = clean_required(payload.list_item_text, "List item text")
    require_sequence_for_sequenced_list(lookup_list, payload.sequence)
    duplicate = (
        db.query(LookupListItem)
        .filter(
            LookupListItem.list_id == list_id,
            func.lower(LookupListItem.list_item_value) == item_value.lower(),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This list item value already exists")
    now = datetime.now(timezone.utc)
    item = LookupListItem(
        list_id=list_id,
        list_item_value=item_value,
        list_item_text=item_text,
        sequence=payload.sequence,
        active=payload.active,
        create_time=now,
        update_time=now,
        create_id=current_user.id,
        update_id=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return LookupListItemResponse.model_validate(item)


@admin_router.put("/{list_id}/items/{list_item_value}", response_model=LookupListItemResponse)
def update_lookup_list_item(
    list_id: int,
    list_item_value: str,
    payload: LookupListItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LookupListItemResponse:
    require_admin(current_user)
    lookup_list = get_list_or_404(db, list_id)
    item = get_item_or_404(db, list_id, list_item_value)
    require_sequence_for_sequenced_list(lookup_list, payload.sequence)
    if not payload.active:
        require_not_default_item(lookup_list, item)
    item.list_item_text = clean_required(payload.list_item_text, "List item text")
    item.sequence = payload.sequence
    item.active = payload.active
    item.update_time = datetime.now(timezone.utc)
    item.update_id = current_user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return LookupListItemResponse.model_validate(item)


@admin_router.delete("/{list_id}/items/{list_item_value}", response_model=LookupListItemResponse)
def deactivate_lookup_list_item(
    list_id: int,
    list_item_value: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LookupListItemResponse:
    require_admin(current_user)
    lookup_list = get_list_or_404(db, list_id)
    item = get_item_or_404(db, list_id, list_item_value)
    require_not_default_item(lookup_list, item)
    item.active = False
    item.update_time = datetime.now(timezone.utc)
    item.update_id = current_user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return LookupListItemResponse.model_validate(item)
