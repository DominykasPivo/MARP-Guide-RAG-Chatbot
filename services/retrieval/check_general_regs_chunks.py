import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION = "chunks"
TARGET_URL = "https://www.lancaster.ac.uk/media/lancaster-university/content-assets/documents/student-based-services/asq/marp/General-Regs.pdf"

query = {
    "filter": {
        "must": [
            {"key": "url", "match": {"value": TARGET_URL}}
        ]
    },
    "limit": 10,
    "with_payload": True
}

response = requests.post(
    f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
    json=query
)

if response.ok:
    data = response.json()
    points = data.get("result", {}).get("points", [])
    print(f"Found {len(points)} chunks from General-Regs.pdf:")
    for i, pt in enumerate(points, 1):
        print(f"Chunk {i} (id={pt['id']}):")
        print(f"  Text: {pt['payload'].get('text', '')[:100]}...")
        print(f"  Page: {pt['payload'].get('page', 'N/A')}")
        print()
else:
    print(f"Qdrant API error: {response.status_code}")
    print(response.text)
