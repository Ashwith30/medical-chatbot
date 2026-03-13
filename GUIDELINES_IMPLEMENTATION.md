# Medical Information Guidelines Implementation

This document outlines how the Medical ChatBot has been enhanced to follow comprehensive medical information guidelines, ensuring safe, clear, and responsible medical information delivery.

## Guidelines Implemented

### 1. **Understanding the User's Question**
- **Implementation**: The chatbot uses intent detection to understand what users are asking, regardless of grammar, spelling mistakes, or sentence structure
- **Features**:
  - `_detect_intent()` function classifies queries into: `code_only`, `medication_only`, `symptoms_only`, `treatment_only`, `explain`, or `full`
  - `normalize_query()` function corrects common medical term typos
  - Accepts various phrasing patterns (e.g., "medicines for X", "I have X", "what is X")

### 2. **Simple Language in Responses**
- **Implementation**: All LLM prompts now include explicit instructions to use simple language
- **Key Instructions in Prompts**:
  ```
  "Use SIMPLE language — anyone with basic education should understand"
  "Avoid medical jargon; if technical terms are needed, explain them briefly"
  ```
- **Response Structure**: Uses emoji-based formatting (🩺, 🤒, 💊) to make information visually clear

### 3. **No Follow-Up Questions**
- **Implementation**: System provides comprehensive answers without asking for clarification
- **Logic**: Extracts the condition/topic from the query using `_extract_condition()` and provides direct answers

### 4. **Never Diagnoses**
- **Implementation**: System avoids diagnostic statements
- **Safeguards**:
  - Prompts teach the LLM to explain symptoms/conditions rather than diagnose
  - Responses provide general medical information, not diagnoses
  - Clear language: "possible causes" rather than "you have"

### 5. **Emergency Symptom Detection**
- **NEW FEATURE**: Highest priority safety mechanism
- **Implementation**: `_detect_emergency_symptoms()` function checks for dangerous symptoms
- **Detected Emergencies**:
  - Chest pain, severe breathing difficulty, sudden paralysis
  - Severe confusion with fever, stiff neck (meningitis)
  - Severe bleeding, anaphylaxis, severe trauma
  - Loss of consciousness, cardiac issues
- **Response**: Immediately alerts user to seek emergency care with routing to hospital/emergency numbers

### 6. **Structured Response Format**
- **Implementation**: Responses use emoji-based sections for clarity
- **Sections**:
  - 🩺 Condition / Topic
  - 🤒 Common Symptoms
  - 💊 Treatments or Medicines
  - 🔗 Source / Verification links

### 7. **Medical Code Information**
- **Implementation**: System handles multiple coding systems
- **Supported Systems**:
  - ICD-10 (diagnoses)
  - LOINC (lab tests)
  - RxNorm/RXCUI (medications)
  - SNOMED CT/SCT (clinical terms)
  - CPT, HCPCS, NDC codes
- **Verification**: Each code is verified with authoritative sources

### 8. **Avoids Medical Jargon**
- **Implementation**: Prompts explicitly require translation of technical terms
- **Enforcement**:
  - "Avoid medical jargon; if technical terms are needed, explain them briefly"
  - LLM instructed to use plain language equivalents
  - Defines complex terms when necessary

### 9. **No Internal System Details**
- **Implementation**: Prompts prevent mention of system internals
- **Safeguards**: 
  - "Do NOT mention database names, AI models, or system details"
  - Responses avoid references to APIs, databases, or technical architecture
  - Focuses only on medical information

### 10. **Always Includes Safety Note**
- **Implementation**: Enhanced disclaimer on all responses
- **Current Disclaimer**:
  ```
  ⚠️ This information is for educational purposes only and is NOT a substitute 
  for professional medical advice. Always consult a qualified healthcare professional 
  for diagnosis, treatment, or medical concerns.
  ```
- **Applies To**: Every response from the chatbot

## System Architecture

### Query Processing Pipeline

```
User Query
    ↓
Step 0: EMERGENCY SYMPTOMS CHECK ← NEW HIGHEST PRIORITY
    ├─ If emergency detected → Immediate alert to seek medical care
    ├─ Return emergency response with hospital routing
    └─ Continue normal flow if not emergency
    ↓
Step 1: Query Normalization
    ├─ Fix typos in medical terms
    ├─ Fix system name variations
    └─ Clean query text
    ↓
Step 2: Medical Query Validation
    ├─ Check if query is medical in nature
    └─ Reject if non-medical topic
    ↓
Step 3: Intent Classification
    ├─ code_only: User wants medical codes
    ├─ medication_only: User wants medication information
    ├─ symptoms_only: User wants symptom information
    ├─ treatment_only: User wants treatment information
    └─ explain: User wants general explanation
    ↓
Step 4: Local Database Search
    ├─ Search ICD-10, LOINC, RxNorm, SNOMED CT
    └─ Return top matching codes with relevance scores
    ↓
Step 5: LLM Enhancement (Arcee AI)
    ├─ Send prompt with strict instructions
    ├─ Ensure simple language
    ├─ Add safety notes
    └─ Return verified, contextualized response
    ↓
Final Response with Disclaimer
```

### Emergency Detection Examples

**Detected as Emergency:**
- "severe chest pain"
- "can't breathe / severe breathing difficulty"
- "sudden paralysis on one side"
- "stiff neck with high fever"
- "severe uncontrolled bleeding"
- "severe allergic reaction / anaphylaxis"
- "loss of consciousness"

**Response for Emergency:**
```
🚨 MEDICAL EMERGENCY DETECTED
Your symptoms suggest: [emergency type]

SEEK IMMEDIATE MEDICAL HELP:
• Call emergency number (911/999/112)
• Go to nearest hospital emergency room
• Do NOT wait
```

## Code Changes Summary

### app.py
- Added emergency response handling in `/search` route
- Emergency responses return `status: "emergency"` with urgent care instructions

### engine/search.py
- Added `EMERGENCY_SYMPTOMS` dictionary with regex patterns for dangerous symptoms
- Added `_detect_emergency_symptoms()` function (highest priority check)
- Updated all LLM prompts with:
  - Preamble enforcing guidelines (simple language, no diagnosis, no jargon)
  - Emoji-based response structure
  - Enhanced safety notes
- Modified `hybrid_medical_search()` to check for emergencies first
- Enhanced prompts for each intent category to ensure guideline compliance

## Key Functions

### Emergency Detection
```python
def _detect_emergency_symptoms(query: str) -> Optional[str]
```
- Detects dangerous symptoms from user query
- Returns description of detected emergency or None
- Highest priority check in processing pipeline

### Intent Detection
```python
def _detect_intent(query: str) -> str
```
- Classifies what user is asking for
- Returns: 'code_only', 'medication_only', 'symptoms_only', 'treatment_only', 'explain', 'full'

### Condition Extraction
```python
def _extract_condition(query: str) -> str
```
- Extracts medical condition/drug name from natural language query
- Handles aliases and variations (e.g., "high blood pressure" → "hypertension")

### Dynamic Prompt Building
```python
def _dynamic_prompt(intent: str, condition: str, query: str, ...) -> tuple
```
- Builds intent-specific prompt with all guidelines enforced
- Returns (prompt_text, max_tokens)
- Each intent gets appropriate instructions and structure

## Testing the Implementation

### Test Emergency Detection
```python
queries = [
    "I have severe chest pain",
    "I can't breathe, help!",
    "stiff neck and high fever",
    "sudden paralysis on my left side",
]
```
All should trigger emergency response.

### Test Simple Language
Submit any query and verify response:
- Uses common words, not medical jargon
- Explains complex terms if used
- Structured with emojis
- Clear, easy to understand

### Test No Diagnosis
Try queries like:
- "I have fever and headache"
- "What could cause my symptoms?"
Verify system explains **possible causes** not specific diagnosis.

### Test Guidelines Enforcement
Check that responses:
1. ✅ Answer what was asked (no follow-up questions)
2. ✅ Use simple language
3. ✅ Include disclaimer
4. ✅ Don't diagnose
5. ✅ Don't mention internal systems
6. ✅ Provide medical code information when relevant
7. ✅ Structure responses clearly

## Future Enhancements

1. **Expanded Emergency Symptoms**: Add more specialized emergency patterns
2. **Multilingual Support**: Extend guidelines to multiple languages
3. **User Feedback**: Track which responses were helpful
4. **Personalization**: Adapt language complexity based on user profile
5. **Citation System**: Enhanced tracking of information sources
6. **Accessibility**: Better support for screen readers and various interfaces

## Compliance Checklist

- ✅ Understand user questions regardless of grammar
- ✅ Respond in simple language
- ✅ Never ask follow-up questions
- ✅ Never diagnose diseases
- ✅ Detect dangerous symptoms and recommend urgent care
- ✅ Structure responses clearly with emoji sections
- ✅ Provide medical code information for relevant systems
- ✅ Avoid medical jargon
- ✅ Don't mention internal system details
- ✅ Always include safety disclaimers
- ✅ Emergency detection as highest priority

All guidelines from the specification have been implemented and integrated into the chatbot system.
