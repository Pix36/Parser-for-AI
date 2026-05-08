import requests
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI()
current_dir = Path(__file__).parent
root = current_dir.parent
templates_path = root / "templates"
templates = Jinja2Templates(directory=templates_path)
BACKEND_URL = "http://fastapi_backend:8003"

# 1. GET /domains -> Homepage con lista domini
@app.get("/", response_class=HTMLResponse)
async def get_domains_view(request: Request):
    try:
        res = requests.get(f"{BACKEND_URL}/domains")
        res.raise_for_status()
        domains = res.json().get("domains", [])
        return templates.TemplateResponse(
            request=request, 
            name="index.html", 
            context={"domains": domains}
        )
    except Exception as e:
        return templates.TemplateResponse(
            request=request, 
            name="error.html", 
            context={"detail": f"Errore connessione backend: {e}"}
        )


# 4. GET /full_gs -> Lista dataset dominio
@app.post("/view_full_gs", response_class=HTMLResponse)
async def get_full_gs_view(request: Request, domain: str = Form(...)):
    res = requests.get(f"{BACKEND_URL}/full_gold_standard", params={"domain": domain})
    if res.status_code != 200:
        return templates.TemplateResponse(
            request=request, 
            name="error.html", 
            context={"detail": res.text}
        )

    data = res.json()
    gs_list = data.get("gold_standard", [])
    
    return templates.TemplateResponse(
        request=request, 
        name="full_gs.html", 
        context={"gs_list": gs_list, "domain": domain}
    )

# 5. Analizza con le metriche aggiuntive
@app.post("/analyze", response_class=HTMLResponse)
async def analyze_view(
    request: Request,
    url: str = Form(""),
    html: str = Form("")
):
    try:
        url = url.strip()
        html = html.strip()

        if not url and not html:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={"detail": "Inserisci URL oppure HTML"}
            )


        # 1. PARSING
        if html:
            payload = {
                "url": url,
                "html_text": html
            }
            res_parse = requests.post(f"{BACKEND_URL}/parse", json=payload)
        else:
            res_parse = requests.get(f"{BACKEND_URL}/parse", params={"url": url})

        if res_parse.status_code != 200:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={"detail": f"Errore parsing: {res_parse.text}"}
            )

        data_parse = res_parse.json()
        parsed_text = data_parse.get("parsed_text", "")
        title = data_parse.get("title", "")
        html_text = data_parse.get("html_text", "")


        # 2. GOLD STANDARD (se URL)

        gold_text = None

        if url:
            res_gs = requests.get(f"{BACKEND_URL}/gold_standard", params={"url": url})
            if res_gs.status_code == 200:
                gold_text = res_gs.json().get("gold_text")


        # 3. METRICHE (solo se GS esiste)

        metrics = None

        if gold_text:
            payload_eval = {
                "parsed_text": parsed_text,
                "gold_text": gold_text
            }

            res_eval = requests.post(f"{BACKEND_URL}/full_metrics_eval", json=payload_eval)

            if res_eval.status_code == 200:
                metrics = res_eval.json()


        # 4. RISULTATO UNIFICATO

        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={
                "parsed_text": parsed_text,
                "gold_text": gold_text,
                "metrics": metrics,
                "url": url,
                "title": title,
                "html_text": html_text
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"detail": str(e)}
        )


# 6. GET /full_gs_eval -> Valutazione generale
@app.post("/view_full_eval", response_class=HTMLResponse)
async def full_gs_eval_view(request: Request, domain: str = Form(...)):
    res = requests.get(f"{BACKEND_URL}/full_gs_eval", params={"domain": domain})
    if res.status_code != 200:
        return templates.TemplateResponse(
            request=request, 
            name="error.html", 
            context={"detail": res.text}
        )

    backend_data = res.json() 
    print(backend_data)
    return templates.TemplateResponse(
        request=request, 
        name="evaluate.html", 
        context={"metrics": backend_data, "domain": domain}
    )