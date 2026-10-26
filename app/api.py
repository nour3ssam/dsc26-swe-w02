
import base64
import uuid
from typing import Any, Optional

from fastapi import FastAPI, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.domain import EventType, InvalidTransition, Parcel, ParcelState, apply_event  # noqa: F401


class CreateParcelRequest(BaseModel):
    merchant_ref: str = Field(..., min_length=1, max_length=64)
    cod_amount_piastres: int = Field(..., ge=0, le=5_000_000)
    address_text: str = Field(..., min_length=1, max_length=500)


class CreateEventRequest(BaseModel):
    type: EventType


def create_problem_response(
    status_code: int,
    title: str,
    detail: str,
    type_uri: str = "about:blank",
    extra: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    content = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if extra:
        content.update(extra)
    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Tawseel Parcel API")

    parcels_db: dict[str, Parcel] = {}
    merchant_refs_set: set[str] = set()
    parcels_list: list[Parcel] = []

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors_list = []
        for error in exc.errors():
            errors_list.append({
                "loc": [str(loc) for loc in error["loc"]],
                "msg": error["msg"],
            })
        return create_problem_response(
            status_code=422,
            title="Unprocessable Entity",
            detail="Validation error",
            extra={"errors": errors_list},
        )

    @app.post(
        "/v1/parcels",
        status_code=status.HTTP_201_CREATED,
        operation_id="createParcel",
    )
    def create_parcel(body: CreateParcelRequest, response: Response):
        if body.merchant_ref in merchant_refs_set:
            return create_problem_response(
                status_code=409,
                title="Conflict",
                detail="merchant_ref already exists",
            )

        parcel_id = f"pcl_{uuid.uuid4().hex}"
        parcel = Parcel(
            id=parcel_id,
            merchant_ref=body.merchant_ref,
            cod_amount_piastres=body.cod_amount_piastres,
            address_text=body.address_text,
        )

        parcels_db[parcel_id] = parcel
        parcels_list.append(parcel)
        merchant_refs_set.add(body.merchant_ref)

        response.headers["Location"] = f"/v1/parcels/{parcel_id}"
        return {
            "id": parcel.id,
            "merchant_ref": parcel.merchant_ref,
            "cod_amount_piastres": parcel.cod_amount_piastres,
            "address_text": parcel.address_text,
            "state": parcel.state,
            "attempts": parcel.attempts,
        }

    @app.get(
        "/v1/parcels/{parcel_id}",
        operation_id="getParcel",
    )
    def get_parcel(parcel_id: str):
        if parcel_id not in parcels_db:
            return create_problem_response(
                status_code=404,
                title="Not Found",
                detail="Parcel not found",
            )
        parcel = parcels_db[parcel_id]
        return {
            "id": parcel.id,
            "merchant_ref": parcel.merchant_ref,
            "cod_amount_piastres": parcel.cod_amount_piastres,
            "address_text": parcel.address_text,
            "state": parcel.state,
            "attempts": parcel.attempts,
        }

    @app.get(
        "/v1/parcels",
        operation_id="listParcels",
    )
    def list_parcels(
        state: Optional[ParcelState] = Query(None),
        limit: int = Query(20),
        cursor: Optional[str] = Query(None),
    ):
        if limit < 1 or limit > 100:
            return create_problem_response(
                status_code=422,
                title="Unprocessable Entity",
                detail="Limit must be between 1 and 100",
            )

        cursor_parcel_id = None
        if cursor is not None:
            try:
                decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
                cursor_parcel_id = decoded
            except Exception:
                return create_problem_response(
                    status_code=400,
                    title="Bad Request",
                    detail="Invalid cursor",
                )

        start_idx = 0
        if cursor_parcel_id is not None:
            found = False
            for idx, p in enumerate(parcels_list):
                if p.id == cursor_parcel_id:
                    start_idx = idx + 1
                    found = True
                    break
            if not found:
                return create_problem_response(
                    status_code=400,
                    title="Bad Request",
                    detail="Cursor parcel not found",
                )

        items_to_return = []
        last_processed_idx = start_idx - 1

        target_state = state.value if state else None

        for idx in range(start_idx, len(parcels_list)):
            p = parcels_list[idx]
            current_p = parcels_db[p.id]
            if target_state is None or current_p.state == target_state:
                items_to_return.append(current_p)
                last_processed_idx = idx
                if len(items_to_return) == limit:
                    break

        has_more = False
        for idx in range(last_processed_idx + 1, len(parcels_list)):
            p = parcels_list[idx]
            current_p = parcels_db[p.id]
            if target_state is None or current_p.state == target_state:
                has_more = True
                break

        next_cursor = None
        if has_more and items_to_return:
            last_item_id = items_to_return[-1].id
            next_cursor = base64.b64encode(last_item_id.encode("utf-8")).decode("utf-8")

        formatted_items = [
            {
                "id": p.id,
                "merchant_ref": p.merchant_ref,
                "cod_amount_piastres": p.cod_amount_piastres,
                "address_text": p.address_text,
                "state": p.state,
                "attempts": p.attempts,
            }
            for p in items_to_return
        ]

        return {"items": formatted_items, "next_cursor": next_cursor}


    @app.post(
        "/v1/parcels/{parcel_id}/events",
        operation_id="createParcelEvent",
    )
    def create_parcel_event(parcel_id: str, body: CreateEventRequest):
        if parcel_id not in parcels_db:
            return create_problem_response(
                status_code=404,
                title="Not Found",
                detail="Parcel not found",
            )

        parcel = parcels_db[parcel_id]

        try:
            updated_parcel = apply_event(parcel, body.type)
        except InvalidTransition as e:
            return create_problem_response(
                status_code=409,
                title="Conflict",
                detail=str(e),
            )

        parcels_db[parcel_id] = updated_parcel

        return {
            "id": updated_parcel.id,
            "merchant_ref": updated_parcel.merchant_ref,
            "cod_amount_piastres": updated_parcel.cod_amount_piastres,
            "address_text": updated_parcel.address_text,
            "state": updated_parcel.state,
            "attempts": updated_parcel.attempts,
        }

    return app


app = create_app()
