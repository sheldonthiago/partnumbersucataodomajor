"""
API web para consultar part numbers no Mercado Livre.

Rodar localmente:
    uvicorn api:app --host 0.0.0.0 --port 8000

Endpoint:
    GET /consultar?part_number=B3GF1511
"""

import os

from fastapi import FastAPI, HTTPException, Query

from consultar_part_number import consultar_part_number_20_anuncios

app = FastAPI(title="Consulta Part Number - Mercado Livre")


@app.get("/")
def raiz():
    return {"status": "ok", "uso": "/consultar?part_number=SEU_PART_NUMBER"}


@app.get("/consultar")
def consultar(part_number: str = Query(..., description="Part number a ser consultado")):
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    resultado = consultar_part_number_20_anuncios(part_number, gemini_api_key=gemini_api_key)

    if "error" in resultado:
        raise HTTPException(status_code=404, detail=resultado["error"])

    return resultado
