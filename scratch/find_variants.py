import csv

with open('scratch/agentes_socrata_muestra_marcio.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        full = f"{r['agentfirstname']} {r['agentlastname']}".lower()
        if 'andrrde' in full or 'adrade' in full or 'andraded' in full or 'garcio' in full:
            print(f"EID: {r['entityid']} - {r['agentfirstname']} {r['agentlastname']}")
