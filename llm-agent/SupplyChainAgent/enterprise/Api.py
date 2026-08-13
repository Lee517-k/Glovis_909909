from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import json

app = FastAPI()

@app.get("/api/state/{fid}")
async def get_state(fid: str):
    filename = f"./data/state_{fid}.json"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return JSONResponse(content=data)
            except json.JSONDecodeError:
                return JSONResponse(content={"error": "Invalid JSON format"}, status_code=500)
    else:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
