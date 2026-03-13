#!/usr/bin/env python3
"""Test that Flask responses are correctly formatted"""

import requests
import json

BASE_URL = "http://localhost:5020"

print("=" * 70)
print("TESTING FLASK RESPONSE FORMAT")
print("=" * 70)

test_queries = [
    ("what is fhir", "Project.json test"),
    ("tell me about ABDM", "Project.json test"),
    ("what are symptoms of diabetes", "Medical knowledge test"),
    ("give me ICD code for malaria", "Code lookup test"),
]

for query, description in test_queries:
    print(f"\n📝 {description}: '{query}'")
    
    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json={"query": query},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"   ❌ HTTP {response.status_code}")
            continue
        
        data = response.json()
        status = data.get("status")
        source = data.get("source")
        
        # Check for expected fields
        has_text = bool(data.get("data") or data.get("enrichment") or data.get("explanation"))
        has_codes = bool(data.get("codes"))
        
        print(f"   ✅ Status: {status}")
        print(f"   ✅ Source: {source}")
        print(f"   {'✅' if has_text else '❌'} Has text content: {has_text}")
        print(f"   {'✅' if has_codes or source == 'local' else '⚠️'} Has codes: {has_codes}")
        
        # Show preview
        text_preview = (data.get("data") or data.get("enrichment") or data.get("explanation") or "")[:80]
        if text_preview:
            print(f"   📄 Content: {text_preview.replace(chr(10), ' ')}...")
        
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to {BASE_URL}")
        break
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
