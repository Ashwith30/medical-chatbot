#!/usr/bin/env python3
"""Test LOINC search and autocorrect functionality"""

from engine.search import search_loinc, autocorrect_medical_term, get_medical_terminology_info

print("=" * 60)
print("TESTING AUTOCORRECT")
print("=" * 60)

# Test autocorrect with common misspellings
test_words = [
    ("lonic", "LOINC"),
    ("glusose", "glucose"),
    ("hemoglobine", "hemoglobin"),
    ("cholesterol", "cholesterol"),  # correct spelling
]

for misspelled, correct in test_words:
    result = autocorrect_medical_term(misspelled, ["LOINC", "glucose", "hemoglobin", "cholesterol", "ionic"])
    status = "✓" if result.lower() == correct.lower() else "✗"
    print(f"{status} '{misspelled}' -> '{result}' (expected: {correct})")

print("\n" + "=" * 60)
print("TESTING LOINC SEARCH FOR HEMOGLOBIN")
print("=" * 60)

results = search_loinc("hemoglobin", limit=5)
if results:
    print(f"Found {len(results)} LOINC codes:\n")
    for r in results:
        print(f"  {r['code']}: {r['term']}")
        print(f"    Component: {r.get('component', 'N/A')}")
else:
    print("No results found - LOINC database may not be loaded properly")

print("\n" + "=" * 60)
print("TESTING PROJECT.JSON TERMINOLOGY")
print("=" * 60)

info = get_medical_terminology_info("LOINC")
if info:
    print(f"✓ Found LOINC information:")
    print(f"  Category: {info['category']}")
    print(f"  Description: {info['description'][:150]}...")
else:
    print("✗ No terminology info found")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
