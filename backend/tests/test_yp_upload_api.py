from fastapi.testclient import TestClient

from app.api.yp_upload import STAGE_DIR
from app.main import app


client = TestClient(app)


def test_template_and_csv_analysis() -> None:
    template = client.get("/api/yp/uploads/template")
    assert template.status_code == 200
    assert template.headers["content-type"].startswith("application/vnd.openxmlformats")

    csv_data = "운송수단,출발지,도착지,기본 운임,소요시간,정시율\nsea,Busan,Hamburg,1200,360,92%\n"
    response = client.post(
        "/api/yp/uploads/analyze",
        data={"carrier_name": "Test Carrier"},
        files={"file": ("sample.csv", csv_data.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["valid_rows"] == 1
    assert payload["preview"][0]["on_time_rate"] == 0.92

    stage = STAGE_DIR / f"YP_{payload['upload_id']}.json"
    stage.unlink(missing_ok=True)
    if STAGE_DIR.exists() and not any(STAGE_DIR.iterdir()):
        STAGE_DIR.rmdir()

