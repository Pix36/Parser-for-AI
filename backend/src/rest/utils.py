import re
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from scraper.parserWiki import mainWiki
from scraper.parserGroki import mainGroki
from scraper.parserNyc import mainNyc
from scraper.parserWired import mainWired
from rouge_score import rouge_scorer
import jiwer

# Check Domain and URL
def check_domain_from_url(url: str) -> bool:
    """
    Controlla se il dominio dell'URL è tra quelli supportati.
    restituisce il dominio se è supportato, altrimenti restituisce False.
    """
    parsed_url = urlparse(url)
    domain =  parsed_url.netloc
    allowed_domains = ["it.wikipedia.org", "www.wired.it", "www.nyc.gov", "grokipedia.com"]
    if domain in allowed_domains:
        return domain
    else :
        return False
    
async def check_url_reachability(url: str) -> bool:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    """
    Controlla se l'URL è raggiungibile (status code 200).
    Restituisce True se raggiungibile, altrimenti False.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
        
        # Solleva un'eccezione se il codice di stato è un 4xx o 5xx
        response.raise_for_status()

    except httpx.RequestError as e:
        # Gestisce sia errori di rete (connessione, timeout) che errori di stato HTTP
        raise HTTPException(status_code=404, detail=f"URL non raggiungibile: {str(e)}")



# Evaluation
def compute_evaluation_metrics(parsed_text : str, gold_text : str) -> dict:
    """
    Dati parsed_text e gold_text li confronta token per token e restituisce un dizionario con precision, recall e F1 score.
    """

    GS_token = estrai_token(gold_text)
    P_token  = estrai_token(parsed_text)

    precision = compute_precision(GS_token,P_token)
    recall = compute_recall(GS_token,P_token)
    F1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "F1": F1}



"""
Handler domini.
un dizionario che ha per chiavi i dominmi supportati e per valori le funzioni di parsing corrispondenti
"""
async def handle_wiki(url: str, html: str = None,crawler = None):
    return await mainWiki(url, html, crawler)
async def handle_groki(url: str, html: str = None,crawler = None):
    return await mainGroki(url, html, crawler)
async def handle_wired(url: str, html: str = None,crawler = None):
    return await mainWired(url, html, crawler)
async def handle_nyc(url: str, html: str = None,crawler = None):
    return await mainNyc(url, html, crawler)

SCRAPER_ROUTER = {
    "it.wikipedia.org": handle_wiki,
    "grokipedia.com": handle_groki,
    "www.wired.it": handle_wired,
    "www.nyc.gov": handle_nyc
}



# Token Eval
def estrai_token(text : str) -> set:
    return set(text.lower().split())

def estrai_token_list(text : str) -> list:
    return text.lower().split()    

def compute_precision(GS_token : set,P_token : set):
    if not P_token:
        return 0.0
    true_positives = len(GS_token & P_token)
    precision = true_positives / len(P_token)
    return precision

def compute_recall(GS_token : set,P_token : set):
    if not GS_token:
        return 0.0
    true_positives = len(GS_token & P_token)
    recall = true_positives / len(GS_token)
    return recall


# Implementazione altre metriche
def compute_html_leakage(parsed_text: str) -> dict:
    """
    Dato in input un parsed text cerca residui di html, restituisce uno score (0 perfetto, > 0 ci sono imperfezioni) 
    e dei dettagli aggiuntivi sul numero di tag, attributi, entità e blocchi di codice trovati.
    """
    tag_pattern = re.compile(r'<\/?[a-z][a-z0-9]*\b[^>]*>', re.IGNORECASE)
    tags_found = tag_pattern.findall(parsed_text)

    attr_pattern = re.compile(r'\b(?:class|id|href|src|style|alt)\s*=\s*(["\']).*?\1', re.IGNORECASE)
    attrs_found = attr_pattern.findall(parsed_text)

    entity_pattern = re.compile(r'&[a-z]+;|&#[0-9]+;', re.IGNORECASE)
    entities_found = entity_pattern.findall(parsed_text)

    code_block_pattern = re.compile(r'\{[^{]*?(?:color|background|margin|padding|function|var|let|const)\s*:.*?\w[^{]*?\}', re.IGNORECASE | re.DOTALL)
    code_blocks_found = code_block_pattern.findall(parsed_text)

    leakage_score = len(tags_found) + len(attrs_found) + len(entities_found) +len(code_blocks_found)

    return {
        "score" : leakage_score,
        "details": {
            "tags": len(tags_found),
            "attributes": len(attrs_found),
            "entities": len(entities_found),
            "code_blocks": len(code_blocks_found)
        }
    }


def compute_rougue_l(parsed_text : str, gold_text : str) -> dict:
    """
    Dato in input un parsed text e un gold text, restituisce il ROUGE-L score tra i due testi.
    ROUGUE-L e' la longest common subsequence tra
    """
    
    if not parsed_text.strip() or not gold_text.strip():
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)

    scores = scorer.score(gold_text, parsed_text)

    rouge_l_score = scores['rougeL']
    
    return {
        "precision": rouge_l_score.precision,
        "recall": rouge_l_score.recall,
        "f1": rouge_l_score.fmeasure # fmeasure è il nome interno per f1-score
    }
    

def comupute_error_rates(parsed_text: str, gold_text: str) -> dict:
    """
    Dato in input parsed e gold text, calcola WER e CER
    """

    if not gold_text.strip():
        if not parsed_text.strip():
            return {"wer": 0.0, "cer": 0.0} # Entrambi vuoti = nessun errore
        else:
            return {"wer": 1.0, "cer": 1.0} # Gold vuoto ma estratto pieno = 100% errore

    if not parsed_text.strip():
        return {"wer": 1.0, "cer": 1.0}
    
    try:
        wer_score = jiwer.wer(gold_text, parsed_text)
        cer_score = jiwer.cer(gold_text, parsed_text)
        
        return {
            "wer": float(wer_score),
            "cer": float(cer_score)
        }
    
    except Exception as e:
        # Fallback di sicurezza in caso di testi anomali
        print(f"Errore nel calcolo di WER/CER: {e}")
        return {"wer": 0.0, "cer": 0.0}


    
