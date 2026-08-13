import json
import urllib.request
import urllib.parse
from collections import Counter
from datetime import datetime
from app import create_app
from app.models import Corporation

def run_investigation():
    DATASET_ID = "4ykn-tg5h"
    BASE_URL = f"https://data.colorado.gov/resource/{DATASET_ID}.json"
    
    query = {
        "$where": "agentprincipaladdress1 like '2236%109%'",
        "$limit": 50000
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
    
    print("Fetching all entities at 2236 E 109th...")
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            records = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
        
    print(f"Fetched {len(records)} records.")
    
    # Process basic stats
    agent_counts = Counter()
    good_standing_count = 0
    after_sept_5_2024_count = 0
    
    for r in records:
        # Agent distribution
        first = r.get("agentfirstname", "").strip()
        last = r.get("agentlastname", "").strip()
        middle = r.get("agentmiddlename", "").strip()
        full_name = " ".join(filter(None, [first, middle, last]))
        if not full_name:
            full_name = r.get("agentorganizationname", "UNKNOWN").strip()
            
        agent_counts[full_name] += 1
        
        # Chronology
        st = r.get("entitystatus", "")
        if st.lower() == "good standing":
            good_standing_count += 1
            
        form_date = r.get("entityformdate", "")
        if form_date:
            if "2024-09-06" <= form_date: # simple string comparison works for ISO dates
                after_sept_5_2024_count += 1
            if "2024-09-05" in form_date: # just in case some were formed on the exact day
                pass
                
    # Entity vs Agent address discrimination
    same_address_count = 0
    diff_address_count = 0
    for r in records:
        a_addr = r.get("agentprincipaladdress1", "").strip().lower()
        e_addr = r.get("principaladdress1", "").strip().lower()
        # Clean basic words to compare
        if a_addr.replace("drive", "dr").replace("east", "e") == e_addr.replace("drive", "dr").replace("east", "e"):
            same_address_count += 1
        else:
            diff_address_count += 1

    print("\n--- 1. SEÑALES ALTERNATIVAS ---")
    print(f"Campos disponibles en Socrata: entityname, principaladdress, entitystatus, entitytype, agentname, agentaddress.")
    print(f"¿Email o teléfono? NO existen en la API Socrata de CO.")
    print(f"¿Dirección de la entidad (principaladdress1) es diferente a la del agente?")
    print(f"  - Comparten la misma dirección: {same_address_count}")
    print(f"  - Dirección de entidad distinta al agente: {diff_address_count}")
    
    print("\n--- 2. CRONOLOGÍA ---")
    print(f"Entidades en Good Standing hoy en esa dirección: {good_standing_count}")
    print(f"Entidades creadas DESPUÉS del 5 de sep de 2024: {after_sept_5_2024_count}")
    
    print("\n--- 3. DISTRIBUCIÓN DE 380 AGENTES ---")
    sorted_agents = agent_counts.most_common()
    for agent, count in sorted_agents[:15]:
        print(f"{count:5d} - {agent}")
    print(f"... y {len(sorted_agents) - 15} agentes más con <= {sorted_agents[15][1]} entidades.")

    # Status of the 27 entities in local DB
    app = create_app()
    with app.app_context():
        # Get all entities from Colorado in DB
        db_entities = Corporation.query.filter_by(state="CO").all()
        print("\n--- ESTADO DE LAS 27 ENTIDADES EN BASE DE DATOS ---")
        print(f"Total entidades CO en DB: {len(db_entities)}")
        
        # We need to cross-reference with Socrata records if we want the actual status, 
        # or we just use the name if we have it. The DB doesn't store status, only name and agent.
        # But we can look up their entityname in the records we just fetched.
        db_names = {c.name.lower() for c in db_entities}
        
        db_status_counts = Counter()
        found_in_socrata = 0
        
        for r in records:
            if r.get("entityname", "").lower() in db_names:
                db_status_counts[r.get("entitystatus", "Unknown")] += 1
                found_in_socrata += 1
                
        print(f"Entidades de la DB encontradas en este dataset: {found_in_socrata}")
        for status, count in db_status_counts.items():
            print(f"  {status}: {count}")

if __name__ == "__main__":
    run_investigation()
