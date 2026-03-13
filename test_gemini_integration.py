#!/usr/bin/env python3
"""Test Gemini API integration for medical chatbot"""

from engine.search import hybrid_medical_search, call_gemini_api

print("=" * 70)
print("TESTING GEMINI API INTEGRATION FOR MEDICAL CHATBOT")
print("=" * 70)

# Test 1: Direct Gemini API call
print("\n1️⃣  Testing direct Gemini API call...")
test_prompt = "What are the symptoms of malaria? Provide only medical information."
result = call_gemini_api(test_prompt, max_tokens=200)
if result:
    print("   ✅ Gemini API working!")
    print(f"   Response preview: {result[:100]}...")
else:
    print("   ❌ Gemini API failed")

# Test 2: Project.json query (FHIR)
print("\n2️⃣  Testing project.json integration (FHIR)...")
result = hybrid_medical_search("what is fhir")
print(f"   Source: {result.get('source')}")
print(f"   Route: {result.get('route')}")
if result.get('data'):
    preview = str(result.get('data'))[:100]
    print(f"   ✅ Got response: {preview}...")

# Test 3: Medical question
print("\n3️⃣  Testing medical question...")
result = hybrid_medical_search("what are symptoms of diabetes")
source = result.get('source')
print(f"   Source: {source}")
if result.get('data'):
    preview = str(result.get('data'))[:100]
    print(f"   ✅ Got response from {source}: {preview}...")
else:
    print("   ❌ No response")

# Test 4: Non-medical question (should filter)
print("\n4️⃣  Testing non-medical question filtering...")
result = hybrid_medical_search("who won the fifa world cup")
source = result.get('source')
print(f"   Source: {source}")
print(f"   Message: {result.get('message', result.get('data', ''))[:80]}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
