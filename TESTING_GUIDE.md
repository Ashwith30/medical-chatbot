# Testing Guide - Medical Guidelines Implementation

## Pre-Testing Setup

1. **Start the Application**
   ```bash
   cd "c:\Users\Hp\OneDrive\Desktop\Medical ChatBot"
   python app.py
   ```
   Expected: Server starts on http://localhost:5000

2. **Open in Browser**
   - Navigate to `http://localhost:5000`
   - Chat interface should load with welcome message

3. **Verify Backend Ready**
   - Check console for: `🏥  Medical ChatBot starting on port 5000`
   - No Python errors should appear

---

## Test Suite 1: Emergency Detection ⚠️

All emergency queries must be detected and return red alert with hospital routing.

### Test 1.1: Chest Pain
```
Query:    "I have severe chest pain"
Expected: 🚨 MEDICAL EMERGENCY DETECTED
          Red alert with pulsing animation
          911/999/112 routing instruction
Fail If:  Shows normal response instead
```

### Test 1.2: Breathing Difficulty
```
Query:    "I can't breathe, having trouble breathing"
Expected: Emergency alert about respiratory distress
          Red styling with clear action items
Fail If:  Treated as normal medical question
```

### Test 1.3: Sudden Paralysis
```
Query:    "sudden paralysis on my left side"
Expected: Emergency alert mentioning stroke possibility
          Clear: Go to hospital immediately
Fail If:  Provides normal explanation instead of emergency alert
```

### Test 1.4: Meningitis Signs
```
Query:    "stiff neck and high fever"
Expected: Emergency alert suggesting meningitis
          Red alert with 911 routing
Fail If:  Just explains meningitis symptoms normally
```

### Test 1.5: Loss of Consciousness
```
Query:    "I lost consciousness, what should I do?"
Expected: Immediate emergency alert
Fail If:  Normal response without emergency styling
```

### Test 1.6: Severe Bleeding
```
Query:    "severe bleeding that won't stop"
Expected: Emergency alert
          Action: Call emergency services
Fail If:  Provides first aid tips instead of hospital routing
```

---

## Test Suite 2: Simple Language Check 📝

All responses should use simple language without unexplained medical jargon.

### Test 2.1: Diabetes Explanation
```
Query:    "What is diabetes?"
Check:    1. No term like "hyperglycemia" without explanation
          2. Uses "high blood sugar" not just "elevated glucose"
          3. Simple 2-3 sentence explanation
          4. Emoji-based structure (🩺 Condition)
Fail If:  Heavy medical terminology, complex sentences
```

### Test 2.2: Complex Condition
```
Query:    "What is myocardial infarction?"
Check:    1. Should also show "Heart Attack" clearly
          2. Explains "cardiac muscle damage" simply
          3. No "ST-elevation" jargon without explanation
Fail If:  Response only uses medical terms
```

### Test 2.3: Medication Names
```
Query:    "medicines for asthma"
Check:    1. Drug names shown (Salbutamol)
          2. Patient-friendly explanation: "(rescue inhaler)"
          3. Not just "SABA reliever" without explanation
Fail If:  Only shows medical abbreviations like "SABA"
```

---

## Test Suite 3: No Follow-Up Questions ❓

The system should never ask for more information - it should provide comprehensive answers.

### Test 3.1: Vague Symptom
```
Query:    "I have fever"
Response: Should provide information about fever causes
          NOT ask: "How long has this been happening?"
          NOT ask: "Any other symptoms?"
Fail If:  Response ends with question marks asking for details
```

### Test 3.2: Short Query
```
Query:    "malaria"
Response: Should provide comprehensive information
          NOT ask: "What specifically do you want to know?"
Fail If:  Response is incomplete pending more information
```

### Test 3.3: Medication Query
```
Query:    "What medications help diabetes?"
Response: Lists medications with explanations
          NOT ask: "Do you have type 1 or type 2?"
Fail If:  Response is incomplete without follow-up answers
```

---

## Test Suite 4: No Diagnosis 🚫

System should explain possibilities, not diagnose definitively.

### Test 4.1: Symptom Description
```
Query:    "fever, cough, sore throat"
Response: ✅ Should say: "These symptoms could indicate..."
          ✅ Should say: "Common causes include..."
          ❌ Should NOT say: "You have the flu"
          ❌ Should NOT say: "This is pneumonia"
Fail If:  Response gives definitive diagnosis
```

### Test 4.2: Specific Condition Query
```
Query:    "Do I have cancer?"
Response: ✅ Should explain: "Cancer would need professional evaluation"
          ✅ Should mention: "Symptoms overlap with many conditions"
          ❌ Should NOT say: "Yes, you have cancer"
          ❌ Should NOT say: "No, you definitely don't"
Fail If:  Makes definitive diagnosis claim
```

### Test 4.3: Condition with Symptoms
```
Query:    "I have fever and swollen lymph nodes, do I have malaria?"
Response: ✅ Explains these symptoms
          ✅ Lists possible causes (including malaria)
          ❌ Does NOT say "You have malaria"
Fail If:  Diagnoses specific disease
```

---

## Test Suite 5: Response Structure 🎨

All responses must follow clear structure with emoji sections.

### Test 5.1: Condition Explanation
```
Query:    "What is hypertension?"
Structure:
  ✅ 🩺 Hypertension (heading)
  ✅ [2-3 sentence explanation]
  ✅ 🤒 Common Symptoms (if applicable)
  ✅ 💊 Treatments (if applicable)
  ✅ Source/verification link
  ✅ Disclaimer
Fail If:  Plain text without sections or emojis
```

### Test 5.2: Medication Info
```
Query:    "medicines for asthma"
Structure:
  ✅ 💊 Asthma — Common Medications
  ✅ • [Drug name] — [What it does]
  ✅ • [Drug name] — [What it does]
  ✅ Source links
  ✅ Disclaimer
Fail If:  Unstructured list
```

### Test 5.3: Symptom Query
```
Query:    "symptoms of malaria"
Structure:
  ✅ 🤒 Malaria — Common Symptoms
  ✅ • [Symptom explanation]
  ✅ • [Symptom explanation]
  ✅ [When to see doctor guidance]
  ✅ Disclaimer
Fail If:  Just lists symptoms without explanations
```

---

## Test Suite 6: Always Include Disclaimer ⚠️

Every response must end with disclaimer.

### Test 6.1: Disclaimer on Normal Response
```
Any query like "What is asthma?"
Response must include:
  ⚠️ This information is for educational purposes only...
  Always consult a qualified healthcare professional
Fail If:  Disclaimer missing from any response
```

### Test 6.2: Disclaimer on Emergency
```
Emergency query
Response must include:
  Multiple disclaimers/warnings
  Text about seeking professional care IMMEDIATELY
Fail If:  No emphasization of needing real medical care
```

---

## Test Suite 7: Medical Code Information 📋

System should properly handle code queries.

### Test 7.1: ICD-10 Code Lookup
```
Query:    "ICD-10 code for diabetes"
Response: ✅ Shows code: E11.9 or similar
          ✅ Shows system: ICD-10
          ✅ Shows term: Type 2 Diabetes Mellitus
          ✅ Includes source link to ICD registry
Fail If:  Cannot find/display code
```

### Test 7.2: RxNorm Code Lookup
```
Query:    "RxNorm code of aspirin"
Response: ✅ Shows RXCUI: 1191
          ✅ Shows system: RxNorm
          ✅ Shows drug name
          ✅ Includes source link
Fail If:  Cannot find medication code
```

### Test 7.3: Code Table Display
```
Any code response
Check:    ✅ Codes shown in table format
          ✅ System indicated (🏥 ICD-10, 💊 RxNorm, 🧪 LOINC)
          ✅ Colored badges for each system
          ✅ Top 3 codes shown (not overwhelming)
Fail If:  Codes not clearly organized
```

---

## Test Suite 8: No System Details 🪐

Responses must not mention internal details.

### Test 8.1: No Database Mentions
```
Any response should NOT contain:
  ❌ "Database found 5 matches"
  ❌ "Querying ICD-10 table"
  ❌ "Local search returned..."
  ❌ "Arcee AI responded..."
Fail If:  Internal system details exposed
```

### Test 8.2: No API Mentions
```
Any response should NOT contain:
  ❌ "API called successfully"
  ❌ "/search endpoint returned"
  ❌ "JSON response:"
Fail If:  Technical API details mentioned
```

### Test 8.3: No Model References
```
Any response should NOT contain:
  ❌ "The AI model determined..."
  ❌ "Machine learning algorithm..."
  ❌ "Language model response..."
Fail If:  References technical AI systems
```

---

## Test Suite 9: Non-Medical Query Rejection 🚫

System must reject non-medical topics.

### Test 9.1: Sports Query
```
Query:    "Who won the football match?"
Expected: "I can only answer medical questions"
          Not an emergency alert
          Polite refusal
Fail If:  Attempts to answer or error
```

### Test 9.2: Weather Query
```
Query:    "What's the weather tomorrow?"
Expected: Rejection with info about medical-only scope
Fail If:  Any attempt to answer
```

### Test 9.3: Diet Advice (Lifestyle)
```
Query:    "Best diet to lose weight fast"
Expected: Rejection (not clinical medical)
          Note: Might accept "How does diabetes affect diet?"
Fail If:  Attempts to provide fitness/diet tips
```

---

## Test Suite 10: Error Handling 🛡️

System handles errors gracefully.

### Test 10.1: Empty Query
```
Query:    "" (empty)
Expected: "Please enter a valid medical question"
          Not a server error
Fail If:  500 error or blank response
```

### Test 10.2: Very Long Query
```
Query:    [1000+ character medical question]
Expected: "Query too long (max 500 chars)"
Fail If:  Times out or crashes
```

### Test 10.3: Special Characters
```
Query:    "What is <script>alert('xss')</script>?"
Expected: Safely escaped, not executed
          Treat as medical query if possible
Fail If:  XSS vulnerability or errors
```

---

## Automated Test Checklist

Use this to quickly verify the system:

```
✅ Emergency Detection
   - [ ] Chest pain → Red emergency alert
   - [ ] Breathing issues → Emergency routing
   - [ ] Stiff neck + fever → Meningitis emergency

✅ Simple Language
   - [ ] Diabetes query → No jargon
   - [ ] Medication query → Plain terms
   - [ ] Complex condition → Explained clearly

✅ No Follow-Ups
   - [ ] Vague query → Full answer
   - [ ] Short query → Complete response
   - [ ] No "Tell me more?" questions

✅ No Diagnosis
   - [ ] Symptoms query → "Could indicate..."
   - [ ] Condition query → Explained, not diagnosed
   - [ ] No "You have X disease" statements

✅ Structure
   - [ ] Emoji headings present (🩺 🤒 💊)
   - [ ] Clear sections
   - [ ] Readable formatting

✅ Disclaimer
   - [ ] On all responses
   - [ ] Prominent for emergencies
   - [ ] Clear wording

✅ Codes
   - [ ] Lookup works (ICD, RxNorm, LOINC)
   - [ ] Table displays properly
   - [ ] Color-coded by system

✅ System Details
   - [ ] No "Database found..."
   - [ ] No "API returned..."
   - [ ] No "AI determined..."

✅ Rejection
   - [ ] Non-medical rejected
   - [ ] Polite message
   - [ ] Clear scope stated

✅ Errors
   - [ ] Empty query handled
   - [ ] Long query handled
   - [ ] Special chars escaped
```

---

## Reporting Issues

If tests fail:
1. Check the error message
2. Reference which test suite failed
3. Document the exact query and response
4. Check browser console (F12) for JavaScript errors
5. Check server console for Python errors

---

## Quick Start Testing

Run these 5 queries to verify all systems:

```
1. "severe chest pain" 
   → Should show emergency alert in red

2. "What is asthma?"
   → Should show simple explanation with 🩺 structure

3. "ICD-10 code for hypertension"
   → Should show code in table with source link

4. "Who won the election?"
   → Should reject with "medical only" message

5. "medicines for malaria"
   → Should list drugs simply with 💊 header
```

If all 5 show expected responses, the implementation is working correctly.

---

**Test Status**: Ready for comprehensive validation
**Last Updated**: March 12, 2026
