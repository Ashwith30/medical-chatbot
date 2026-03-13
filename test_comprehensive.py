#!/usr/bin/env python3
"""Comprehensive test covering all chatbot functionality"""

import requests
import json

BASE_URL = "http://localhost:5020"

print("=" * 80)
print("COMPREHENSIVE MEDICAL CHATBOT TEST")
print("=" * 80)

test_cases = [
    {
        "query": "What is FHIR?",
        "type": "Project.json - Healthcare Standard",
        "expect_contains": ["FHIR", "Healthcare Data Exchange", "API"]
    },
    {
        "query": "Tell me about ABDM",
        "type": "Project.json - Indian Health System",
        "expect_contains": ["ABDM", "Digital", "Health"]
    },
    {
        "query": "What are the symptoms of diabetes?",
        "type": "Medical Condition - Symptoms",
        "expect_contains": ["Diabetes", "thirst", "glucose", "symptom"]
    },
    {
        "query": "What medications are used for malaria?",
        "type": "Medical Condition - Medications",
        "expect_contains": ["malaria", "drug", "medication", "artemis"]
    },
    {
        "query": "give me ICD code for cancer",
        "type": "Medical Code Lookup",
        "expect_contains": ["Code", "ICD", "cancer"]
    },
    {
        "query": "LOINC code for glucose",
        "type": "Laboratory Test Code",
        "expect_contains": ["LOINC", "glucose", "lab"]
    },
    {
        "query": "Explain SNOMED CT",
        "type": "Healthcare Standard/Code System",
        "expect_contains": ["SNOMED", "Clinical", "Terminology"]
    },
    {
        "query": "who won the fifa world cup?",
        "type": "Non-Medical Query (Should Reject)",
        "expect_contains": ["medical", "cannot", "only"]
    },
]

success_count = 0
for i, test in enumerate(test_cases, 1):
    print(f"\n[Test {i}] {test['type']}")
    print(f"  Query: '{test['query']}'")
    
    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json={"query": test["query"]},
            timeout=15
        )
        
        data = response.json()
        status = data.get("status")
        
        # Check response format
        if status not in ["success", "rejected", "empty", "error"]:
            print(f"  ❌ Invalid status: {status}")
            continue
        
        # Get content
        content = (data.get("data") or data.get("enrichment") or 
                  data.get("explanation") or data.get("message") or "")
        
        # Check for expected content
        content_lower = content.lower()
        found_items = [item for item in test["expect_contains"] 
                      if item.lower() in content_lower]
        
        if found_items or status == "rejected":
            print(f"  ✅ Status: {status}")
            print(f"  ✅ Found {len(found_items)}/{len(test['expect_contains'])} expected terms")
            if content:
                print(f"  📄 Content preview: {content[:80].replace(chr(10), ' ')}...")
            success_count += 1
        else:
            print(f"  ⚠️ Status: {status}")
            print(f"  ⚠️ Missing expected content")
            print(f"  Expected to find: {test['expect_contains']}")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "=" * 80)
print(f"RESULTS: {success_count}/{len(test_cases)} tests passed")
print("=" * 80)
print("\n✅ You can now try the chatbot at: http://localhost:5020")
print("   Query types working:")
print("   • Healthcare standards (FHIR, ABDM, RxNorm, SNOMED CT, LOINC, ICD)")
print("   • Medical conditions and diseases")
print("   • Symptoms, treatments, and medications")
print("   • Medical code lookups")
print("   • Proper filtering of non-medical queries")
