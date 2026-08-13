import json
import csv
import urllib.request
import urllib.parse
from app import create_app
import re

def analyze():
    DATASET_ID = "4ykn-tg5h"
    BASE_URL = f"https://data.colorado.gov/resource/{DATASET_ID}.json"
    
    app = create_app()
    with app.app_context():
        detection_required = app.config.get("DETECTION_REQUIRED", "Marcio")
        detection_alternates = app.config.get("DETECTION_ALTERNATES", ["Garcia", "Andrade"])
        
    terms = [{"first": detection_required, "last": alt} for alt in detection_alternates]
    terms.append({"first": detection_required, "last": None})
    
    select_fields = (
        "entityid,entityname,entitystatus,entityformdate,"
        "agentfirstname,agentmiddlename,agentlastname,agentsuffix,"
        "agentorganizationname,agentprincipalcity,agentprincipalstate"
    )
    
    seen_ids = set()
    results = []
    
    for term in terms:
        where_clauses = []
        if term["first"]:
            where_clauses.append(f"lower(agentfirstname) = '{term['first'].lower()}'")
        if term["last"]:
            where_clauses.append(f"lower(agentlastname) = '{term['last'].lower()}'")
            
        where_str = " AND ".join(where_clauses)
        if not where_str:
            continue
            
        # The EXACT query from earlier with limit 1000
        query = {
            "$select": select_fields,
            "$where": where_str,
            "$limit": 1000
        }
        
        url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for r in data:
                    eid = r.get("entityid")
                    if eid and eid not in seen_ids:
                        seen_ids.add(eid)
                        results.append(r)
        except Exception as e:
            print(f"Error fetching data: {e}")

    # Analysis
    apellidos = set()
    vacio_o_anomalo = 0
    apellidos_compuestos_o_guion = 0
    sufijos = 0
    middle_initials = 0
    anomalous_examples = []
    
    for r in results:
        first = r.get('agentfirstname', '').strip()
        last = r.get('agentlastname', '').strip()
        middle = r.get('agentmiddlename', '').strip()
        suffix = r.get('agentsuffix', '').strip()
        
        full = f"{first} {middle} {last} {suffix}".strip()
        
        if last:
            apellidos.add(last.lower())
            
        if not first and not last:
            vacio_o_anomalo += 1
            anomalous_examples.append(f"Vacío (EID: {r['entityid']})")
        elif (first and len(first) <= 1) or (last and len(last) <= 1):
             vacio_o_anomalo += 1
             anomalous_examples.append(f"Anómalo (inicial): '{full}' (EID: {r['entityid']})")
            
        if " " in last or "-" in last:
            apellidos_compuestos_o_guion += 1
            
        if suffix or re.search(r'\b(jr\.?|sr\.?|ii|iii|iv|v)\b', last, re.IGNORECASE) or re.search(r'\b(jr\.?|sr\.?|ii|iii|iv|v)\b', first, re.IGNORECASE):
            sufijos += 1
            
        if middle:
            middle_initials += 1
            
        if re.search(r'[0-9!@#$%^&*()_+={}\[\]|\\:;"\'<>,.?/]', full):
            anomalous_examples.append(f"Caracteres raros: '{full}' (EID: {r['entityid']})")
            
        if len(last) > 20:
            anomalous_examples.append(f"Apellido muy largo: '{last}' (EID: {r['entityid']})")
            
    print(f"Total registros: {len(results)}")
    print(f"Apellidos distintos: {len(apellidos)}")
    print(f"Apellidos compuestos o con guion: {apellidos_compuestos_o_guion}")
    print(f"Sufijos detectados: {sufijos}")
    print(f"Inicial/nombre del medio (agentmiddlename): {middle_initials}")
    print(f"Vacíos o anómalos: {vacio_o_anomalo}")
    
    print("\nCasos más raros:")
    seen_ex = set()
    dedup = []
    for ex in anomalous_examples:
        val = ex.split("(EID:")[0]
        if val not in seen_ex:
            seen_ex.add(val)
            dedup.append(ex)
            
    for ex in dedup[:15]:
        print(f"- {ex}")

if __name__ == "__main__":
    analyze()
