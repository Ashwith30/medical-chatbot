# Medical Guidelines Quick Reference

## System Behavior Summary

### Handling Different Query Types

#### Medical Questions (Accepted)
```
✅ "What is diabetes?"
✅ "Medicines for malaria"
✅ "Symptoms of asthma"
✅ "ICD code for hypertension"
✅ "How is pneumonia treated?"
✅ "I have fever and headache"
```

#### Non-Medical Questions (Rejected)
```
❌ "Who won the election?"
❌ "Best restaurants nearby"
❌ "How to lose weight fast" (lifestyle diet advice)
❌ "Sports news"
❌ "Tell a joke"
```

#### Emergency Scenarios (Immediate Alert)
```
🚨 "Severe chest pain"
🚨 "Can't breathe / breathing difficulty"
🚨 "Sudden paralysis"
🚨 "Stiff neck + high fever"
🚨 "Severe bleeding"
🚨 "Loss of consciousness"
→ Response: Red emergency alert + 911/999/112 routing
```

---

## Response Structure

### Example Response (Malaria - Explanation Intent)
```
🩺 Malaria
Malaria is an infectious disease caused by parasites transmitted through mosquito bites.
It causes cycles of fever, chills, and sweating. Without treatment, it can be life-threatening.

🤒 Common Symptoms
  • Cyclical high fever with chills and rigors
  • Severe headache and muscle/joint aches
  • Nausea, vomiting, and profuse sweating
  • Fatigue and general weakness

💊 Treatment
The standard first-line treatment is artemisinin-based combination therapy (ACT).
Most effective when started early; consult a doctor immediately if symptoms develop.

🔗 Source: WHO Malaria Guidelines
https://www.who.int/news-room/fact-sheets/detail/malaria

⚠️ This information is for educational purposes only...
```

### Example Response (Emergency - Chest Pain)
```
🚨 MEDICAL EMERGENCY DETECTED
Your symptoms suggest: possible heart attack or cardiac emergency.

TAKE ACTION IMMEDIATELY:
  • Call your local emergency number (911 in US, 999 in UK, 112 in EU)
  • Go to the nearest hospital emergency room
  • Do NOT wait — this requires immediate medical attention

This chatbot cannot replace emergency medical care. 
Please seek professional medical attention immediately.
```

---

## Language Simplification Rules

### Complex Term → Simplified
```
"Pathophysiology" → "How the disease works"
"Aetiology" → "What causes it"
"Respiratory distress" → "Trouble breathing"
"Hypertension" → "High blood pressure"
"Myocardial infarction" → "Heart attack"
"Septicemia" → "Blood infection"
"Anaphylaxis" → "Severe allergic reaction"
```

### Always Explain Technical Terms
```
❌ Wrong: "Requires ACE inhibitor therapy"
✅ Right: "Requires ACE inhibitor therapy (a type of blood pressure medicine)"

❌ Wrong: "Check your HbA1c levels"
✅ Right: "Check your HbA1c levels (a test that shows average blood sugar over 3 months)"
```

---

## What NOT To Do

### Never Diagnose
```
❌ "You have diabetes"
✅ "High blood sugar levels can indicate diabetes. See a doctor for testing."

❌ "This is definitely cancer"
✅ "Unexplained weight loss has many causes, including cancer. Medical evaluation is needed."
```

### Never Ask Follow-up Questions
```
❌ "What symptoms do you have exactly?"
✅ [Provide comprehensive answer based on extracted intent]

❌ "How long have you had this?"
✅ [Already provide answer for acute/chronic distinctions]
```

### Never Mention System Details
```
❌ "Database returned 3 matches for 'malaria'"
❌ "Arcee AI generated this response"
❌ "Querying ICD-10 tables..."
✅ [Just provide the medical information]
```

### Never Assume Expertise
```
❌ "As a medical AI..."
❌ "Our sophisticated algorithm determined..."
✅ "Medical information about..." [neutral, source-based]
```

---

## Symptom Categories

### Emergency Symptoms (Require 911/999/112)
- Chest pain/pressure/tightness
- Severe/inability to breathe
- Sudden severe headache
- Loss of consciousness
- Severe bleeding
- Stiff neck + fever
- Sudden weakness/paralysis
- Severe allergic reaction (swelling face/throat)
- Confusion in previously alert person

### Urgent Symptoms (See doctor same day)
- High fever (≥39°C) with confusion
- Persistent vomiting/diarrhea
- Severe abdominal pain
- Signs of infection (spreading redness, warmth)
- Sudden vision loss

### Common Symptoms (See doctor within week)
- Mild fever
- Cough, sore throat
- Headache without other symptoms
- Rash without other symptoms
- Nausea

---

## Code Systems Explained

### ICD-10 (Diagnoses)
```
Format: Letter + 2 digits (sometimes + period + decimals)
Example: E11.9 (Type 2 diabetes without complications)
Use: Disease/condition coding for medical records
Source: https://icd.who.int/browse10
```

### LOINC (Lab Tests)
```
Format: 5 digits + dash + 1 digit
Example: 2345-7 (Glucose in serum/plasma)
Use: Laboratory tests and measurements
Source: https://loinc.org
```

### RxNorm (Medications)
```
Format: RXCUI (number only)
Example: 284635 (Artemether-lumefantrine)
Use: Medication identification
Source: https://rxnav.nlm.nih.gov
```

### SNOMED CT (Clinical Terms)
```
Format: 6-18 digit number
Example: 44054006 (Diabetes mellitus, type 2)
Use: Comprehensive clinical terminology
Source: https://browser.ihtsdotools.org
```

---

## Guidelines Verification Checklist

Use this to verify any response follows guidelines:

```
☐ Easy to understand language (no unexplained jargon)
☐ Describes possibilities, NOT diagnosis
☐ Answers the specific question asked
☐ No follow-up questions
☐ Structured with emoji and clear sections
☐ Includes safety disclaimer
☐ No mentions of databases/APIs/models
☐ Relevant for the emergency status check
☐ Includes verification sources when available
☐ Does NOT attempt to diagnose disease
```

---

## Common User Scenarios

### Scenario: "I'm not feeling well"
❌ Query too vague to process effectively
✅ Response: "I can help if you describe your symptoms or the condition you're asking about. Examples: fever, headache, cough, etc."

### Scenario: "Is this serious?"
❌ Attempt to diagnose severity
✅ Response: [Explain symptoms] "Contact a doctor if symptoms worsen or persist. For emergencies, call 911/999/112"

### Scenario: "What medication should I take?"
❌ Recommend specific medications
✅ Response: [Show medication information] "Always consult your doctor for medication recommendations"

### Scenario: "How is this diagnosed?"
✅ Response: Explain testing procedures, not diagnosis interpretation

### Scenario: "What are the tests I should get?"
✅ Response: Explain relevant tests for the condition without ordering them

---

## Emergency Response Template

All emergencies follow this pattern:

```
🚨 MEDICAL EMERGENCY DETECTED
Your symptoms suggest: [symptom type detected]

TAKE ACTION IMMEDIATELY:
  • Call emergency: 911 (US) / 999 (UK) / 112 (EU)
  • Go to hospital NOW
  • Do NOT wait

⚠️ This chatbot cannot replace emergency care.
   Seek professional medical attention immediately.
```

---

**Remember**: This system is designed to **inform**, not **treat**. Always encourage professional medical consultation.

For more details, see:
- `GUIDELINES_IMPLEMENTATION.md` - Technical implementation
- `IMPLEMENTATION_SUMMARY.md` - Complete change summary
- `README.md` - Project overview
