"""
Patient Registration System - REST API + Vapi voice agent integration.

Architecture:
  Caller <-> Vapi (telephony/STT/TTS/LLM) <-> /vapi/tool-call (this file)
                                                     |
                                                     v
                                          database.py (SQLite, persistent)
                                                     ^
                                                     |
  External clients <-> REST API (/patients...) -----+

Same service-layer functions (database.py) back both the REST API and the
voice agent tools, so there's one source of truth for persistence logic.
"""
import logging
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import database as db
from validation import PatientCreate, PatientUpdate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("patient-voice-agent")

app = FastAPI(title="Patient Registration System")


@app.on_event("startup")
def startup():
    db.init_db()
    logger.info("Database ready")


def envelope(data=None, error=None):
    return {"data": data, "error": error}


def format_validation_errors(e: ValidationError) -> list:
    return [
        {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
        for err in e.errors()
    ]


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    return envelope(data={"status": "ok"})


@app.get("/patients")
def list_patients(last_name: Optional[str] = None,
                   date_of_birth: Optional[str] = None,
                   phone_number: Optional[str] = None):
    results = db.list_patients(last_name, date_of_birth, phone_number)
    return envelope(data=results)


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    patient = db.get_by_id(patient_id)
    if not patient:
        return JSONResponse(status_code=404, content=envelope(error="Patient not found."))
    return envelope(data=patient)


@app.post("/patients", status_code=201)
def create_patient(payload: dict):
    try:
        validated = PatientCreate(**payload)
    except ValidationError as e:
        return JSONResponse(status_code=422, content=envelope(error=format_validation_errors(e)))
    record = db.create_patient(validated.model_dump())
    logger.info("Created patient: %s", record)
    return envelope(data=record)


@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, payload: dict):
    try:
        validated = PatientUpdate(**payload)
    except ValidationError as e:
        return JSONResponse(status_code=422, content=envelope(error=format_validation_errors(e)))
    updated = db.update_patient(patient_id, validated.model_dump(exclude_none=True))
    if updated is None:
        return JSONResponse(status_code=404, content=envelope(error="Patient not found."))
    logger.info("Updated patient: %s", updated)
    return envelope(data=updated)


@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: str):
    ok = db.soft_delete_patient(patient_id)
    if not ok:
        return JSONResponse(status_code=404, content=envelope(error="Patient not found."))
    logger.info("Soft-deleted patient: %s", patient_id)
    return envelope(data={"patient_id": patient_id, "deleted": True})


# ---------------------------------------------------------------------------
# Vapi voice agent webhook
# ---------------------------------------------------------------------------

@app.post("/vapi/tool-call")
async def vapi_tool_call(request: Request):
    payload = await request.json()
    tool_calls = payload.get("message", {}).get("toolCallList", [])
    results = []

    for call in tool_calls:
        call_id = call.get("id")
        function = call.get("function", {})
        name = function.get("name")
        args = function.get("arguments", {}) or {}
        logger.info("Vapi tool call: %s args=%s", name, args)

        try:
            result_text = handle_tool(name, args)
        except Exception as e:
            logger.exception("Tool execution failed")
            result_text = f"There was a problem processing that: {str(e)}"

        results.append({"toolCallId": call_id, "result": result_text})

    return JSONResponse(content={"results": results}, status_code=200)


def handle_tool(name: str, args: dict) -> str:
    if name == "check_existing_patient":
        phone = _digits(args.get("phone_number", ""))
        existing = db.find_by_phone(phone)
        if existing:
            return (f"Existing patient found: {existing['first_name']} {existing['last_name']}, "
                     f"patient_id {existing['patient_id']}.")
        return "No existing patient found with that phone number."

    if name == "register_patient":
        try:
            validated = PatientCreate(**args)
        except ValidationError as e:
            # Return the FIRST validation error so the agent can re-prompt
            # for that specific field, per spec's error-handling requirement.
            first_err = e.errors()[0]
            field = first_err["loc"][0] if first_err.get("loc") else "field"
            return f"Invalid value for {field}: {first_err['msg']} Please provide it again."
        record = db.create_patient(validated.model_dump())
        logger.info("Voice-registered patient: %s", record)
        return (f"Registration complete for {record['first_name']} {record['last_name']}. "
                 f"Patient ID {record['patient_id']}.")

    if name == "update_patient":
        patient_id = args.pop("patient_id", None)
        if not patient_id:
            return "Missing patient_id for update."
        try:
            validated = PatientUpdate(**args)
        except ValidationError as e:
            first_err = e.errors()[0]
            field = first_err["loc"][0] if first_err.get("loc") else "field"
            return f"Invalid value for {field}: {first_err['msg']} Please provide it again."
        updated = db.update_patient(patient_id, validated.model_dump(exclude_none=True))
        if not updated:
            return "Could not find that patient record to update."
        return f"Updated record for {updated['first_name']} {updated['last_name']}."

    return f"Unknown tool: {name}"


def _digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
