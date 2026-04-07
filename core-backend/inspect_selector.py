import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

url = 'https://www.minhngoc.net.vn/ket-qua-xo-so/dien-toan-vietlott/mega-6x45.html'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'
})

with urllib.request.urlopen(req, timeout=15) as r:
    html = r.read().decode('utf-8', errors='replace')

# Show context for circle-num
print("=== .circle-num contexts ===")
for m in re.finditer(r'circle-num', html):
    start = max(0, m.start()-50)
    end = min(len(html), m.end()+150)
    print(html[start:end])
    print("---")

# Show context for result-number
print("\n=== .result-number contexts (first 5) ===")
count = 0
for m in re.finditer(r'result-number', html):
    start = max(0, m.start()-30)
    end = min(len(html), m.end()+100)
    print(html[start:end])
    print("---")
    count += 1
    if count >= 5:
        break

# Show context for so-trung
print("\n=== .so-trung contexts ===")
for m in re.finditer(r'so-trung', html):
    start = max(0, m.start()-50)
    end = min(len(html), m.end()+200)
    print(html[start:end])
    print("---")
