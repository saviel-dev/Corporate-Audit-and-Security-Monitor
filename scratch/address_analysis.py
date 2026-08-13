import json
import urllib.request
import urllib.parse
from datetime import datetime

def analyze_address():
    DATASET_ID = "4ykn-tg5h"
    BASE_URL = f"https://data.colorado.gov/resource/{DATASET_ID}.json"
    
    # We want to match all variations of 2236 E 109th Dr.
    # The simplest is to match the building number and zip, or just fetch all 80233 and filter in memory,
    # or fetch by building number "2236%" and filter in memory.
    query = {
        "$where": "agentprincipaladdress1 like '2236%109%'",
        "$limit": 50000
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
    
    print("Fetching all entities at 2236 E 109th...")
    req = urllib.request.Request(url)
    records = []
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            records = data
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
        
    print(f"Fetched {len(records)} records.")
    
    # Process and clean records
    processed_records = []
    for r in records:
        first = r.get("agentfirstname", "").strip()
        last = r.get("agentlastname", "").strip()
        middle = r.get("agentmiddlename", "").strip()
        full_name = " ".join(filter(None, [first, middle, last]))
        r["_full_name"] = full_name
        
        date_str = r.get("entityformdate", "")
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
                r["_parsed_date"] = dt
            except:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    r["_parsed_date"] = dt
                except:
                    r["_parsed_date"] = datetime.min
        else:
            r["_parsed_date"] = datetime.min
            
        processed_records.append(r)
        
    processed_records.sort(key=lambda x: x["_parsed_date"])
    
    # Q1: ¿Cuántas entidades tienen el nombre CORRECTO y en qué fechas?
    # Correct names: "Marcio Garcia Andrade", "Marcio Andrade", "Marcio Garcia" (if they match the same person)
    # The prompt explicitly asked about "Marcio Garcia Andrade"
    correct_names = ["marcio garcia andrade"]
    correct_records = [r for r in processed_records if r["_full_name"].lower() in correct_names]
    
    print("\n--- 1. Entidades con nombre CORRECTO ---")
    print(f"Total correctas: {len(correct_records)}")
    if correct_records:
        min_date = correct_records[0]["_parsed_date"]
        max_date = correct_records[-1]["_parsed_date"]
        print(f"Fechas desde {min_date.strftime('%Y-%m-%d')} hasta {max_date.strftime('%Y-%m-%d')}")
        
    # Q2: Ráfagas de las deformadas
    deformed_variants = ["garcia andrrde", "garcia adrade", "garcio andrade", "andraded", "garcio garcia", "garcio", "gracia"]
    deformed_records = []
    for r in processed_records:
        fl = r["_full_name"].lower()
        if fl not in correct_names and "marcio" in fl:
            if any(df in fl for df in deformed_variants):
                deformed_records.append(r)
                
    print("\n--- 2. Detalles de Ráfagas (Deformadas) ---")
    for r in deformed_records:
        date_str = r["_parsed_date"].strftime("%Y-%m-%d")
        print(f"Fecha: {date_str} | Nombre: {r['_full_name']:30} | Tipo: {r.get('entityform')} | Estado: {r.get('entitystatus')} | Nombre Entidad: {r.get('entityname')}")

    # Q3: Agentes con nombre COMPLETAMENTE distinto en esa dirección
    print("\n--- 3. Otros Agentes (Distintos a Marcio) en la misma dirección ---")
    other_agents = set()
    for r in processed_records:
        if "marcio" not in r["_full_name"].lower():
            other_agents.add(r["_full_name"])
    print(f"Total otros agentes: {len(other_agents)}")
    for a in list(other_agents)[:20]:
        print(f"- {a}")
        
    # Q4: Estado de las entidades deformadas
    print("\n--- 4. Estado de las entidades deformadas ---")
    status_counts = {}
    for r in deformed_records:
        st = r.get("entitystatus", "Unknown")
        status_counts[st] = status_counts.get(st, 0) + 1
    for k, v in status_counts.items():
        print(f"{k}: {v}")
        
    # Q5: Timeline for file output
    with open("scratch/timeline.txt", "w", encoding="utf-8") as f:
        f.write("Fecha | ID | Estado | Agente | Nombre Entidad\n")
        f.write("-" * 80 + "\n")
        for r in processed_records:
            date_str = r["_parsed_date"].strftime("%Y-%m-%d") if r["_parsed_date"] != datetime.min else "N/A"
            f.write(f"{date_str} | {r.get('entityid')} | {r.get('entitystatus')[:15]:15} | {r.get('_full_name')[:25]:25} | {r.get('entityname')}\n")
            
    print("\nLínea temporal completa escrita en scratch/timeline.txt")

if __name__ == "__main__":
    analyze_address()
