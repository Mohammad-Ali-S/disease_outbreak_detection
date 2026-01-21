import requests
import json

try:
    resp = requests.get("http://localhost:8000/api/public/dashboard")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    
    analysis = data.get("analysis", {})
    clusters = analysis.get("clusters", [])
    network = analysis.get("network", [])
    
    print(f"Clusters Count: {len(clusters)}")
    print(f"Network Edges: {len(network)}")
    
    if len(clusters) > 0:
        print("SUCCESS: Data for map visualization is present.")
        print(f"Sample Cluster: {json.dumps(clusters[0], indent=2)}")
    else:
        print("WARNING: No clusters returned. Is there enough data?")

except Exception as e:
    print(f"Error: {e}")
