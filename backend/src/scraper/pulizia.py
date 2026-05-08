import re



def proteggi_formule(testo):
    """
    Estrae i blocchi {\displaystyle ...} bilanciando le parentesi graffe.
    Restituisce il testo con dei placeholder e un dizionario per ripristinare le formule.
    """
    placeholders = {}
    risultato = []
    i = 0
    math_idx = 0
    
    while i < len(testo):
        # Cerca l'inizio tipico delle formule Wikipedia
        if testo[i:].startswith(r'{\displaystyle'):
            start_idx = i
            brace_count = 0
            
            # Cerca la parentesi graffa di chiusura corrispondente
            for j in range(i, len(testo)):
                if testo[j] == '{':
                    brace_count += 1
                elif testo[j] == '}':
                    brace_count -= 1
                    
                # Quando il conteggio torna a zero, abbiamo isolato la formula completa
                if brace_count == 0:
                    end_idx = j + 1
                    formula = testo[start_idx:end_idx]
                    
                    # Creiamo e salviamo il placeholder
                    placeholder = f"§§MATH{math_idx}§§"
                    placeholders[placeholder] = formula
                    risultato.append(placeholder)
                    
                    i = end_idx
                    math_idx += 1
                    break
            else:
                # Se le parentesi sono sbilanciate (errore nel testo originale), procedi
                risultato.append(testo[i])
                i += 1
        else:
            risultato.append(testo[i])
            i += 1
            
    return "".join(risultato), placeholders


#Pulizia Markdown
async def pulizia(md):
    if md:
        # 2. regex solo per sezioni finali
        md = re.split(r'##\s*(Note|Riferimenti|Bibliografia|Collegamenti esterni|References|Media Contact|Frequently asked questions|Get help|Related|Additional resources|More information)', md, flags=re.IGNORECASE)[0]
    else: md = ""

    # 3. pulizia minima

    md, math_blocks = proteggi_formule(md)
    
    # link markdown
    md = re.sub(r'\[([^\]]+)\]\(([^()]*?(?:\([^()]*\)[^()]*)*)\s*(?:"[^"]*")?\)', r'\1', md)
    
    # url
    md = re.sub(r'\(https?://[^)]+\)', '', md)
    
    # note wikipedia
    md = re.sub(r'\[\[\d+\]\]', '', md)
    md = re.sub(r'\[\d+\]', '', md)
    md = re.sub(r'\[\[?\s*[Nn]ota\s*\d+\s*\]\]?', '', md)

    # italic corretto
    md = re.sub(r'_([^_]+)_', r'\1', md)

    # bold
    md = re.sub(r'\*\*([^*]+)\*\*', r'\1', md)

    # Elimina ogni singolo asterisco ovunque si trovi
    md = re.sub(r'\*', '', md)

    # Riformattazzione liste puntate
    md = re.sub(r'^\d+\.\s*', '', md, flags=re.M)

    # Riformattazzione :
    md = re.sub(r'\s+([,.!?;:])', r'\1', md)

    # header (TITOLI)
    md = re.sub(r'^#{1,6}\s*', '', md, flags=re.MULTILINE)

    md = re.sub(r'\[\s*\]', '', md)

    #Nyc
    md = re.sub(r'Learn how to [^\n]+', '', md)

    #Groki
    md = re.sub(r'\[\(#ref-\d+\)\]\(#ref-\d+\)', '', md)

    #Wiki
    md = re.sub(r"\(#cite[_]?note-?[^)]+\)", "", md)

    #Test 193
    md = re.sub(r'\`', '', md)

    #Virgolette
    md = re.sub(r'"\s*(.*?)\s*"', r'"\1"', md)
    md = re.sub(r'“\s*(.*?)\s*”', r'“\1”', md)

    #Wired
    #md = re.sub(r"'\s+", "'", md)

    # spazi
    md = re.sub(r'\s{2,}', ' ', md)
    md = re.sub(r'\n{3,}', '\n\n', md)

    for placeholder, formula_originale in math_blocks.items():
        md = md.replace(placeholder, formula_originale)

    md = re.sub(r'\\\\', r'\\', md)

    return md.strip()
