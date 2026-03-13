#!/usr/bin/env python3
"""Quick verification tests for medical chatbot"""

from engine.search import hybrid_medical_search, autocorrect_medical_term

print("=" * 70)
print("QUICK VERIFICATION TESTS")
print("=" * 70)

# Test 1: Medical question (should route to LLM)
print("\n1. Medical Question: 'What are symptoms of cholera?'")
result = hybrid_medical_search("What are symptoms of cholera?")
print(f"   Route: {result['source']} | Confidence: {result['confidence']}")
print(f"   Status: {'✓ LLM' if result['source'] == 'llm' else '⚠ Other'}")

# Test 2: ICD code lookup (should route to local)
print("\n2. ICD Code: 'ICD code for cholera'")
result = hybrid_medical_search("ICD code for cholera")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result['data'], list):
   codes = [item.get('code') for item in result['data'] if item.get('code')]
    print(f"   Codes found: {codes[:3]}")
    print(f"   Status: {'✓ Local' if codes else '⚠ No codes'}")

# Test 3: LOINC search
print("\n3. LOINC: 'LOINC code for glucose'")
result = hybrid_medical_search("LOINC code for glucose")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result['data'], list):
   loinc_items = [item for item in result['data'] if item.get('system') == 'LOINC']
    print(f"   LOINC results: {len(loinc_items)}")
    if loinc_items:
        print(f"   Example: {loinc_items[0].get('code')} - {loinc_items[0].get('term')[:50]}")
    print(f"   Status: {'✓ LOINC' if loinc_items else '⚠ No LOINC'}")

# Test 4: RxNorm search
print("\n4. RxNorm: 'RxNorm code for aspirin'")
result = hybrid_medical_search("RxNorm code for aspirin")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result['data'], list):
    rxnorm_items = [item for item in result['data'] if item.get('system') == 'RXNORM']
    print(f"   RxNorm results: {len(rxnorm_items)}")
    if rxnorm_items:
        print(f"   Example: RXCUI {rxnorm_items[0].get('code')} - {rxnorm_items[0].get('term')[:50]}")
    print(f"   Status: {'✓ RxNorm' if rxnorm_items else '⚠ No RxNorm'}")

# Test 5: SNOMED search
print("\n5. SNOMED: 'SNOMED code for headache'")
result = hybrid_medical_search("SNOMED code for headache")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result['data'], list):
    snomed_items = [item for item in result['data'] if item.get('system') == 'SNOMED CT']
    print(f"   SNOMED results: {len(snomed_items)}")
    if snomed_items:
        print(f"   Example: {snomed_items[0].get('code')} - {snomed_items[0].get('term')[:50]}")
    print(f"   Status: {'✓ SNOMED' if snomed_items else '⚠ No SNOMED'}")

# Test 6: Project metadata (FHIR/ABDM/HL7 etc)
print("\n6. Project info: 'Tell me about FHIR'")
result = hybrid_medical_search("Tell me about FHIR")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result.get('data'), str):
    print(f"   Data snippet: {result['data'][:120].replace('\n',' ')}")
    print(f"   Status: {'✓ Found project info' if 'FHIR' in result['data'] else '⚠ Missing FHIR'}")

print("\n7. Project info: 'What is ABDM?'")
result = hybrid_medical_search("What is ABDM?")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result.get('data'), str):
    print(f"   Data snippet: {result['data'][:120].replace('\n',' ')}")
    print(f"   Status: {'✓ Found ABDM' if 'ABDM' in result['data'] else '⚠ Missing ABDM'}")
print("\n8. Project info: 'Explain HL7'")
result = hybrid_medical_search("Explain HL7")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result.get('data'), str):
    print(f"   Data snippet: {result['data'][:120].replace('\n',' ')}")
    print(f"   Status: {'✓ Found HL7' if 'HL7' in result['data'] else '⚠ Missing HL7'}")

print("\n9. Project info: 'Tell me about Mirth Connect'")
result = hybrid_medical_search("Tell me about Mirth Connect")
print(f"   Route: {result['source']}")
if result['source'] == 'local' and isinstance(result.get('data'), str):
    print(f"   Data snippet: {result['data'][:120].replace('\n',' ')}")
    print(f"   Status: {'✓ Found Mirth' if 'Mirth' in result['data'] else '⚠ Missing Mirth'}")

# Test 7: Autocorrect
# Test 7: Autocorrect
print("\n8. Autocorrect: 'glusose' -> ?")
vocabulary = ["glucose", "aspirin", "diabetes", "hypertension"]
corrected = autocorrect_medical_term("glusose", vocabulary)
print(f"   Result: '{corrected}'")
print(f"   Status: {'✓ Correct' if corrected.lower() == 'glucose' else '⚠ Wrong'}")

# Test 7: Mixed question
print("\n7. Mixed: 'Explain diabetes and give ICD code'")
result = hybrid_medical_search("Explain diabetes and give ICD code")
print(f"   Route: {result['source']}")
print(f"   Status: {'✓ Responds' if result['data'] else '⚠ No response'}")

# Test 8: Safety (non-medical)
print("\n8. Safety: 'Who is president of India?'")
result = hybrid_medical_search("Who is president of India?")
print(f"   Route: {result['source']}")
if result['source'] == 'llm' and isinstance(result['data'], str):
    if "only answer medical" in result['data'].lower():
        print(f"   Status: ✓ Restricted to medical")
    else:
        print(f"   Status: ⚠ Answered non-medical")
else:
    print(f"   Status: ? Other response")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
