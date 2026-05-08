import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
from pathlib import Path
from urllib.parse import urlparse
from scraper.pulizia import pulizia
from rest.utils import check_domain_from_url,check_url_reachability,SCRAPER_ROUTER,compute_evaluation_metrics,compute_rougue_l,comupute_error_rates
import time

app = FastAPI()


# Modelli Pydantic
class ParseFromurlResponse(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str

class DomainsResponse(BaseModel):
    domains: List[str]

class GoldStandardResponse(BaseModel):
    url : str
    domain : str
    title : str
    html_text : str
    gold_text : str

class EvaluateInput(BaseModel):
    parsed_text: str
    gold_text: str

class TokenLevelEval(BaseModel):
    precision: float
    recall: float
    f1: float

class EvaluateOutput(BaseModel):
    token_level_eval: TokenLevelEval 
    rouge_metrics : Optional[dict] = None
    error_metrics : Optional[dict] = None

class FullGoldStandardResponse(BaseModel):
    gold_standard: List[GoldStandardResponse]

class ParseFromurlRequest(BaseModel):
    url: str
    html_text: str



#Caricamento dati all'avvio del server 
# Caricamento domini supportati
current_dir = Path(__file__).parent
root = current_dir.parent.parent.parent
domains_path = root / "domini.json"

with open(domains_path, "r",encoding="utf-8") as f:
    supported_data = json.load(f)
    SUPPORTED_DOMAINS = supported_data["domains"]

# Caricamento Gold Standard
gs_path = root / "GS_Data"
gs_wiki = gs_path / "dominio_wikipedia_gs.json"
gs_wired = gs_path / "dominio_wired_gs.json"
gs_nyc = gs_path / "dominio_nyc_gs.json"
gs_groki = gs_path / "dominio_grokipedia_gs.json"



with open(gs_wiki, "r",encoding="utf-8") as f:
    gs_wiki = json.load(f)

with open(gs_wired, "r",encoding="utf-8") as f:
    gs_wired = json.load(f)

with open(gs_nyc, "r",encoding="utf-8") as f:
    gs_nyc = json.load(f)

with open(gs_groki, "r",encoding="utf-8") as f:
    gs_groki = json.load(f)

"""
Dizionario che ha per chiavi i domini supportati e per valori i gold standard corrispondenti
"""
DOMAIN_MAP = {
    "it.wikipedia.org": gs_wiki,
    "www.wired.it": gs_wired,
    "www.nyc.gov": gs_nyc,
    "grokipedia.com": gs_groki
}


# Chiamate GET e POST Parse
@app.get("/parse",response_model=ParseFromurlResponse)
async def parse_url(url : str) -> ParseFromurlResponse:
    """
    Prende in input un url, controlla se il dominio è supportato e se l'url è raggiungibile.
    Esegue scraping, parsing e restituisce un oggetto ParseFromurlResponse.
    """
    domain = check_domain_from_url(url) # controlla se il dominio e' supportato

    if not domain:
        raise HTTPException(status_code=400, detail=f"Dominio non supportato, dominio letto : {domain}")
    
    await check_url_reachability(url) # controlla se l'url e' raggiungibile

    scraper_function = SCRAPER_ROUTER.get(domain) # recupera la funzione di scraping corrispondente al dominio
    output = await scraper_function(url) # esegue lo scraping e il parsing

    return ParseFromurlResponse(
        url=url,
        domain=domain,
        title=output.get("title",""),
        html_text=output.get("html_text",""),
        parsed_text=output.get("parsed_text","")
    )

@app.post("/parse", response_model=ParseFromurlResponse)
async def parse_url_post(inp : ParseFromurlRequest) -> ParseFromurlResponse:
    """
    Prende in input un oggetto ParseFromurlRequest, controlla se il dominio è supportato e se l'url è raggiungibile.
    Esegue scraping, parsing e restituisce un oggetto ParseFromurlResponse.
    """
    domain = check_domain_from_url(inp.url) # controlla se il dominio e' supportato

    if not domain:
        raise HTTPException(status_code=400, detail=f"Dominio non supportato, dominio letto : {domain}")
    

    scraper_function = SCRAPER_ROUTER.get(domain) # recupera la funzione di scraping corrispondente al dominio
    output = await scraper_function(inp.url, html=inp.html_text) 

    return ParseFromurlResponse(
        url=inp.url,
        domain=domain,
        title=output.get("title"),
        html_text=inp.html_text,
        parsed_text=output["parsed_text"]
    )



# Chiamata GET Domini
@app.get("/domains",response_model=DomainsResponse)
async def get_domains() -> DomainsResponse:
    """
    Restituisce la lista dei domini supportati.
    """
    return DomainsResponse(domains=SUPPORTED_DOMAINS)



# Chiamate POST Metriche Aggiuntive
@app.post("/get_error_metrics",response_model=dict)
async def get_error_metrics(inp: EvaluateInput) -> dict:
    """
    Prende in input parsed_text e gold_text, pulisce parsed_text e restituisce un dizionario con WER e CER.
    """
    parsed_text = inp.parsed_text
    parsed_text = await pulizia(parsed_text)
    gold_text = inp.gold_text

    return  comupute_error_rates(parsed_text, gold_text)

@app.post("/get_rouge_metrics",response_model=dict)
async def get_rouge_metrics(inp: EvaluateInput) -> dict:
    """
    Prende in input parsed_text e gold_text, pulisce parsed_text e restituisce un dizionario con le metriche ROUGE-L.
    """
    parsed_text = inp.parsed_text
    parsed_text = await pulizia(parsed_text)
    gold_text = inp.gold_text

    return compute_rougue_l(parsed_text, gold_text)



# Chiamata GET Gold Standard
@app.get("/gold_standard",response_model=GoldStandardResponse)
async def get_gs(url : str) -> GoldStandardResponse:
    """
    Prende in input un url, controlla se il dominio è supportato e restituisce l'oggetto GoldStandardResponse corrispondente.
    """
    domain = check_domain_from_url(url) # controlla se il dominio e' supportato
        
    gs = DOMAIN_MAP.get(domain,None) # recupera il gold standard corrispondente al dominio, se non esiste restituisce None

    if gs is None:
        raise HTTPException(status_code=404, detail=f"Gold Standard non trovato per il dominio: {domain}")
    
    for item in gs: # se non trova l'url nel gold standard solleva un'eccezione
        if item["url"] == url:
            return GoldStandardResponse(**item)
    raise HTTPException(status_code=404, detail=f"url non presente nel Gold Standard: {url}")

@app.get("/full_gold_standard", response_model=FullGoldStandardResponse)
async def get_full_gs(domain: str) -> FullGoldStandardResponse:
    """
    Restituisce il gold standard completo per un determinato dominio.
    """
    if domain not in SUPPORTED_DOMAINS:
        raise HTTPException(status_code=400, detail=f"Dominio non supportato, dominio letto : {domain}")
    
    gs = DOMAIN_MAP.get(domain,None) # recupera il gold standard corrispondente al dominio, se non esiste restituisce None

    if gs is None: 
        raise HTTPException(status_code=404, detail=f"Gold Standard non trovato per il dominio: {domain}")
    
    output_list = list() # converte ogni elemento del gold standard in un oggetto GoldStandardResponse e lo aggiunge alla lista output_list
    for item in gs:
        output_list.append(GoldStandardResponse(**item))
    
    return FullGoldStandardResponse(gold_standard=output_list)



# Chiamata POST Evaluate e POST Metriche Aggiuntive
@app.post("/evaluate", response_model=EvaluateOutput)
async def evaluate(inp: EvaluateInput) -> EvaluateOutput:
    """
    Prende in input parsed_text e gold_text, pulisce parsed_text, calcola precision, recall e F1 score a livello di token e restituisce un oggetto EvaluateOutput.
    """
    parsed_text = inp.parsed_text
    parsed_text = await pulizia(parsed_text)
    gold_text = inp.gold_text

    metrics = compute_evaluation_metrics(parsed_text, gold_text)
    
    token_eval = TokenLevelEval(
        precision=metrics["precision"], 
        recall=metrics["recall"], 
        f1=metrics["F1"]
    )
    return EvaluateOutput(token_level_eval=token_eval)

@app.post("/full_metrics_eval", response_model=EvaluateOutput)
async def full_metrics_eval(inp: EvaluateInput) -> EvaluateOutput:
    """
    Prende in input parsed_text e gold_text, pulisce parsed_text, calcola precision, recall, F1, rouge-l, wer e cer a livello di token e restituisce un oggetto EvaluateOutput.
    """
    parsed_text = inp.parsed_text
    parsed_text = await pulizia(parsed_text)
    gold_text = inp.gold_text

    metrics = compute_evaluation_metrics(parsed_text, gold_text)
    
    token_eval = TokenLevelEval(
        precision=metrics["precision"], 
        recall=metrics["recall"], 
        f1=metrics["F1"]
    )

    rouge_results = compute_rougue_l(parsed_text, gold_text)
    error_rates = comupute_error_rates(parsed_text, gold_text)

    return EvaluateOutput(token_level_eval=token_eval,rouge_metrics=rouge_results,error_metrics=error_rates)



# Chiamata GET Full Gold Standard Evaluation con Metriche Aggiuntive
@app.get("/full_gs_eval", response_model=EvaluateOutput)
async def full_gs_eval(domain : str):
    """
    Prende in input un dominio, controlla se è supportato, recupera il gold standard completo per quel dominio.
    Per ogni url presente nel gold standard esegue scraping, parsing, pulizia e valutazione.
    Restituisce un oggetto EvaluateOutput con la media delle metriche token level e ROUGE-L.
    """

    if domain not in SUPPORTED_DOMAINS: # controlla se il dominio e' supportato, se no solleva un'eccezione
        raise HTTPException(status_code=400, detail=f"Dominio non supportato, dominio letto : {domain}")

    full_gs = DOMAIN_MAP.get(domain,None) # recupera il gold standard corrispondente al dominio, se non esiste restituisce None

    if full_gs is None:
        raise HTTPException(status_code=404, detail=f"Gold Standard non trovato per il dominio: {domain}")
    

    scraper_function = SCRAPER_ROUTER.get(domain) # recupera la funzione di scraping corrispondente al dominio
    browser_cfg = BrowserConfig(headless=True)  # Configurazione del browser per il crawler asincrono

    async with AsyncWebCrawler(config=browser_cfg) as shared_crawler: # creo un crawler asincrono condiviso per tutte le richieste di scraping, in modo da non inizializzare un nuovo browser per ogni richiesta.
        tasks = []
        for item in full_gs: # creo una lista di task asincroni per elaborare tutti gli url del gold standard in ''parallelo'', passando il crawler condiviso a ciascuna richiesta di scraping.
            tasks.append(process_single_url(item, shared_crawler, scraper_function))
        risultati = await asyncio.gather(*tasks, return_exceptions=True)  # eseguo tutti i task asincroni e raccolgo i risultati, se un task solleva un'eccezione viene catturata e restituita come risultato.

    return calculate_average_metrics(risultati) # calcolo le metriche medie e restituisco l'oggetto EvaluateOutput
    






"""
Funzioni di supporto

"""


async def process_single_url(item: dict, crawler: AsyncWebCrawler, scraper_func: callable) -> tuple[dict, dict, dict]:
    """
    Esegue scraping, pulizia e valutazione su un singolo URL.
    Restituisce una tupla con (base_metrics, rouge_metrics).
    """
    html_content = item.get("html_text")
    
    # Scraping
    if html_content:
        output = await scraper_func(item["url"], html=html_content, crawler=crawler)
    else:
        output = await scraper_func(item["url"], crawler=crawler)

    # Pulizia
    parsed_text = await pulizia(output["parsed_text"])
    gold_text = item["gold_text"]
    
    # Valutazione
    base_metrics = compute_evaluation_metrics(parsed_text, gold_text)
    rouge_metrics = compute_rougue_l(parsed_text, gold_text)
    error_metrics = comupute_error_rates(parsed_text, gold_text)

    return base_metrics, rouge_metrics, error_metrics



def calculate_average_metrics(risultati: list) -> EvaluateOutput:
    """
    Prende in input una lista di tuple (base_metrics, rouge_metrics), 
    filtra gli errori e restituisce l'oggetto EvaluateOutput con le medie.
    """
    sum_p, sum_r, sum_f1 = 0.0, 0.0, 0.0
    sum_rouge_p, sum_rouge_r, sum_rouge_f1 = 0.0, 0.0, 0.0
    sum_wer, sum_cer = 0.0, 0.0
    valid_results = 0

    for res in risultati:
        if isinstance(res, Exception):
            print(f"Errore durante lo scraping/parsing di un URL: {res}")
            continue
            
        base_m, rouge_m, error_m = res
        
        sum_p += base_m["precision"]
        sum_r += base_m["recall"]
        sum_f1 += base_m["F1"]

        sum_rouge_p += rouge_m["precision"]
        sum_rouge_r += rouge_m["recall"]
        sum_rouge_f1 += rouge_m["f1"]

        sum_wer += error_m["wer"]
        sum_cer += error_m["cer"]
        
        valid_results += 1

    if valid_results == 0:
        raise HTTPException(status_code=400, detail="Elaborazione fallita per tutti gli URL del dataset.")

    # Costruisco e restituisco l'oggetto finale
    return EvaluateOutput(
        token_level_eval=TokenLevelEval(
            precision=sum_p / valid_results, 
            recall=sum_r / valid_results, 
            f1=sum_f1 / valid_results
        ),
        rouge_metrics={
            "rouge_l": {
                "precision": sum_rouge_p / valid_results,
                "recall": sum_rouge_r / valid_results,
                "f1": sum_rouge_f1 / valid_results
            }
        },
        error_metrics={
            "wer": sum_wer / valid_results,
            "cer": sum_cer / valid_results
        }
    )