"""
API web para consultar part numbers no Mercado Livre.

Rodar localmente:
    uvicorn api:app --host 0.0.0.0 --port 8000

Interface web:
    http://localhost:8000/

Endpoint JSON:
    GET /api/consultar?part_number=B3GF1511
"""

import os

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from consultar_part_number import consultar_part_number_20_anuncios

app = FastAPI(title="Consulta Part Number - Mercado Livre")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def formulario(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.post("/consultar", response_class=HTMLResponse)
async def consultar_form(
    request: Request,
    part_number: str = Form(""),
    foto: UploadFile | None = File(None),
):
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    foto_bytes = None
    foto_mime_type = "image/jpeg"
    if foto is not None and foto.filename:
        foto_bytes = await foto.read()
        foto_mime_type = foto.content_type or "image/jpeg"

    resultado = consultar_part_number_20_anuncios(
        part_number=part_number.strip() or None,
        gemini_api_key=gemini_api_key,
        foto_bytes=foto_bytes,
        foto_mime_type=foto_mime_type,
    )

    if "error" in resultado:
        return templates.TemplateResponse(
            request, "index.html", {"erro": resultado["error"]}
        )

    return templates.TemplateResponse(
        request,
        "resultados.html",
        {
            "part_number": resultado["part_number"],
            "query_otimizada": resultado["query_otimizada_gemini"],
            "anuncios": resultado["lista_20_anuncios"],
        },
    )


@app.get("/api/consultar")
def consultar_json(part_number: str = Query(..., description="Part number a ser consultado")):
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    resultado = consultar_part_number_20_anuncios(part_number, gemini_api_key=gemini_api_key)

    if "error" in resultado:
        raise HTTPException(status_code=404, detail=resultado["error"])

    return resultado
