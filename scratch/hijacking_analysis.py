import json
import urllib.request
import urllib.parse
from datetime import datetime

def analyze_hijacking():
    DATASET_ID = "4ykn-tg5h"
    BASE_URL = f"https://data.colorado.gov/resource/{DATASET_ID}.json"
    
    # We query exactly for agent firstname = Marcio and fetch all up to 15000 to be sure we get them all
    query = {
        "$where": "lower(agentfirstname) = 'marcio'",
        "$limit": 15000
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
    
    print("Fetching all 'Marcio' from Socrata...")
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
    
    target_name = "Marcio Garcia Andrade"
    deformed_variants = [
        "garcia andrrde",
        "garcia adrade",
        "garcio andrade",
        "andraded",
        "garcio garcia",
        "garcio",
        "gracia"
    ]
    
    deformed_records = []
    correct_addresses = set()
    
    for r in records:
        first = r.get("agentfirstname", "").strip()
        last = r.get("agentlastname", "").strip()
        middle = r.get("agentmiddlename", "").strip()
        full_name = " ".join(filter(None, [first, middle, last]))
        r["_full_name"] = full_name
        
        addr1 = r.get("agentprincipaladdress1", "").strip().upper()
        city = r.get("agentprincipalcity", "").strip().upper()
        zipc = r.get("agentprincipalzipcode", "").strip()
        full_addr = f"{addr1}, {city}, {zipc}"
        r["_full_addr"] = full_addr
        
        last_lower = last.lower()
        full_lower = full_name.lower()
        
        is_deformed = False
        for df in deformed_variants:
            if df in full_lower:
                # Need to be exact or somewhat exact to avoid matching correct ones
                is_deformed = True
                
        # Filter out correct ones if they somehow matched
        if full_lower == "marcio garcia andrade" or last_lower == "garcia" or last_lower == "andrade":
            is_deformed = False
            
        if is_deformed:
            deformed_records.append(r)
        elif last_lower == "garcia andrade" or last_lower == "andrade" or last_lower == "garcia":
            if addr1:
                correct_addresses.add(full_addr)
                
    for dr in deformed_records:
        date_str = dr.get("entityformdate", "")
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
                dr["_parsed_date"] = dt
            except:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    dr["_parsed_date"] = dt
                except:
                    dr["_parsed_date"] = datetime.min
        else:
            dr["_parsed_date"] = datetime.min
            
    deformed_records.sort(key=lambda x: x["_parsed_date"])
    
    print("\nDeformed records found:")
    for dr in deformed_records:
        date_str = dr["_parsed_date"].strftime("%Y-%m-%d") if dr["_parsed_date"] != datetime.min else "N/A"
        match = "YES" if dr["_full_addr"] in correct_addresses else "NO"
        print(f"{date_str} | {dr.get('entityid')} | {dr['_full_name']:30} | Match: {match} | {dr['_full_addr']}")

if __name__ == "__main__":
    analyze_hijacking()
