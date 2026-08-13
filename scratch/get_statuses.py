import urllib.request, urllib.parse, json

query = urllib.parse.urlencode({
    '$select': 'entitystatus, count(*)',
    '$group': 'entitystatus',
    '$limit': 50000
})
url = 'https://data.colorado.gov/resource/4ykn-tg5h.json?' + query
print(f'Fetching: {url}')
try:
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read().decode())
        print('Distinct entitystatus in Colorado:')
        for row in sorted(data, key=lambda x: int(x.get('count', 0)), reverse=True):
            print(f"{row.get('count', 0):>10} - {row.get('entitystatus', 'NULL')}")
except Exception as e:
    print('Error:', e)
