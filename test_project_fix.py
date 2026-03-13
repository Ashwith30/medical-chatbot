#!/usr/bin/env python3
"""Test that project.json integration is working correctly"""

from engine.search import hybrid_medical_search

print("=" * 70)
print("TESTING PROJECT.JSON INTEGRATION FIX")
print("=" * 70)

# Test queries for project.json standards
test_queries = [
    "what is fhir",
    "tell me about ABDM",
    "explain LOINC",
    "what is RxNorm?",
    "describe Mirth Connect",
    "tell me about HL7",
    "what is SNOMED CT?"
]

for query in test_queries:
    print(f"\n📝 Query: '{query}'")
    result = hybrid_medical_search(query)
    source = result.get("source", "unknown")
    
    # Check if it returned project.json data
    data = result.get("data", "")
    route = result.get("route", "")
    
    if route == "project" or (source == "local" and isinstance(data, str) and len(data) > 50):
        # Successful - got project data
        print(f"   ✅ Source: {source}")
        print(f"   ✅ Route: {route}")
        # Show first 100 chars of response
        if isinstance(data, str):
            preview = data[:100].replace('\n', ' ')
            print(f"   📄 Preview: {preview}...")
    else:
        # Failed - didn't get project data
        print(f"   ❌ Source: {source}")
        print(f"   ❌ Route: {route}")
        if isinstance(data, str):
            preview = data[:80].replace('\n', ' ')
            print(f"   📄 Got: {preview}...")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
