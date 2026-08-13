import json
import csv
import urllib.request
import urllib.parse
from app import create_app

def extract_agents():
    # Use exact same strategy as co_discovery.py, but dump to CSV
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
            
        query = {
            "$select": select_fields,
            "$where": where_str,
            "$limit": 1000
        }
        
        url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
        print(f"Fetching: {url}")
        
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
            
    # Write to CSV
    import os
    csv_path = os.path.join(os.path.dirname(__file__), "agentes_socrata.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["entityid", "entityname", "agentfirstname", "agentlastname", "agentprincipalcity", "agentprincipalstate"])
        for r in results:
            writer.writerow([
                r.get("entityid", ""),
                r.get("entityname", ""),
                r.get("agentfirstname", ""),
                r.get("agentlastname", ""),
                r.get("agentprincipalcity", ""),
                r.get("agentprincipalstate", "")
            ])
            
    print(f"Extracted {len(results)} entities to {csv_path}")

if __name__ == "__main__":
    extract_agents()
