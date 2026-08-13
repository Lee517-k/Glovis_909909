from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook

from app.repositories.yp_data_repository import YPDataRepository


router = APIRouter(prefix="/yp", tags=["carrier-data"])
repository = YPDataRepository()
uploads: dict[str, dict[str, Any]] = {}

FIELDS = ["mode", "origin_name", "destination_name", "typical_base_rate", "typical_transit_hours", "capacity_value", "capacity_unit", "on_time_rate"]


@router.get("/uploads/template")
def template() -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "carrier_capabilities"
    sheet.append(FIELDS)
    sheet.append(["sea", "Busan", "Hamburg", 1200, 360, 100, "vehicle", 0.92])
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="glovis_carrier_capability_template.xlsx"'})


def read_rows(filename: str, content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "csv":
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return list(reader.fieldnames or []), list(reader)
    if suffix in {"xlsx", "xlsm"}:
        sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).active
        values = list(sheet.values)
        headers = [str(value or "").strip() for value in values[0]] if values else []
        return headers, [dict(zip(headers, row)) for row in values[1:] if any(value is not None for value in row)]
    raise HTTPException(status_code=400, detail="현재 CSV와 XLSX 파일만 분석할 수 있습니다.")


@router.post("/uploads/analyze")
async def analyze(file: UploadFile = File(...), carrier_name: str = Form(...)) -> dict[str, Any]:
    if not carrier_name.strip():
        raise HTTPException(status_code=400, detail="선사 이름을 입력해 주세요.")
    content = await file.read()
    headers, rows = read_rows(file.filename or "", content)
    normalized = [{field: row.get(field) for field in FIELDS} for row in rows]
    issues = []
    valid_rows = []
    for index, row in enumerate(normalized, start=2):
        errors = [f"{field} 값이 없습니다." for field in ("mode", "origin_name", "destination_name") if not row.get(field)]
        if str(row.get("mode", "")).lower() not in {"sea", "air", "rail", "road"}:
            errors.append("mode는 sea, air, rail, road 중 하나여야 합니다.")
        if errors:
            issues.append({"row": index, "errors": errors, "data_errors": errors, "warnings": [], "data_warnings": []})
        else:
            valid_rows.append(row)
    upload_id = uuid.uuid4().hex
    uploads[upload_id] = {"carrier_name": carrier_name.strip(), "rows": valid_rows, "file_name": file.filename or "upload"}
    return {
        "upload_id": upload_id, "file_name": file.filename, "carrier_name": carrier_name.strip(),
        "total_rows": len(rows), "valid_rows": len(valid_rows), "invalid_rows": len(rows) - len(valid_rows),
        "warning_count": 0, "headers": headers,
        "mapping": [{"system_field": field, "source_column": field if field in headers else None, "required": field in {"mode", "origin_name", "destination_name"}, "status": "mapped" if field in headers else "excluded"} for field in FIELDS],
        "issues": issues, "preview": normalized[:10],
    }


@router.post("/uploads/{upload_id}/remap")
def remap(upload_id: str) -> dict[str, Any]:
    if upload_id not in uploads:
        raise HTTPException(status_code=404, detail="업로드 분석 결과를 찾을 수 없습니다.")
    raise HTTPException(status_code=501, detail="수동 컬럼 재매핑은 다음 단계에서 지원합니다.")


@router.post("/uploads/{upload_id}/commit")
def commit(upload_id: str) -> dict[str, int]:
    upload = uploads.pop(upload_id, None)
    if upload is None:
        raise HTTPException(status_code=404, detail="업로드 분석 결과를 찾을 수 없습니다.")
    return {"inserted_or_updated": repository.insert_upload(upload["carrier_name"], upload["rows"], upload["file_name"])}
