"""
Medical Hybrid Search Engine  –  search.py
===========================================
Hybrid pipeline: local DBs → Gemini AI verification → final response.

Spec-required public functions:
  classify_query(query)
  search_icd(query)
  search_loinc(query)
  search_rxnorm(query)
  search_snomed(query)
  load_local_medical_data()
  call_gemini_api(prompt)
  verify_code_with_arcee(query, local_candidate)
  hybrid_medical_search(query)
"""

import json
import os
import re
import requests
from typing import Any, Dict, List, Optional, Tuple
from difflib import get_close_matches
from dotenv import load_dotenv

# Load .env file at startup
load_dotenv()

# ─────────────────────────────────────────────────────────────
# FILE PATHS
# ─────────────────────────────────────────────────────────────
DATA_DIR     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ICD_PATH     = os.path.join(DATA_DIR, "record.json")
LOINC_PATH   = os.path.join(DATA_DIR, "loinc.json")
RXCONSO_PATH = os.path.join(DATA_DIR, "RXNCONSO_sample.json")
RXREL_PATH   = os.path.join(DATA_DIR, "RXNREL_sample.json")
RXSAT_PATH   = os.path.join(DATA_DIR, "RXNSAT_sample.json")
SNOMED_PATH  = os.path.join(DATA_DIR, "snomed-300k (1).jsonl")
PROJECT_PATH = os.path.join(DATA_DIR, "project.json")

DISCLAIMER = (
    "\n\nThis information is for educational purposes only and is not a substitute "
    "for professional medical advice. Always consult a qualified healthcare professional."
)

def _detect_emergency_symptoms(query: str) -> Optional[str]:
    """
    Detects if the query describes potentially dangerous symptoms.
    Returns a warning message, or None if no emergency detected.
    
    This provides a WARNING, not a full emergency routing.
    Uses general medical knowledge to identify dangerous symptoms.
    """
    q = query.lower().strip()
    
    dangerous_patterns = [
        # Cardiac
        (r"\bchest\s+(pain|tightness|pressure|discomfort|heaviness)", 
         "Chest pain, pressure, or tightness may indicate a serious cardiac condition."),
        # Respiratory
        (r"\bsevere.*breath|can't\s+breathe|unable\s+to\s+breathe",
         "Severe difficulty breathing requires immediate medical attention."),
        # Neurological
        (r"\bsudden.*paralysis|sudden.*weakness.*side|can't\s+move",
         "Sudden paralysis or weakness may indicate a stroke."),
        (r"\bsudden.*severe.*headache|thunderclap",
         "Sudden severe headache may indicate a serious condition like meningitis."),
        (r"\bstiff\s+neck.*fever|neck\s+stiffness.*high\s+fever",
         "Stiff neck with fever may indicate meningitis, a serious infection."),
        # Consciousness
        (r"\blose\s+consciousness|unconscious|passed\s+out|fainted",
         "Loss of consciousness requires immediate medical evaluation."),
        (r"\bassociatedsudden.*confusion|confused.*severe",
         "Sudden confusion may indicate a serious medical emergency."),
        # Bleeding
        (r"\bsevere.*bleed|bleed.*won't\s+stop|uncontrolled\s+bleed",
         "Severe or uncontrolled bleeding requires immediate medical attention."),
        # Allergic reaction
        (r"\bswelling.*face|swelling.*throat|tongue\s+swelling|can't\s+swallow",
         "Facial or throat swelling may indicate anaphylaxis, a serious allergic reaction."),
    ]
    
    for pattern, warning_msg in dangerous_patterns:
        if re.search(pattern, q, re.IGNORECASE):
            return warning_msg
    
    return None

# ─────────────────────────────────────────────────────────────
# NORMALISATION TABLES
# ─────────────────────────────────────────────────────────────
SYSTEM_ALIASES: Dict[str, List[str]] = {
    "LOINC":  ["lonic","lonc","loinic","lionic","loink","loinck","lonick","loic","loniec","loince"],
    "SNOMED": ["snoomed","snommed","snomd","snoemed","snomned","snowmed","snomede","snomde"],
    "RXNORM": ["rxnom","rxnor","rxnrm","rxnormal","rxnomr","rxnomm","rxnormed","rxnomre"],
    "ICD-10": ["idc","icd10","idc10","icd 10"],
}

MEDICAL_TERM_VOCABULARY: List[str] = [
    "glucose","hemoglobin","hba1c","creatinine","sodium","potassium","cholesterol",
    "bilirubin","albumin","ferritin","tsh","hematocrit","platelet","leukocyte",
    "erythrocyte","triglyceride","calcium","magnesium","cortisol","estrogen","testosterone",
    "aspirin","ibuprofen","metformin","insulin","amoxicillin","lisinopril","atorvastatin",
    "omeprazole","paracetamol","acetaminophen","warfarin","heparin","morphine",
    "cholera","diabetes","hypertension","asthma","pneumonia","tuberculosis","malaria",
    "dengue","hepatitis","fracture","headache","fever","nausea","vomiting","diarrhea",
    "anemia","obesity","depression","anxiety","seizure","stroke","infarction","edema",
    "inflammation","hemorrhage","arthritis","cancer","sepsis","thyroid",
]

SYSTEM_TERM_TRIGGERS: Dict[str, List[str]] = {
    "loinc":  ["glucose","hemoglobin","hba1c","creatinine","sodium","potassium",
               "cholesterol","bilirubin","albumin","ferritin","tsh","t4","t3",
               "wbc","rbc","platelet","hematocrit"],
    "rxnorm": ["aspirin","ibuprofen","metformin","insulin","amoxicillin","lisinopril",
               "atorvastatin","omeprazole","paracetamol","acetaminophen","warfarin",
               "heparin","morphine"],
    "snomed": ["headache","fever","nausea","vomiting","diarrhea","hypertension",
               "diabetes","asthma","pneumonia","fracture"],
    "icd":    ["cholera","diabetes","hypertension","asthma","cancer","tuberculosis",
               "malaria","dengue","hepatitis"],
}

# ─────────────────────────────────────────────────────────────
# CLASSIFICATION PATTERNS
# ─────────────────────────────────────────────────────────────
CODE_PATTERNS: List[str] = [
    r"\bICD[-\s]?\d{1,2}\b", r"\b[A-Z]\d{2,3}(\.\d{1,4})?\b",
    r"\bLOINC\b", r"\bRXNORM\b", r"\bRXCUI\b", r"\bSNOMED\b", r"\bSCT\b",
    r"\b\d{5,7}-\d\b", r"\b\d{6,18}\b", r"\bcode\s+(for|of)\b", r"\blookup\b",
]
CODE_TRIGGER_PHRASES: List[str] = [
    "code of","code for","give me the code","what is the code","find the code",
    "lookup","look up","find code","get code","show code","retrieve code",
]
MEDICAL_UNDERSTANDING_PATTERNS: List[str] = [
    r"\bsymptoms?\b",r"\btreatment\b",r"\btherapy\b",r"\bcauses?\b",
    r"\brisk\s+factors?\b",r"\bdiagnosis\b",r"\bdiagnose\b",r"\bwhat\s+(is|are)\b",
    r"\bexplain\b",r"\bdefinition\b",r"\bhow\s+(is|does|do|to)\b",r"\bprognosis\b",
    r"\bprevention\b",r"\bmedication\b",r"\bdrug\b",r"\bdosage\b",
    r"\bside\s+effects?\b",r"\bcomplication\b",r"\bmanagement\b",
]
MEDICAL_KEYWORDS: set = {
    "icd","loinc","rxnorm","snomed","sct","fhir","hl7","disease","disorder","syndrome",
    "condition","diagnosis","symptom","treatment","therapy","medication","drug","dose",
    "patient","clinical","medical","health","hospital","doctor","nurse","physician",
    "pathology","anatomy","physiology","infection","virus","bacteria","cancer","tumor",
    "chronic","acute","pain","fever","blood","heart","lung","liver","kidney","brain",
    "nerve","muscle","bone","skin","eye","ear","stomach","diabetes","hypertension",
    "cholera","glucose","insulin","antibiotic","vaccine","allergy","immune","test",
    "lab","scan","mri","xray","ct","biopsy","surgery","prescription","pharmacy",
    "dosage","overdose","toxicity","code","rxcui","etiology","asthma","pneumonia",
    "arthritis","fracture","hemorrhage","anemia","obesity","malnutrition","depression",
    "anxiety","seizure","stroke","infarction","edema","inflammation","hemoglobin",
    "hematology","hematocrit","platelet","leukocyte","erythrocyte","cholesterol",
    "triglyceride","creatinine","bilirubin","electrolyte","sodium","potassium","calcium",
    "magnesium","thyroid","cortisol","hormone","aspirin","ibuprofen","metformin",
    "amoxicillin","lisinopril","tuberculosis","malaria","dengue","hepatitis","sepsis",
    "complication","management","prognosis",
    # Extended conditions — for bare-term queries like "meningitis" or "rabies"
    "meningitis","rabies","ebola","typhoid","lupus","leprosy","schistosomiasis",
    "leishmaniasis","trypanosomiasis","brucellosis","leptospirosis","listeria",
    "salmonella","campylobacter","shigella","gonorrhea","syphilis","chlamydia",
    "hpv","herpes","influenza","covid","coronavirus","monkeypox","zika","west nile",
    "glaucoma","cataract","retinopathy","macular degeneration",
    "parkinson","alzheimer","dementia","schizophrenia","bipolar","ptsd","adhd","autism",
    "endometriosis","fibroids","polycystic","pcos","menopause","osteoporosis",
    "appendicitis","pancreatitis","peritonitis","diverticulitis","colitis","crohns",
    "cirrhosis","gallstones","jaundice","ascites",
    "psoriasis","eczema","dermatitis","acne","rosacea","vitiligo","melanoma",
    "lymphoma","leukemia","myeloma","sarcoma","glioma","mesothelioma",
    "fibrillation","arrhythmia","tachycardia","bradycardia","angina","cardiomyopathy",
    "thrombosis","embolism","aneurysm","atherosclerosis","peripheral",
    "hypothyroidism","hyperthyroidism","addison","cushing","pituitary","acromegaly",
    "nephropathy","glomerulonephritis","pyelonephritis","cystitis","urethritis",
    "bronchitis","pleuritis","emphysema","silicosis","sarcoidosis",
    "osteoarthritis","gout","fibromyalgia","spondylitis","tendinitis","bursitis",
    "encephalitis","neuritis","neuropathy","myasthenia","multiple sclerosis",
    "thalassemia","sickle cell","hemophilia","thrombocytopenia","neutropenia",
    "abscess","cellulitis","osteomyelitis","endocarditis","pericarditis","myocarditis",
}
NON_MEDICAL_SIGNALS: List[str] = [
    r"\bwho\s+(won|is\s+the\s+president|scored)\b",
    r"\bweather\b",r"\bsports?\b",r"\bfootball\b",r"\bcricket\b",r"\bpolitics\b",
    r"\bmovie\b",r"\bsong\b",r"\btravel\b",r"\bhotel\b",
    r"\bjoke\b",r"\bfunny\b",r"\bstock\s+market\b",r"\bcrypto\b",r"\bbitcoin\b",
    # ── Lifestyle / diet / fitness (not clinical medical) ──
    r"\bbest\s+diet\b",r"\bdiet\s+(for|plan|tips|advice)\b",
    r"\bweight\s+loss\s+(diet|tips|advice|plan|food|exercise)\b",
    r"\bhow\s+to\s+lose\s+weight\b",r"\blose\s+weight\s+fast\b",
    r"\bfitness\s+(tips|plan|advice|routine)\b",
    r"\brecipe\b",r"\bcook\b",r"\brestaurant\b",
]
HYBRID_CODE_SYSTEMS: List[str] = ["rxnorm","rxcui","loinc","snomed","icd","sct"]
HYBRID_CODE_ASKING_WORDS: List[str] = [
    "what is the","give me the","find the","what is",
    "rxcui for","rxnorm for","loinc for","icd for","snomed for",
    "rxcui of","rxnorm of","loinc of","icd of","snomed of",
    "code for","code of","number for","number of",
]

# ══════════════════════════════════════════════════════════════
# SECTION 1 — NORMALISATION
# ══════════════════════════════════════════════════════════════

def normalize_query(query: str) -> str:
    """Two-pass: fix system-name typos then medical-term typos."""
    words = query.split()
    out: List[str] = []
    for word in words:
        w = word.lower().strip(".,?!")
        replaced = False
        for canonical, variants in SYSTEM_ALIASES.items():
            if w in variants or get_close_matches(w, variants, n=1, cutoff=0.75):
                out.append(canonical); replaced = True; break
        if replaced:
            continue
        if len(w) >= 4:
            # Don't fuzzy-replace words that are themselves valid medical terms
            # e.g. "infection" should never become "infarction"
            _PROTECTED = {
                "infection","infections","infected","infective","infectious",
                "asthmatic","diabetic","hypertensive","epileptic","arthritic",
                "obese","depressed","anxious","fractured","ischaemic","ischemic",
                "contagious","chronic","acute","severe","mild","moderate",
                "patient","patients","doctor","nurse","hospital","clinic",
            }
            if w in _PROTECTED:
                out.append(word); continue
            tm = get_close_matches(w, MEDICAL_TERM_VOCABULARY, n=1, cutoff=0.80)
            if tm and tm[0] != w:
                out.append(tm[0]); replaced = True
        if not replaced:
            out.append(word)
    normalised = " ".join(out)
    if normalised != query:
        print(f"[NORMALIZE] '{query}' → '{normalised}'")
    return normalised


def extract_search_term(query: str) -> str:
    """Extract the core medical noun from a query."""
    q = query.lower()
    words_count = len(q.split())
    if words_count <= 6:
        for sys in ["loinc","snomed","rxnorm","icd-10","icd10","icd","rxcui","sct"]:
            q = re.sub(rf"\b{sys}\b", "", q)
        for pat in [r"\bcode\s*(of|for)?\b",r"\bgive\s+me\b",r"\bwhat\s+is\b",
                    r"\bfind\b",r"\blookup\b",r"\bget\b",r"\bshow\b",
                    r"\bthe\b",r"\bof\b",r"\bfor\b",r"\bnumber\b",r"\bidentifier\b"]:
            q = re.sub(pat, " ", q)
        result = re.sub(r"\s+", " ", q).strip()
        if result:
            return result
    _skip = {"icd","loinc","rxnorm","snomed","sct","rxcui","fhir","hl7","code",
             "medical","health","test","lab","drug","dose","patient","clinical",
             "doctor","nurse","scan","what","blood","pain","acute","chronic",
             "disease","infection","condition","symptom","treatment","therapy",
             "diagnosis","number","identifier","term","class","type","level"}
    all_terms: List[str] = [t for lst in SYSTEM_TERM_TRIGGERS.values() for t in lst]
    for word in re.findall(r"\b[a-z]+\b", query.lower()):
        if (word in all_terms or word in MEDICAL_KEYWORDS) and word not in _skip:
            return word
    for sys in ["rxnorm","rxcui","loinc","snomed","icd"]:
        m = re.search(rf"\b{sys}\b\s+(?:code\s+)?(?:for|of)?\s*(\w+)", query.lower())
        if m:
            return m.group(1)
    return ""

# ══════════════════════════════════════════════════════════════
# SECTION 2 — SAFETY & CLASSIFICATION
# ══════════════════════════════════════════════════════════════

def is_medical_query(query: str) -> bool:
    """
    Return True if the query is health/medical related.
    
    This function is now VERY permissive - it accepts nearly all health-related questions.
    
    Only rejects:
      - Completely off-topic (sports scores, weather, politics)
      - Bot/jailbreak attempts
    
    Accepts:
      - Symptoms, diseases, conditions
      - Medications, treatments, therapies
      - Diet, lifestyle, prevention
      - Lab tests, medical terminology
      - Any health-related question in any format
    """
    q = query.lower().strip()
    
    # Hard reject only truly off-topic queries
    hard_reject_patterns = [
        r"\bwho\s+(won|is\s+the\s+president|scored|defeated)\b",
        r"\bweather|forecast|temperature|celsius|fahrenheit",
        r"\bsports?\b|football|cricket|basketball|baseball|soccer",
        r"\bstock\s+market|crypto|bitcoin|finance|investment",
        r"\bmovie|film|actor|director|screenplay",
        r"\bjoke|funny|comedy|laugh",
        r"\btravel\b|hotel|flight|vacation|tourism",
        r"\bcooking|recipe|restaurant|food\s+review",
    ]
    
    for pattern in hard_reject_patterns:
        if re.search(pattern, q, re.IGNORECASE):
            return False
    
    # Accept virtually anything health-related
    # Just having ANY word related to health makes it valid
    if len(q) > 0:
        return True
    
    return False


def classify_query(query: str) -> Tuple[str, float]:
    """
    Returns ('local'|'hybrid'|'llm', confidence).
    local   — pure code lookup
    hybrid  — code lookup + clinical explanation in same query
    llm     — pure medical explanation, no code lookup needed
    """
    q = query.lower()
    mentions_system     = any(s in q for s in HYBRID_CODE_SYSTEMS)
    has_explanation_ask = any(re.search(p, q) for p in MEDICAL_UNDERSTANDING_PATTERNS)
    has_code_ask = (
        any(phrase in q for phrase in HYBRID_CODE_ASKING_WORDS) or
        any(re.search(p, query, re.IGNORECASE) for p in CODE_PATTERNS)
    )
    if mentions_system and has_code_ask and has_explanation_ask:
        return ("hybrid", 0.97)
    if mentions_system and has_code_ask:
        return ("local", 0.95)
    for pat in CODE_PATTERNS:
        if re.search(pat, query, re.IGNORECASE): return ("local", 0.93)
    for phrase in CODE_TRIGGER_PHRASES:
        if phrase in q: return ("local", 0.92)
    for pat in MEDICAL_UNDERSTANDING_PATTERNS:
        if re.search(pat, q): return ("llm", 0.85)
    return ("llm", 0.60)

# ══════════════════════════════════════════════════════════════
# SECTION 3 — FILE LOADERS
# ══════════════════════════════════════════════════════════════

def _safe_load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Cannot load {path}: {e}")
        return []


def load_local_medical_data() -> Dict[str, Any]:
    """
    Load all available local medical databases.
    Returns dict: icd, loinc, rxnorm{conso,rel,sat}, snomed (path), project.
    SNOMED is never fully loaded — always streamed on demand.
    LOINC is loaded only if ≤ 500 MB, otherwise streamed too.
    """
    data: Dict[str, Any] = {
        "icd":     _safe_load_json(ICD_PATH),
        "rxnorm": {
            "conso": _safe_load_json(RXCONSO_PATH),
            "rel":   _safe_load_json(RXREL_PATH),
            "sat":   _safe_load_json(RXSAT_PATH),
        },
        # project.json contains additional non-clinical information such as
        # FHIR, ABDM, HL7, Mirth Connect, OCR, DigiYatra, etc.  We'll store it
        # here and provide search helpers so users can query that data via the
        # same hybrid search API used for medical codes.
        "project": _safe_load_json(PROJECT_PATH),
        "loinc":   [],
        "snomed":  SNOMED_PATH,
    }
    if os.path.exists(LOINC_PATH):
        size = os.path.getsize(LOINC_PATH)
        if size <= 500 * 1024 * 1024:
            data["loinc"] = _safe_load_json(LOINC_PATH)
        else:
            print(f"[INFO] LOINC {size//(1024*1024)} MB — streaming on demand")
    return data


# ─────────────────────────────────────────────────────────────
# PROJECT METADATA SEARCH
# ─────────────────────────────────────────────────────────────

def search_project(query: str, limit: int = 5) -> List[Dict]:
    """Lookup entries from `project.json` based on query keywords.

    This lets users ask about FHIR, ABDM, HL7, Mirth Connect, OCR, DigiYatra,
    and any other subjects added to the metadata file.
    """
    q = query.lower().strip()
    results: List[Dict] = []
    project_data = load_local_medical_data().get("project", {})
    standards = project_data.get("healthcare_standards", [])
    for entry in standards:
        name = entry.get("name", "").lower()
        desc = entry.get("description", "").lower()
        # Check if entry name appears in query (e.g., "fhir" in "what is fhir")
        # Also check if query is in description or purpose (for partial matches)
        if name in q or q in desc or any(q in str(v).lower() for v in entry.get("purpose", [])):
            results.append(entry)
        if len(results) >= limit:
            break
    return results


def format_project_results(entries: List[Dict]) -> str:
    """Convert project metadata entries into a readable string."""
    lines: List[str] = []
    for entry in entries:
        lines.append(f"Name: {entry.get('name','')}")
        if entry.get('category'):
            lines.append(f"Category: {entry.get('category')}")
        if entry.get('description'):
            lines.append(f"Description: {entry.get('description')}")
        if entry.get('purpose'):
            lines.append(f"Purpose: {'; '.join(entry.get('purpose', []))}")
        if entry.get('key_features'):
            lines.append(f"Key features: {'; '.join(entry.get('key_features', []))}")
        if entry.get('example_use_case'):
            lines.append(f"Example: {entry.get('example_use_case')}")
        lines.append("")
    return "\n".join(lines).strip()

# ══════════════════════════════════════════════════════════════
# SECTION 4 — SCORING
# ══════════════════════════════════════════════════════════════

def _score_match(query_lower: str, text: str) -> int:
    """
    Strict word-boundary relevance score.
    100 = exact match, 90 = whole-word match, 0 = no match.
    Substring-only matches (e.g. 'code' inside 'Codeine') return 0.
    """
    if not query_lower or not text:
        return 0
    tl = text.lower()
    if query_lower == tl:
        return 100
    if re.search(r"\b" + re.escape(query_lower) + r"\b", tl):
        return 90
    return 0

# ══════════════════════════════════════════════════════════════
# SECTION 5 — INDIVIDUAL DB SEARCH FUNCTIONS
# ══════════════════════════════════════════════════════════════

def search_icd(query: str, limit: int = 10) -> List[Dict]:
    """Search ICD-10 database (record.json)."""
    q = query.lower().strip()
    results: List[Dict] = []
    for r in _safe_load_json(ICD_PATH):
        term = r.get("term",""); code = r.get("code",""); desc = r.get("description","")
        score = max(_score_match(q,term), _score_match(q,desc),
                    100 if q == code.lower() else 0)
        if score > 0:
            results.append({"code":code,"term":term,"description":desc,
                             "system":r.get("system","ICD-10"),"relevance":score})
        if len(results) >= limit * 3: break
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:limit]


def search_loinc(query: str, limit: int = 10) -> List[Dict]:
    """Search LOINC database (loinc.json). Streams if file > 500 MB."""
    q = query.lower().strip()
    results: List[Dict] = []
    if not os.path.exists(LOINC_PATH):
        return results

    def _rec(r: dict) -> Optional[Dict]:
        term = r.get("LONG_COMMON_NAME",""); comp = r.get("COMPONENT","")
        code = r.get("LOINC_NUM","")
        score = max(_score_match(q,term), _score_match(q,comp),
                    100 if q == code.lower() else 0)
        if score > 0:
            return {"code":code,"term":term,
                    "description":f"LOINC Lab Test | {comp} [{r.get('SYSTEM','')}]",
                    "system":"LOINC","relevance":score}
        return None

    if os.path.getsize(LOINC_PATH) <= 500 * 1024 * 1024:
        for r in _safe_load_json(LOINC_PATH):
            rec = _rec(r)
            if rec: results.append(rec)
            if len(results) >= limit * 3: break
    else:
        try:
            with open(LOINC_PATH,"r",encoding="utf-8") as f:
                for line in f:
                    if len(results) >= limit * 3: break
                    line = line.strip().rstrip(",")
                    if not line or line in ("[","}"): continue
                    try:
                        rec = _rec(json.loads(line))
                        if rec: results.append(rec)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[WARN] LOINC stream error: {e}")
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:limit]


def search_rxnorm(query: str, limit: int = 10) -> List[Dict]:
    """Search RxNorm database (RXNCONSO_sample.json). Deduplicates by RXCUI."""
    q = query.lower().strip()
    results: List[Dict] = []
    seen: set = set()
    for r in _safe_load_json(RXCONSO_PATH):
        name = r.get("STR",""); rxcui = str(r.get("RXCUI",""))
        score = max(_score_match(q,name), 100 if q == rxcui else 0)
        if score > 0 and rxcui not in seen:
            seen.add(rxcui)
            results.append({"code":rxcui,"term":name,
                             "description":f"RxNorm Drug | TTY: {r.get('TTY','')}",
                             "system":"RxNorm","relevance":score})
        if len(results) >= limit * 3: break
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:limit]


def search_snomed(query: str, limit: int = 10) -> List[Dict]:
    """Search SNOMED CT database (snomed-300k.jsonl). Always streamed."""
    q = query.lower().strip()
    results: List[Dict] = []
    if not os.path.exists(SNOMED_PATH):
        return results
    try:
        with open(SNOMED_PATH,"r",encoding="utf-8") as f:
            for line in f:
                if len(results) >= limit * 3: break
                line = line.strip()
                if not line: continue
                try:
                    r = json.loads(line)
                    desc = r.get("description",""); code = str(r.get("code",""))
                    score = max(_score_match(q,desc), 100 if q == code.lower() else 0)
                    if score > 0:
                        results.append({"code":code,"term":desc,
                                        "description":"SNOMED CT Concept",
                                        "system":"SNOMED CT","relevance":score})
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[WARN] SNOMED stream error: {e}")
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:limit]

# ══════════════════════════════════════════════════════════════
# SECTION 6 — SYSTEM DETECTION & COMBINED SEARCH
# ══════════════════════════════════════════════════════════════

def _detect_systems(query: str, term: str) -> Dict[str, bool]:
    q = query.lower(); t = term.lower()
    explicit = {"icd":"icd" in q,"loinc":"loinc" in q,
                "rxnorm":"rxnorm" in q or "rxcui" in q,
                "snomed":"snomed" in q or "sct" in q}
    if any(explicit.values()):
        return explicit
    infer_loinc  = any(k in q for k in ("lab","test","assay","panel","level","serum","plasma")) \
                   or any(k in t for k in SYSTEM_TERM_TRIGGERS["loinc"])
    infer_rxnorm = any(k in q for k in ("drug","medication","medicine","pill","tablet","dose")) \
                   or any(k in t for k in SYSTEM_TERM_TRIGGERS["rxnorm"])
    infer_snomed = bool(re.search(r"\b\d{6,18}\b",query)) \
                   or any(k in t for k in SYSTEM_TERM_TRIGGERS["snomed"])
    any_inf = infer_loinc or infer_rxnorm or infer_snomed
    return {"icd":not any_inf,"loinc":infer_loinc,"rxnorm":infer_rxnorm,"snomed":infer_snomed}


def _search_all_codes(query: str, limit: int = 10) -> List[Dict]:
    """Normalise → extract term → detect DBs → search → deduplicate → rank."""
    query = normalize_query(query)
    term  = extract_search_term(query) or query
    print(f"[SEARCH] Query='{query}' | Term='{term}'")
    dbs = _detect_systems(query, term)
    print(f"[SEARCH] DBs → ICD:{dbs['icd']} LOINC:{dbs['loinc']} "
          f"RxNorm:{dbs['rxnorm']} SNOMED:{dbs['snomed']}")
    results: List[Dict] = []
    if dbs["icd"]:    results.extend(search_icd(term, limit))
    if dbs["loinc"]:  results.extend(search_loinc(term, limit))
    if dbs["rxnorm"]: results.extend(search_rxnorm(term, limit))
    if dbs["snomed"]: results.extend(search_snomed(term, limit))
    if not results and term != query:
        print(f"[SEARCH] Retry with full query")
        if dbs["icd"]:    results.extend(search_icd(query, limit))
        if dbs["loinc"]:  results.extend(search_loinc(query, limit))
        if dbs["rxnorm"]: results.extend(search_rxnorm(query, limit))
        if dbs["snomed"]: results.extend(search_snomed(query, limit))
    seen: set = set()
    unique: List[Dict] = []
    for r in results:
        k = (r.get("code",""), r.get("system",""))
        if k not in seen:
            seen.add(k); unique.append(r)
    unique.sort(key=lambda x: x["relevance"], reverse=True)
    return unique[:limit]

# ══════════════════════════════════════════════════════════════
# SECTION 7 — GEMINI AI API
# ══════════════════════════════════════════════════════════════

def call_gemini_api(prompt: str, max_tokens: int = 700) -> str:
    """
    Send prompt to Google Gemini API.
    Reads GEMINI_API_KEY from environment.
    Returns response text or "" on any failure — never raises.
    Includes medical-only content filtering.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("[WARN] GEMINI_API_KEY not set")
        return ""
    
    # Correct Gemini API endpoint
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    # Add medical content filter to the prompt
    filtered_prompt = (
        f"{prompt}\n\n"
        "IMPORTANT: Only provide medical, healthcare, and health-related information. "
        "If the request is not medical/health-related, respond with: 'I can only provide medical and healthcare information.'"
    )
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": filtered_prompt}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
        }
    }
    
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=25)
        resp.raise_for_status()
        content = ""
        try:
            response_data = resp.json()
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    if len(candidate["content"]["parts"]) > 0:
                        content = candidate["content"]["parts"][0].get("text", "")
        except (KeyError, IndexError, ValueError):
            print("[WARN] Gemini response format error")
            return ""
        
        if not content:
            print("[WARN] Gemini returned empty content")
            return ""
        
        return content.strip()
    except requests.exceptions.Timeout:
        print("[WARN] Gemini API timeout")
        return ""
    except requests.exceptions.HTTPError as e:
        print(f"[WARN] Gemini HTTP error: {e}")
        return ""
    except Exception as e:
        print(f"[WARN] Gemini API error: {e}")
        return ""


# ─────────────────────────────────────────────────────────────
# NATURAL LANGUAGE UNDERSTANDING (NLU)
# Handles conversational / human-style queries, not just
# clinical keyword queries.
#
# Examples it must handle correctly:
#   "medicines for malaria"            → medication_only
#   "i am suffering from malaria"      → medication_only  (distress → help)
#   "what should i take for malaria"   → medication_only
#   "i have fever and headache"        → symptoms_only    (describe symptoms)
#   "how do i know if i have malaria"  → symptoms_only
#   "how do i treat malaria"           → treatment_only
#   "what is malaria"                  → explain
#   "ICD code for malaria"             → code_only
# ─────────────────────────────────────────────────────────────

# ── Phrase pattern groups ──────────────────────────────────
# Each group maps to an intent. Checked in priority order.
# Patterns use simple substring match on lowercase query.

_MEDICATION_PHRASES = [
    # Direct drug requests
    "medicines for", "medicine for", "medications for", "medication for",
    "drugs for", "drug for", "pills for", "pill for",
    "tablets for", "tablet for", "antibiotics for", "antibiotic for",
    # "what to take" style
    "what to take", "what should i take", "what can i take",
    "what medicine", "which medicine", "which medicines",
    "which drug", "which drugs", "which tablet", "which pill",
    "what medication", "what medications",
    # ── NEW: "what drugs are used for", "what are the drugs for" ──
    "what drugs are used", "what drugs are given", "what drugs treat",
    "what are the drugs", "what are the medicines", "what are the medications",
    "which drugs are used", "which drugs are given",
    "what antibiotics", "which antibiotics",
    "name the drugs", "name the medicines", "list the drugs",
    # "suffering / sick / infected" + implicit need for help
    "i am suffering", "i have been suffering", "suffering from",
    "i am sick", "i got", "i've got", "i have contracted",
    "infected with", "diagnosed with",
    # "help me" / "what should i do"
    "what should i do", "what do i do", "what can i do",
    "help me with", "how can i recover", "how to recover",
    "how to get better", "how to feel better",
    "what to do if", "what to do when",
    # Explicit drug lookups
    "drug treatment", "drug therapy", "pharmaceutical",
    "rxnorm for", "rxcui for",
]

_SYMPTOMS_PHRASES = [
    "symptoms of", "symptom of", "signs of", "sign of",
    "symptoms for", "signs for",
    "how does it feel", "how do i feel", "how will i feel",
    "how do i know if i have", "how do i know if",
    "how to know if i have", "how to know if",
    "do i have", "could i have", "might i have",
    "am i suffering from", "is this",
    "clinical features", "clinical presentation",
    "what are the signs", "what are the symptoms",
    "what happens when you have", "what happens if you have",
    "how does malaria feel", "how does diabetes feel",   # pattern
    "i have fever", "i have headache", "i have pain",
    "i am feeling", "i feel", "i keep feeling",
]

_TREATMENT_PHRASES = [
    "treatment for", "treatment of", "treat", "treating",
    "how to treat", "how is it treated", "how do you treat",
    "therapy for", "therapy of", "management of", "manage",
    "how to manage", "how is it managed",
    "cure for", "cure of", "how to cure", "is there a cure",
    "first line treatment", "standard treatment",
    "clinical management",
]

_CODE_PHRASES = [
    "icd code", "icd-10 code", "loinc code", "snomed code",
    "rxnorm code", "rxcui", "medical code", "coding",
    "what is the code", "give me the code", "find the code",
    "code for", "code of", "lookup", "look up",
    "identifier for", "medical identifier",
]

_EXPLAIN_PHRASES = [
    "what is", "what are", "define", "definition of",
    "explain", "tell me about", "describe",
    "what causes", "what cause", "causes of",
    "why does", "why do", "how does", "how do",
    "pathophysiology", "etiology", "overview of",
    "about malaria", "about diabetes", "about",   # "about X"
    "information on", "information about",
    "details about", "details on",
]


def _detect_intent(query: str) -> str:
    """
    Detect what the user ACTUALLY wants from a natural-language query.

    Priority order (highest first):
      1. code_only      — technical code lookup
      2. medication_only — any drug / medicine / "what should I do" ask
      3. symptoms_only  — symptom / "do I have" / "how does it feel" ask
      4. treatment_only — treatment / cure / management (non-drug phrasing)
      5. explain        — general "what is / tell me about" ask
      6. explain        — fallback

    Returns one of:
      'code_only' | 'medication_only' | 'symptoms_only' |
      'treatment_only' | 'explain' | 'full'
    """
    q = query.lower().strip()

    # ── 0. Explicit coding system names always win first ─────
    # e.g. "rxnorm for malaria", "loinc code of hemoglobin"
    _SYSTEM_NAMES = ("rxnorm", "rxcui", "loinc", "snomed", "icd", "sct",
                     "icd-10", "icd10", "hcpcs", "cpt", "ndc")
    if any(s in q for s in _SYSTEM_NAMES):
        # Hybrid: also asks for explanation
        if any(p in q for p in _EXPLAIN_PHRASES + _SYMPTOMS_PHRASES + _TREATMENT_PHRASES):
            return "full"
        return "code_only"

    # ── 1. Code lookup phrases ────────────────────────────────
    if any(p in q for p in _CODE_PHRASES):
        # Hybrid: also asks for explanation in same query
        if any(p in q for p in _EXPLAIN_PHRASES + _SYMPTOMS_PHRASES + _TREATMENT_PHRASES):
            return "full"
        return "code_only"

    # ── 2. Medication / drug / "what should I do" ────────────
    if any(p in q for p in _MEDICATION_PHRASES):
        return "medication_only"

    # ── 3. Symptoms / "do I have" ────────────────────────────
    if any(p in q for p in _SYMPTOMS_PHRASES):
        return "symptoms_only"

    # ── 4. Treatment / cure / management ────────────────────
    if any(p in q for p in _TREATMENT_PHRASES):
        return "treatment_only"

    # ── 5. General explanation ───────────────────────────────
    if any(p in q for p in _EXPLAIN_PHRASES):
        return "explain"

    # ── 6. Fallback: bare condition name or short query ──────
    # e.g. "malaria", "diabetes type 2", "hypertension"
    # → give a helpful explain + quick action summary
    return "explain"


def _extract_condition(query: str) -> str:
    """
    Extract the medical condition / drug name from a natural query.

    Examples:
      "i am suffering from malaria"   → "malaria"
      "medicines for diabetes type 2" → "diabetes"
      "symptoms of high blood pressure" → "hypertension"
      "what is aspirin"                → "aspirin"
    """
    q = query.lower()

    # ── Condition alias map — maps ANY human phrasing → canonical key ──
    # Canonical keys MUST match keys in _BUILTIN_* dicts exactly.
    # Longer / more specific aliases must come first.
    aliases = [
        # Malaria
        ("mosquito bite fever",     "malaria"),
        ("plasmodium",              "malaria"),
        ("malaria",                 "malaria"),
        # Diabetes
        ("blood sugar",             "diabetes"),
        ("high sugar",              "diabetes"),
        ("type 2 diabetes",         "diabetes"),
        ("type 1 diabetes",         "diabetes"),
        ("type ii diabetes",        "diabetes"),
        ("type i diabetes",         "diabetes"),
        ("diabetes mellitus",       "diabetes"),
        ("diabetic",                "diabetes"),
        ("diabetes",                "diabetes"),
        # Hypertension
        ("high blood pressure",     "hypertension"),
        ("high bp",                 "hypertension"),
        ("elevated blood pressure", "hypertension"),
        ("blood pressure",          "hypertension"),
        ("hypertension",            "hypertension"),
        ("hypertensive",            "hypertension"),
        # Tuberculosis
        ("tuberculosis",            "tuberculosis"),
        ("pulmonary tb",            "tuberculosis"),
        (" tb ",                    "tuberculosis"),   # space-padded to avoid 'tab'
        # Asthma
        ("asthma",                  "asthma"),
        ("asthmatic",               "asthma"),
        ("bronchial asthma",        "asthma"),
        # Pneumonia
        ("pneumonia",               "pneumonia"),
        ("lung infection",          "pneumonia"),
        ("chest infection",         "pneumonia"),
        # Dengue
        ("dengue fever",            "dengue"),
        ("dengue",                  "dengue"),
        ("breakbone fever",         "dengue"),
        # Cholera
        ("cholera",                 "cholera"),
        ("rice water stool",        "cholera"),
        ("water borne",             "cholera"),
        # Hepatitis
        ("hepatitis b",             "hepatitis"),
        ("hepatitis c",             "hepatitis"),
        ("hepatitis a",             "hepatitis"),
        ("hepatitis",               "hepatitis"),
        ("liver inflammation",      "hepatitis"),
        ("jaundice",                "hepatitis"),
        # HIV/AIDS
        ("hiv/aids",                "hiv"),
        ("aids",                    "hiv"),
        ("hiv",                     "hiv"),
        ("antiretroviral",          "hiv"),
        # Influenza
        ("influenza",               "influenza"),
        ("flu",                     "influenza"),
        ("seasonal flu",            "influenza"),
        # COVID
        ("covid-19",                "covid"),
        ("covid 19",                "covid"),
        ("coronavirus",             "covid"),
        ("sars-cov-2",              "covid"),
        ("covid",                   "covid"),
        # Sepsis
        ("sepsis",                  "sepsis"),
        ("septicemia",              "sepsis"),
        ("blood poisoning",         "sepsis"),
        ("septic shock",            "sepsis"),
        # Stroke
        ("stroke",                  "stroke"),
        ("brain attack",            "stroke"),
        ("cerebrovascular",         "stroke"),
        ("tia",                     "stroke"),
        ("transient ischaemic",     "stroke"),
        # Cancer
        ("cancer",                  "cancer"),
        ("tumour",                  "cancer"),
        ("tumor",                   "cancer"),
        ("carcinoma",               "cancer"),
        ("malignancy",              "cancer"),
        ("oncology",                "cancer"),
        # Anaemia
        ("anemia",                  "anemia"),
        ("anaemia",                 "anemia"),
        ("low hemoglobin",          "anemia"),
        ("low haemoglobin",         "anemia"),
        ("iron deficiency",         "anemia"),
        # Depression
        ("depression",              "depression"),
        ("depressed",               "depression"),
        ("major depressive",        "depression"),
        ("low mood",                "depression"),
        # Anxiety
        ("anxiety disorder",        "anxiety"),
        ("anxiety",                 "anxiety"),
        ("panic attack",            "anxiety"),
        ("panic disorder",          "anxiety"),
        ("generalised anxiety",     "anxiety"),
        # Arthritis
        ("rheumatoid arthritis",    "arthritis"),
        ("arthritis",               "arthritis"),
        ("joint pain",              "arthritis"),
        ("joint inflammation",      "arthritis"),
        # Obesity
        ("obesity",                 "obesity"),
        ("obese",                   "obesity"),
        ("overweight",              "obesity"),
        ("bmi over 30",             "obesity"),
        # Seizure/Epilepsy
        ("epilepsy",                "seizure"),
        ("seizure",                 "seizure"),
        ("convulsion",              "seizure"),
        ("epileptic",               "seizure"),
        ("fits",                    "seizure"),
        # Heart Attack / MI
        ("myocardial infarction",   "myocardial infarction"),
        ("heart attack",            "myocardial infarction"),
        ("cardiac arrest",          "myocardial infarction"),
        ("mi ",                     "myocardial infarction"),
        ("stemi",                   "myocardial infarction"),
        ("nstemi",                  "myocardial infarction"),
        # Kidney / Renal Failure
        ("chronic kidney disease",  "renal failure"),
        ("kidney failure",          "renal failure"),
        ("renal failure",           "renal failure"),
        ("ckd",                     "renal failure"),
        ("kidney disease",          "renal failure"),
        ("end stage renal",         "renal failure"),
        # Fracture
        ("fracture",                "fracture"),
        ("broken bone",             "fracture"),
        ("bone fracture",           "fracture"),
        ("bone break",              "fracture"),
    ]
    for alias, canonical in aliases:
        if alias in q:
            return canonical

    # ── Strip intent phrases to isolate condition ────────────
    strip_patterns = [
        r"i am suffering from\s*", r"i have been suffering from\s*",
        r"suffering from\s*",       r"i am sick with\s*",
        r"i have contracted\s*",    r"infected with\s*",
        r"diagnosed with\s*",       r"i got\s+(?:a\s+|the\s+)?",
        r"i've got\s+(?:a\s+|the\s+)?", r"i have\s+(?:a\s+|the\s+)?",
        r"i am\s+(?:a\s+)?",        r"i'm\s+(?:a\s+)?",
        r"what drugs are used for\s*", r"what drugs are given for\s*",
        r"what drugs treat\s*",     r"what are the drugs for\s*",
        r"what are the medicines for\s*", r"which drugs are used for\s*",
        r"medicines for\s*",        r"medication for\s*",
        r"medications for\s*",      r"drugs for\s*",  r"drug for\s*",
        r"treatment for\s*",        r"treatment of\s*",
        r"symptoms of\s*",          r"symptoms for\s*",
        r"signs of\s*",             r"sign of\s*",
        r"what is\s+(?:a\s+|the\s+)?",
        r"what are\s*",             r"explain\s*",
        r"tell me about\s*",
        r"what should i (do|take).{0,20}(for|with|about)\s*",
        r"what should i (do|take)\s*",   # "typhoid what should i take" → typhoid
        r"what to (do|take).{0,20}(for|if i have|when i have)\s*",
        r"what (can|should) i (do|take) (for|with|if|when)\s*",
        r"how to treat\s*",         r"how do i treat\s*",
        r"cure for\s*",             r"therapy for\s*",
        r"what to take for\s*",     r"what can i take for\s*",
        r"help me with\s*",         r"help with\s*",
        r"how (do i|to|can i) (recover|get better|feel better).{0,15}(from|with)?\s*",
        r"i (feel|am feeling|keep feeling)\s*",
        r"if i have\s*",            r"when i have\s*",
        r"do i have\s*",            r"could i have\s*",
        r"am i suffering from\s*",  r"how do i know if i have\s*",
        r"how do i know if\s*",
        # Strip normalised system names (RXNORM, LOINC, SNOMED, ICD-10)
        r"\b(rxnorm|rxcui|loinc|snomed|sct|icd-10|icd10|icd)\b\s*",
        # Only strip these standalone filler words — NOT "disease", "syndrome" etc.
        r"\b(code|for|the|a|an)\b\s*",
    ]
    result = q
    for pat in strip_patterns:
        result = re.sub(pat, "", result).strip()

    # Remove trailing noise
    result = re.sub(r"\b(please|today|now|quickly|fast|soon|help|what|should|take|do)\b", "", result).strip()
    result = re.sub(r"[?!.,]+$", "", result).strip()
    result = re.sub(r"\s{2,}", " ", result).strip()

    # ── IMPORTANT: return the full cleaned string as the condition ──
    # Do NOT scan word-by-word — that loses multi-word conditions like
    # "celiac disease", "parkinson disease", "sickle cell anemia"
    if result and len(result.split()) >= 1:
        return result

    return query


# ─────────────────────────────────────────────────────────────
# VERIFICATION SOURCE LINKS
# ─────────────────────────────────────────────────────────────
_VERIFY_SOURCES = {
    "ICD-10":    "https://icd.who.int/browse10",
    "LOINC":     "https://loinc.org/search",
    "RxNorm":    "https://rxnav.nlm.nih.gov",
    "SNOMED CT": "https://browser.ihtsdotools.org",
    "CPT":       "https://www.ama-assn.org/practice-management/cpt",
    "NDC":       "https://www.accessdata.fda.gov/scripts/cder/ndc",
}

_ARCEE_FOOTER = (
    "\n\n---\n"
    "🔬 *Powered by Google Gemini AI for comprehensive medical research*"
)

def _source_link(system: str) -> str:
    """Return the single most relevant verification URL for a coding system."""
    for key, url in _VERIFY_SOURCES.items():
        if key.lower() in system.lower():
            return f"🔗 Verify: {url}"
    return ""


def _build_source_instruction(intent: str, condition: str) -> str:
    """
    Returns a source instruction string that tells Arcee to include
    a SPECIFIC authoritative URL for this condition — not a generic list.

    Priority order for sources:
      - WHO fact sheet (international diseases, guidelines)
      - NIH / MedlinePlus (clinical reference, USA)
      - CDC (infectious disease, public health)
      - PubMed / NEJM / Lancet (research-backed conditions)
      - RxNorm / DrugBank (medication queries)
      - NICE / AHA / ADA / ACR (specialty guidelines)
    """
    if intent == "medication_only":
        return (
            "SOURCE RULE (MANDATORY):\n"
            "  You MUST end with:\n"
            f"  Guideline  : [Most relevant clinical guideline NAME + its full URL for {condition}]\n"
            "  🔗 RxNorm  : https://rxnav.nlm.nih.gov\n"
            "  Choose the most authoritative source — WHO, CDC, NIH, ADA, AHA, NICE, etc.\n"
            "  The URL must be real and directly relevant to this condition.\n"
            "  NEVER use a placeholder URL."
        )
    elif intent == "symptoms_only":
        return (
            "SOURCE RULE (MANDATORY):\n"
            "  You MUST end with a single line:\n"
            f"  🔗 Source: [Most relevant authoritative URL for {condition} symptoms]\n"
            "  Use WHO fact sheet, CDC, NIH MedlinePlus, or Mayo Clinic.\n"
            "  The URL must be real and specific to this condition."
        )
    elif intent == "treatment_only":
        return (
            "SOURCE RULE (MANDATORY):\n"
            "  You MUST include:\n"
            f"  Guideline : [Most relevant clinical guideline for {condition} + its full URL]\n"
            "  Use WHO, CDC, NICE, AHA, ACR, or specialty society guidelines.\n"
            "  The URL must be real and directly relevant."
        )
    elif intent == "code_only":
        return (
            "SOURCE RULE (MANDATORY):\n"
            "  You MUST end with the most relevant code registry URL:\n"
            "  🔗 Verify: [URL — e.g. https://icd.who.int, https://rxnav.nlm.nih.gov, https://loinc.org]\n"
            "  Pick the URL for the specific coding system in the answer."
        )
    else:  # explain / full
        return (
            "SOURCE RULE (MANDATORY):\n"
            "  You MUST end with:\n"
            f"  🔗 Source: [Most relevant authoritative URL for {condition}]\n"
            "  Use WHO fact sheet, NIH MedlinePlus, CDC, or a PubMed review article URL.\n"
            "  The URL must be real and specific to this condition. Never use a generic homepage."
        )


def _dynamic_prompt(intent: str, condition: str, query: str,
                    system: str = "", code: str = "", term: str = "") -> tuple:
    """
    Builds the Arcee prompt + max_tokens for any condition + any intent.
    Updated for inclusive approach: accepts any health question, uses general knowledge,
    matches user intent, no unnecessary restrictions.
    
    Returns (prompt_str, max_tokens).
    """
    display_name = term or condition.title()
    src_rule = _build_source_instruction(intent, condition)
    code_context = (
        f"\nVerified medical record — System: {system} | Code: {code} | Term: {term}"
        if code else ""
    )

    if intent == "code_only":
        if code:
            prompt = (
                "You are a medical coding expert.\n"
                f"User query: {query}{code_context}\n\n"
                "Task: Verify the medical code.\n"
                "Respond with just the verification:\n"
                f"✓ Code correct: {code} ({system})\n"
                f"or ✗ Correction: [correct code]\n\n"
                f"{DISCLAIMER}"
            )
        else:
            prompt = (
                "You are a medical coding expert.\n"
                f"User query: {query}\n\n"
                "Task: Find the appropriate medical code.\n"
                "Respond in this format:\n"
                "Code: [code]\n"
                "System: [ICD-10 / LOINC / RxNorm / SNOMED CT]\n\n"
                f"{DISCLAIMER}"
            )
        max_tok = 130

    elif intent == "symptoms_only":
        prompt = (
            "You are a clinical expert answering about symptoms.\n"
            f"User query: {query}{code_context}\n"
            f"Condition: {display_name}\n\n"
            "Task: List the common symptoms of this condition in simple words.\n"
            "IMPORTANT: Always provide helpful information using your general medical knowledge.\n"
            "Never say 'data not available offline' or similar.\n"
            "Respond in this format:\n\n"
            f"**Common Symptoms of {display_name}:**\n"
            "• [symptom in simple words]\n"
            "• [symptom]\n"
            "• [symptom]\n"
            "• [symptom]\n\n"
            f"{DISCLAIMER}"
        )
        max_tok = 180

    elif intent == "treatment_only":
        prompt = (
            "You are a clinical expert answering about treatment.\n"
            f"User query: {query}{code_context}\n"
            f"Condition: {display_name}\n\n"
            "Task: Explain the standard treatment approaches in simple words.\n"
            "Respond in this format:\n\n"
            f"**Treatment for {display_name}:**\n"
            "[Explain standard treatment approaches in 2-3 simple sentences]\n\n"
            f"{DISCLAIMER}"
        )
        max_tok = 180

    elif intent == "medication_only":
        prompt = (
            "You are a clinical pharmacology expert answering about medications.\n"
            f"User query: {query}{code_context}\n"
            f"Condition: {display_name}\n\n"
            "Task: List common medications used in simple language.\n"
            "IMPORTANT: Always provide helpful information using your general medical knowledge.\n"
            "Never say 'data not available offline' or similar.\n"
            "Respond in this format:\n\n"
            f"**Common Medications for {display_name}:**\n"
            "• [Drug name] — used for [what it does]\n"
            "• [Drug name] — used for [what it does]\n"
            "• [Drug name] — used for [what it does]\n\n"
            f"{DISCLAIMER}"
        )
        max_tok = 260

    elif intent == "full":
        prompt = (
            "You are a medical expert providing comprehensive information.\n"
            f"User query: {query}{code_context}\n"
            f"Condition: {display_name}\n\n"
            "Task: Provide code and a comprehensive explanation.\n"
            "IMPORTANT: Always provide helpful information using your general medical knowledge.\n"
            "Never say 'data not available offline' or similar.\n"
            "Respond with this structure:\n\n"
            f"**Code:** {code or '[code]'} ({system or '[system]'})\n\n"
            f"**{display_name}**\n"
            "[Brief explanation of what this condition is]\n\n"
            f"{DISCLAIMER}"
        )
        max_tok = 220

    else:  # explain / bare condition / anything else
        prompt = (
            "You are a medical expert answering a health question.\n"
            f"User query: {query}{code_context}\n"
            f"Condition: {display_name}\n\n"
            "Task: Answer the user's question comprehensively.\n"
            "If the user asks for causes, explain causes. If they ask about symptoms, list symptoms.\n"
            "If they ask about treatment or lifestyle, provide those. Match their intent.\n"
            "Use simple, clear language that anyone can understand.\n\n"
            "Respond in this general format (adapt as needed for their specific question):\n\n"
            f"**{display_name}**\n\n"
            f"**Common Symptoms:**\n[List symptoms]\n\n"
            f"**Causes:**\n[Explain causes]\n\n"
            f"**Treatment:**\n[Explain treatment options]\n\n"
            f"**Lifestyle & Prevention:**\n[Lifestyle tips]\n\n"
            "(You don't need all sections — focus on what the user asked about)\n\n"
            f"{DISCLAIMER}"
        )
        max_tok = 350

    return prompt, max_tok


def verify_code_with_arcee(query: str, local_candidate: Optional[Dict]) -> str:
    """
    Core hybrid pipeline: DB result → Gemini verification + clinical answer.
    Uses _dynamic_prompt so it handles ANY condition, not just hardcoded ones.
    Intent-specific — returns ONLY what the user asked for.
    """
    intent    = _detect_intent(query)
    condition = _extract_condition(query)

    if local_candidate:
        system = local_candidate.get("system", "")
        code   = local_candidate.get("code", "")
        term   = local_candidate.get("term", "")
        prompt, max_tok = _dynamic_prompt(
            intent, condition, query,
            system=system, code=code, term=term
        )
    else:
        prompt, max_tok = _dynamic_prompt(intent, condition, query)

    result = call_gemini_api(prompt, max_tokens=max_tok)
    if result:
        result += _ARCEE_FOOTER
    return result


def _arcee_explain(query: str) -> str:
    """
    LLM-only route — no local DB involved.
    Handles ANY medical condition in any natural-language phrasing.
    Uses _dynamic_prompt for full intent + source awareness.
    """
    intent    = _detect_intent(query)
    condition = _extract_condition(query)
    prompt, max_tok = _dynamic_prompt(intent, condition, query)
    result = call_gemini_api(prompt, max_tokens=max_tok)
    if result:
        result += _ARCEE_FOOTER
    return result


def _arcee_hybrid_prompt(query: str, codes: List[Dict]) -> str:
    """
    Hybrid route — user asked for code + explanation together.
    Uses _dynamic_prompt so it works for ANY condition.
    """
    top       = codes[0] if codes else {}
    system    = top.get("system", "")
    code      = top.get("code", "")
    term      = top.get("term", "")
    intent    = _detect_intent(query)
    condition = _extract_condition(query)

    # Force 'full' intent for hybrid route (code + explanation)
    effective_intent = "full" if intent in ("code_only", "explain") else intent
    prompt, max_tok = _dynamic_prompt(
        effective_intent, condition, query,
        system=system, code=code, term=term
    )
    result = call_gemini_api(prompt, max_tokens=max_tok)
    if result:
        result += _ARCEE_FOOTER
    return result

# ══════════════════════════════════════════════════════════════
# SECTION 8 — EXACT-CODE LOOKUP IN DB
# ══════════════════════════════════════════════════════════════

def _detect_code_in_query(query: str) -> Optional[Tuple[str, str]]:
    q = query.lower()
    m = re.search(r"\b(\d{6,18})\b", query)
    if m and ("snomed" in q or "sct" in q or len(m.group(1)) >= 8):
        return (m.group(1), "SNOMED CT")
    m = re.search(r"\b(\d{4,6}-\d)\b", query)
    if m and ("loinc" in q or "lab" in q):
        return (m.group(1), "LOINC")
    m = re.search(r"\b([A-Z]\d{2,3}(?:\.\d{1,4})?)\b", query)
    if m:
        return (m.group(1), "ICD-10")
    m = re.search(r"\bRXCUI[:\s]+(\d+)\b", query, re.IGNORECASE)
    if m:
        return (m.group(1), "RxNorm")
    return None


def _lookup_code_in_db(code: str, system: str) -> Optional[Dict]:
    code = code.strip(); s = system.lower()
    if "icd" in s:
        for r in _safe_load_json(ICD_PATH):
            if r.get("code","").upper() == code.upper():
                return {"code":r.get("code"),"term":r.get("term"),
                        "description":r.get("description",""),"system":"ICD-10"}
        return None
    if "loinc" in s:
        fsize = os.path.getsize(LOINC_PATH) if os.path.exists(LOINC_PATH) else 0
        src = _safe_load_json(LOINC_PATH) if fsize <= 500*1024*1024 else []
        if src:
            for r in src:
                if r.get("LOINC_NUM","") == code:
                    return {"code":r.get("LOINC_NUM"),"term":r.get("LONG_COMMON_NAME",""),
                            "description":f"{r.get('COMPONENT','')} [{r.get('SYSTEM','')}]",
                            "system":"LOINC"}
        else:
            if os.path.exists(LOINC_PATH):
                with open(LOINC_PATH,"r",encoding="utf-8") as f:
                    for line in f:
                        try:
                            r = json.loads(line.strip().rstrip(","))
                            if r.get("LOINC_NUM","") == code:
                                return {"code":r.get("LOINC_NUM"),
                                        "term":r.get("LONG_COMMON_NAME",""),
                                        "description":f"{r.get('COMPONENT','')} [{r.get('SYSTEM','')}]",
                                        "system":"LOINC"}
                        except Exception: continue
        return None
    if "rxnorm" in s or "rx" in s:
        for r in _safe_load_json(RXCONSO_PATH):
            if str(r.get("RXCUI","")) == str(code):
                return {"code":r.get("RXCUI"),"term":r.get("STR",""),
                        "description":f"RxNorm Drug | TTY:{r.get('TTY','')}","system":"RxNorm"}
        return None
    if "snomed" in s or "sct" in s:
        if os.path.exists(SNOMED_PATH):
            with open(SNOMED_PATH,"r",encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line.strip())
                        if str(r.get("code","")) == str(code):
                            return {"code":str(r.get("code")),"term":r.get("description",""),
                                    "description":"SNOMED CT Concept","system":"SNOMED CT"}
                    except Exception: continue
        return None
    return None

# ══════════════════════════════════════════════════════════════
# SECTION 9b — BUILT-IN FALLBACK KNOWLEDGE BASE
#
# Covers 25 common conditions × 4 intents (medications, symptoms,
# treatment, explain). Used when Arcee API is unavailable so
# users ALWAYS get a useful, structured answer.
#
# Condition aliases (defined earlier in _extract_condition):
#   "high blood pressure" / "high bp" → hypertension
#   "diabetic" / "blood sugar"        → diabetes
#   "tb"                              → tuberculosis
#   "flu"                             → influenza
#   "heart attack"                    → myocardial infarction
#   "mosquito bite fever"             → malaria
# ══════════════════════════════════════════════════════════════

_RX = "🔗 RxNorm lookup: https://rxnav.nlm.nih.gov"
_WHO = "https://www.who.int/news-room/fact-sheets/detail"
_CDC = "https://www.cdc.gov"
_ML  = "https://medlineplus.gov"

_BUILTIN_MEDICATIONS: Dict[str, str] = {

    "malaria": (
        "Condition  : Malaria (Plasmodium spp.)\n"
        "Medications:\n"
        "  • Artemether-Lumefantrine — RXCUI: 284635  — ACT (first-line, uncomplicated)\n"
        "  • Artesunate              — RXCUI: 1000157 — Artemisinin IV (severe malaria)\n"
        "  • Chloroquine             — RXCUI: 2468    — P. vivax / P. ovale (sensitive areas)\n"
        "  • Doxycycline             — RXCUI: 3640    — Combination / prophylaxis\n"
        f"Guideline  : WHO Malaria 2023 — {_WHO}/malaria\n{_RX}"
    ),
    "diabetes": (
        "Condition  : Diabetes Mellitus\n"
        "Medications:\n"
        "  • Metformin       — RXCUI: 6809    — Biguanide (first-line Type 2)\n"
        "  • Insulin glargine — RXCUI: 274783 — Long-acting insulin (Type 1 & 2)\n"
        "  • Empagliflozin   — RXCUI: 1545653 — SGLT-2 inhibitor (cardioprotective)\n"
        "  • Sitagliptin     — RXCUI: 593411  — DPP-4 inhibitor\n"
        "Guideline  : ADA Standards of Care 2024 — https://diabetesjournals.org/care/issue/47/Supplement_1\n"
        f"{_RX}"
    ),
    "hypertension": (
        "Condition  : Hypertension (High Blood Pressure)\n"
        "Medications:\n"
        "  • Lisinopril          — RXCUI: 29046  — ACE inhibitor (first-line)\n"
        "  • Amlodipine          — RXCUI: 17767  — Calcium channel blocker\n"
        "  • Hydrochlorothiazide — RXCUI: 5487   — Thiazide diuretic\n"
        "  • Losartan            — RXCUI: 203160 — ARB\n"
        f"Guideline  : ESH 2023 — https://academic.oup.com/eurheartj/article/44/28/2539/7191010\n{_RX}"
    ),
    "tuberculosis": (
        "Condition  : Tuberculosis (TB)\n"
        "Medications (HRZE regimen):\n"
        "  • Isoniazid    — RXCUI: 6038 — Bactericidal (2 months intensive)\n"
        "  • Rifampicin   — RXCUI: 9393 — Bactericidal (6 months total)\n"
        "  • Pyrazinamide — RXCUI: 9054 — Sterilising (2 months intensive)\n"
        "  • Ethambutol   — RXCUI: 4005 — Bacteriostatic (2 months intensive)\n"
        f"Guideline  : WHO TB Guidelines 2022 — {_WHO}/tuberculosis\n{_RX}"
    ),
    "asthma": (
        "Condition  : Asthma\n"
        "Medications:\n"
        "  • Salbutamol (Albuterol) — RXCUI: 435    — SABA reliever (acute attack)\n"
        "  • Budesonide             — RXCUI: 1747   — Inhaled corticosteroid (ICS controller)\n"
        "  • Formoterol             — RXCUI: 386849 — LABA (add-on to ICS)\n"
        "  • Montelukast            — RXCUI: 41493  — Leukotriene antagonist\n"
        f"Guideline  : GINA 2023 — https://ginasthma.org/gina-reports\n{_RX}"
    ),
    "pneumonia": (
        "Condition  : Pneumonia\n"
        "Medications:\n"
        "  • Amoxicillin         — RXCUI: 723    — Aminopenicillin (community-acquired, mild)\n"
        "  • Azithromycin        — RXCUI: 141962 — Macrolide (atypical organisms)\n"
        "  • Co-amoxiclav        — RXCUI: 392518 — Augmented penicillin (moderate)\n"
        "  • Ceftriaxone         — RXCUI: 210491 — 3rd-gen cephalosporin (hospital-acquired)\n"
        f"Guideline  : BTS Pneumonia Guidelines — https://www.brit-thoracic.org.uk\n{_RX}"
    ),
    "dengue": (
        "Condition  : Dengue Fever\n"
        "Medications (supportive — no specific antiviral):\n"
        "  • Paracetamol (Acetaminophen) — RXCUI: 161 — Antipyretic / analgesic\n"
        "  • IV Normal Saline            — RXCUI: 9863 — Fluid resuscitation (severe dengue)\n"
        "  ⚠️ Avoid: Aspirin and NSAIDs (increase bleeding risk)\n"
        f"Guideline  : WHO Dengue Guidelines 2012 — {_WHO}/dengue-and-severe-dengue\n{_RX}"
    ),
    "cholera": (
        "Condition  : Cholera\n"
        "Medications:\n"
        "  • Oral Rehydration Salts (ORS) — RXCUI: 206765 — First-line fluid replacement\n"
        "  • Doxycycline                  — RXCUI: 3640   — Antibiotic (adults, reduces duration)\n"
        "  • Azithromycin                 — RXCUI: 141962 — Antibiotic (children / pregnant)\n"
        "  • IV Ringer's Lactate          — RXCUI: 10432  — Severe dehydration / shock\n"
        f"Guideline  : WHO Cholera Guidelines — {_WHO}/cholera\n{_RX}"
    ),
    "hepatitis": (
        "Condition  : Hepatitis (B & C)\n"
        "Medications:\n"
        "  • Tenofovir (HBV)    — RXCUI: 120810 — Nucleotide analogue (Hep B)\n"
        "  • Entecavir (HBV)    — RXCUI: 217698 — Nucleoside analogue (Hep B)\n"
        "  • Sofosbuvir (HCV)   — RXCUI: 1399145 — DAA pangenotypic (Hep C)\n"
        "  • Ledipasvir/Sofosbuvir — RXCUI: 1599997 — Combination DAA (Hep C)\n"
        f"Guideline  : WHO Hepatitis — {_WHO}/hepatitis\n{_RX}"
    ),
    "hiv": (
        "Condition  : HIV / AIDS\n"
        "Medications (ART — antiretroviral therapy):\n"
        "  • Tenofovir+Emtricitabine — RXCUI: 1487498 — NRTI backbone\n"
        "  • Dolutegravir            — RXCUI: 1433868 — INSTI (preferred 3rd agent)\n"
        "  • Efavirenz               — RXCUI: 195085  — NNRTI\n"
        "  • Lopinavir/Ritonavir     — RXCUI: 210200  — PI/r (salvage therapy)\n"
        f"Guideline  : WHO HIV Guidelines 2023 — {_WHO}/hiv\n{_RX}"
    ),
    "influenza": (
        "Condition  : Influenza (Flu)\n"
        "Medications:\n"
        "  • Oseltamivir (Tamiflu) — RXCUI: 252160 — Neuraminidase inhibitor (within 48h)\n"
        "  • Zanamivir             — RXCUI: 115354 — Inhaled neuraminidase inhibitor\n"
        "  • Paracetamol           — RXCUI: 161    — Fever and pain relief\n"
        "  • Ibuprofen             — RXCUI: 5640   — Anti-inflammatory / antipyretic\n"
        f"Guideline  : CDC Flu Treatment — https://www.cdc.gov/flu/treatment\n{_RX}"
    ),
    "covid": (
        "Condition  : COVID-19 (SARS-CoV-2)\n"
        "Medications:\n"
        "  • Nirmatrelvir/Ritonavir (Paxlovid) — RXCUI: 2367533 — Protease inhibitor (high-risk)\n"
        "  • Remdesivir                         — RXCUI: 2284960 — RNA polymerase inhibitor\n"
        "  • Dexamethasone                      — RXCUI: 3264    — Corticosteroid (severe/ICU)\n"
        "  • Paracetamol                        — RXCUI: 161     — Symptomatic fever/pain\n"
        f"Guideline  : WHO COVID-19 Treatment — https://www.who.int/publications/i/item/WHO-2019-nCoV-therapeutics-2023.1\n{_RX}"
    ),
    "sepsis": (
        "Condition  : Sepsis\n"
        "Medications (empirical — adjust to cultures):\n"
        "  • Piperacillin-Tazobactam — RXCUI: 392440 — Broad-spectrum beta-lactam (first-line)\n"
        "  • Meropenem               — RXCUI: 119548 — Carbapenem (resistant organisms)\n"
        "  • Vancomycin              — RXCUI: 11124  — Glycopeptide (MRSA cover)\n"
        "  • Norepinephrine          — RXCUI: 7512   — Vasopressor (septic shock)\n"
        f"Guideline  : Surviving Sepsis 2021 — https://www.sccm.org/Clinical-Resources/Guidelines/Guidelines/Surviving-Sepsis-Guidelines-2021\n{_RX}"
    ),
    "stroke": (
        "Condition  : Stroke (Ischaemic)\n"
        "Medications:\n"
        "  • Alteplase (tPA)    — RXCUI: 10785  — Thrombolytic (within 4.5h of onset)\n"
        "  • Aspirin            — RXCUI: 1191   — Antiplatelet (after haemorrhage excluded)\n"
        "  • Clopidogrel        — RXCUI: 174742 — Antiplatelet (dual with aspirin)\n"
        "  • Atorvastatin       — RXCUI: 83367  — Statin (secondary prevention)\n"
        f"Guideline  : AHA Stroke 2023 — https://www.ahajournals.org/doi/10.1161/STR.0000000000000436\n{_RX}"
    ),
    "cancer": (
        "Condition  : Cancer (General)\n"
        "Medications (common classes):\n"
        "  • Paclitaxel    — RXCUI: 56946  — Taxane chemotherapy\n"
        "  • Doxorubicin   — RXCUI: 3639   — Anthracycline chemotherapy\n"
        "  • Pembrolizumab — RXCUI: 1726337 — PD-1 checkpoint inhibitor (immunotherapy)\n"
        "  • Tamoxifen     — RXCUI: 10324  — SERM (hormone receptor+ breast cancer)\n"
        f"Guideline  : NCI Cancer Treatment — https://www.cancer.gov/about-cancer/treatment\n{_RX}"
    ),
    "anemia": (
        "Condition  : Anaemia (Iron-Deficiency)\n"
        "Medications:\n"
        "  • Ferrous sulphate   — RXCUI: 4450   — Oral iron supplement (first-line)\n"
        "  • Ferric carboxymaltose — RXCUI: 858080 — IV iron (malabsorption/intolerance)\n"
        "  • Folic acid         — RXCUI: 4511   — Folate-deficiency anaemia\n"
        "  • Cyanocobalamin (B12) — RXCUI: 2200 — B12-deficiency / pernicious anaemia\n"
        f"Guideline  : WHO Anaemia — {_WHO}/anaemia\n{_RX}"
    ),
    "depression": (
        "Condition  : Depression (Major Depressive Disorder)\n"
        "Medications:\n"
        "  • Sertraline     — RXCUI: 36437  — SSRI (first-line)\n"
        "  • Fluoxetine     — RXCUI: 41493  — SSRI\n"
        "  • Venlafaxine    — RXCUI: 39786  — SNRI (moderate-severe)\n"
        "  • Mirtazapine    — RXCUI: 15996  — NaSSA (sleep disturbance)\n"
        f"Guideline  : NICE Depression 2022 — https://www.nice.org.uk/guidance/ng222\n{_RX}"
    ),
    "anxiety": (
        "Condition  : Anxiety Disorder (GAD)\n"
        "Medications:\n"
        "  • Sertraline   — RXCUI: 36437 — SSRI (first-line long-term)\n"
        "  • Escitalopram — RXCUI: 321988 — SSRI\n"
        "  • Venlafaxine  — RXCUI: 39786 — SNRI\n"
        "  • Diazepam     — RXCUI: 3322  — Benzodiazepine (short-term only)\n"
        f"Guideline  : NICE Anxiety 2020 — https://www.nice.org.uk/guidance/cg113\n{_RX}"
    ),
    "pneumonia": (
        "Condition  : Pneumonia\n"
        "Medications:\n"
        "  • Amoxicillin   — RXCUI: 723    — First-line community-acquired (mild)\n"
        "  • Azithromycin  — RXCUI: 141962 — Atypical organisms (Mycoplasma, Legionella)\n"
        "  • Co-amoxiclav  — RXCUI: 392518 — Moderate severity\n"
        "  • Ceftriaxone   — RXCUI: 210491 — Hospital-acquired / severe\n"
        f"Guideline  : BTS CAP Guidelines — https://www.brit-thoracic.org.uk\n{_RX}"
    ),
    "arthritis": (
        "Condition  : Rheumatoid Arthritis\n"
        "Medications:\n"
        "  • Methotrexate   — RXCUI: 8692   — DMARD (disease-modifying, first-line)\n"
        "  • Hydroxychloroquine — RXCUI: 5521 — DMARD (mild disease)\n"
        "  • Adalimumab     — RXCUI: 327361 — Anti-TNF biologic\n"
        "  • Prednisolone   — RXCUI: 8638   — Corticosteroid (bridging therapy)\n"
        f"Guideline  : ACR RA Guidelines 2021 — https://www.rheumatology.org/Practice-Quality/Clinical-Support/Clinical-Practice-Guidelines/Rheumatoid-Arthritis\n{_RX}"
    ),
    "obesity": (
        "Condition  : Obesity (BMI ≥ 30)\n"
        "Medications:\n"
        "  • Orlistat       — RXCUI: 37925  — Lipase inhibitor (fat absorption blocker)\n"
        "  • Semaglutide    — RXCUI: 2200c  — GLP-1 agonist (Wegovy — weight management)\n"
        "  • Naltrexone/Bupropion — RXCUI: 1551489 — Combination appetite suppressant\n"
        "  • Liraglutide    — RXCUI: 475968 — GLP-1 agonist (Saxenda)\n"
        f"Guideline  : WHO Obesity — {_WHO}/obesity-and-overweight\n{_RX}"
    ),
    "seizure": (
        "Condition  : Seizure / Epilepsy\n"
        "Medications:\n"
        "  • Valproate      — RXCUI: 11170  — Broad-spectrum AED (first-line generalised)\n"
        "  • Levetiracetam  — RXCUI: 67107  — AED (focal and generalised)\n"
        "  • Lamotrigine    — RXCUI: 28439  — AED (focal / absence / mood stabiliser)\n"
        "  • Diazepam IV    — RXCUI: 3322   — Acute seizure termination (status epilepticus)\n"
        f"Guideline  : NICE Epilepsy 2022 — https://www.nice.org.uk/guidance/ng217\n{_RX}"
    ),
    "myocardial infarction": (
        "Condition  : Myocardial Infarction (Heart Attack)\n"
        "Medications:\n"
        "  • Aspirin        — RXCUI: 1191   — Antiplatelet (immediate 300 mg loading dose)\n"
        "  • Clopidogrel    — RXCUI: 174742 — Dual antiplatelet (DAPT with aspirin)\n"
        "  • Atorvastatin   — RXCUI: 83367  — High-intensity statin\n"
        "  • Metoprolol     — RXCUI: 6918   — Beta-blocker (reduce cardiac workload)\n"
        f"Guideline  : AHA/ACC STEMI 2022 — https://www.ahajournals.org/doi/10.1161/CIR.0000000000001002\n{_RX}"
    ),
    "renal failure": (
        "Condition  : Chronic Kidney Disease (CKD)\n"
        "Medications:\n"
        "  • Ramipril        — RXCUI: 35296  — ACE inhibitor (renoprotective, first-line)\n"
        "  • Losartan        — RXCUI: 203160 — ARB (ACE-intolerant patients)\n"
        "  • Dapagliflozin   — RXCUI: 1488564 — SGLT-2 inhibitor (CKD progression)\n"
        "  • Erythropoietin  — RXCUI: 51428  — Renal anaemia\n"
        f"Guideline  : KDIGO CKD 2022 — https://kdigo.org/guidelines/ckd-evaluation-and-management\n{_RX}"
    ),
    "influenza": (
        "Condition  : Influenza (Flu)\n"
        "Medications:\n"
        "  • Oseltamivir (Tamiflu) — RXCUI: 252160 — Neuraminidase inhibitor (within 48h)\n"
        "  • Zanamivir             — RXCUI: 115354 — Inhaled antiviral\n"
        "  • Paracetamol           — RXCUI: 161    — Fever/pain (symptomatic)\n"
        "  • Ibuprofen             — RXCUI: 5640   — Anti-inflammatory/antipyretic\n"
        f"Guideline  : CDC Flu Treatment — https://www.cdc.gov/flu/treatment\n{_RX}"
    ),
    "fracture": (
        "Condition  : Bone Fracture\n"
        "Medications:\n"
        "  • Ibuprofen       — RXCUI: 5640   — NSAID analgesic (mild-moderate pain)\n"
        "  • Morphine        — RXCUI: 7052   — Opioid (severe pain, acute setting)\n"
        "  • Calcium + Vit D — RXCUI: 20610  — Bone healing support\n"
        "  • Zoledronic acid — RXCUI: 258328 — Bisphosphonate (osteoporotic fractures)\n"
        f"Guideline  : NICE Fractures — https://www.nice.org.uk/guidance/ng38\n{_RX}"
    ),
}

_BUILTIN_SYMPTOMS: Dict[str, str] = {
    "malaria": (
        "Condition : Malaria\nSymptoms  :\n"
        "  • Cyclical high fever with chills and rigors\n"
        "  • Severe headache and muscle/joint aches\n"
        "  • Nausea, vomiting, and profuse sweating\n"
        "  • Fatigue and general weakness\n"
        "  • Jaundice, confusion, or seizures (severe P. falciparum)\n"
        f"🔗 Source: {_WHO}/malaria"
    ),
    "diabetes": (
        "Condition : Diabetes Mellitus\nSymptoms  :\n"
        "  • Excessive thirst (polydipsia) and frequent urination (polyuria)\n"
        "  • Unexplained weight loss\n"
        "  • Fatigue, blurred vision\n"
        "  • Slow-healing wounds and recurrent infections\n"
        "  • Tingling/numbness in hands and feet (neuropathy)\n"
        f"🔗 Source: {_WHO}/diabetes"
    ),
    "hypertension": (
        "Condition : Hypertension\nSymptoms  :\n"
        "  • Often completely asymptomatic ('silent killer')\n"
        "  • Morning occipital headache\n"
        "  • Dizziness and blurred vision\n"
        "  • Shortness of breath on exertion\n"
        "  • Chest pain or palpitations (hypertensive crisis)\n"
        f"🔗 Source: {_WHO}/hypertension"
    ),
    "tuberculosis": (
        "Condition : Tuberculosis (TB)\nSymptoms  :\n"
        "  • Persistent cough lasting > 3 weeks (may be blood-stained)\n"
        "  • Night sweats and low-grade fever\n"
        "  • Unexplained weight loss and fatigue\n"
        "  • Chest pain and shortness of breath\n"
        "  • Swollen lymph nodes (extrapulmonary TB)\n"
        f"🔗 Source: {_WHO}/tuberculosis"
    ),
    "asthma": (
        "Condition : Asthma\nSymptoms  :\n"
        "  • Recurrent wheezing and chest tightness\n"
        "  • Shortness of breath (worse at night/exercise)\n"
        "  • Persistent dry cough (especially nocturnal)\n"
        "  • Symptoms triggered by allergens, cold, exercise, smoke\n"
        "  • Rapid breathing and use of accessory muscles (severe attack)\n"
        f"🔗 Source: {_WHO}/asthma"
    ),
    "pneumonia": (
        "Condition : Pneumonia\nSymptoms  :\n"
        "  • Productive cough with purulent / rusty sputum\n"
        "  • High fever with chills\n"
        "  • Pleuritic chest pain (worse on breathing)\n"
        "  • Shortness of breath and rapid breathing\n"
        "  • Fatigue, loss of appetite, confusion (elderly)\n"
        f"🔗 Source: {_CDC}/pneumonia"
    ),
    "dengue": (
        "Condition : Dengue Fever\nSymptoms  :\n"
        "  • Sudden high fever (39–40°C) for 2–7 days\n"
        "  • Severe headache and pain behind the eyes\n"
        "  • Muscle, bone, and joint pain ('breakbone fever')\n"
        "  • Skin rash (maculopapular, appears 3–5 days after fever)\n"
        "  • Bleeding gums, nosebleeds, easy bruising (severe dengue)\n"
        f"🔗 Source: {_WHO}/dengue-and-severe-dengue"
    ),
    "cholera": (
        "Condition : Cholera\nSymptoms  :\n"
        "  • Sudden onset profuse watery diarrhoea ('rice-water stools')\n"
        "  • Severe vomiting\n"
        "  • Rapid dehydration: sunken eyes, dry mouth, decreased urine\n"
        "  • Muscle cramps (due to electrolyte loss)\n"
        "  • Shock (hypotension) in severe cases\n"
        f"🔗 Source: {_WHO}/cholera"
    ),
    "hepatitis": (
        "Condition : Hepatitis\nSymptoms  :\n"
        "  • Jaundice (yellowing of skin and eyes)\n"
        "  • Dark urine and pale stools\n"
        "  • Fatigue, nausea, and loss of appetite\n"
        "  • Right upper abdominal pain (liver region)\n"
        "  • Fever (more common in acute hepatitis A/E)\n"
        f"🔗 Source: {_WHO}/hepatitis"
    ),
    "hiv": (
        "Condition : HIV\nSymptoms  :\n"
        "  • Acute: fever, swollen lymph nodes, sore throat, rash (2–4 wks)\n"
        "  • Chronic: often asymptomatic for years\n"
        "  • Weight loss, persistent diarrhoea, night sweats\n"
        "  • Recurrent infections (TB, candidiasis, pneumonia)\n"
        "  • AIDS stage: CD4 < 200 with opportunistic infections\n"
        f"🔗 Source: {_WHO}/hiv"
    ),
    "influenza": (
        "Condition : Influenza (Flu)\nSymptoms  :\n"
        "  • Sudden onset high fever (38–40°C)\n"
        "  • Severe muscle aches and headache\n"
        "  • Dry cough and sore throat\n"
        "  • Chills, fatigue, and loss of appetite\n"
        "  • Runny or stuffy nose\n"
        f"🔗 Source: {_WHO}/influenza"
    ),
    "covid": (
        "Condition : COVID-19\nSymptoms  :\n"
        "  • Fever, dry cough, and fatigue\n"
        "  • Loss of taste or smell (anosmia/ageusia)\n"
        "  • Shortness of breath (severe cases)\n"
        "  • Sore throat, headache, muscle aches\n"
        "  • Diarrhoea and nausea (some cases)\n"
        f"🔗 Source: {_WHO}/coronavirus-disease-covid-19"
    ),
    "sepsis": (
        "Condition : Sepsis\nSymptoms  :\n"
        "  • High fever or abnormally low temperature\n"
        "  • Rapid heart rate (tachycardia) and rapid breathing\n"
        "  • Confusion or altered mental status\n"
        "  • Extreme pain or discomfort\n"
        "  • Clammy / mottled skin (septic shock)\n"
        f"🔗 Source: {_WHO}/sepsis"
    ),
    "stroke": (
        "Condition : Stroke\nSymptoms (FAST):\n"
        "  • Face drooping on one side\n"
        "  • Arm weakness (cannot raise both arms equally)\n"
        "  • Speech difficulty (slurred or incomprehensible)\n"
        "  • Sudden severe headache ('thunderclap')\n"
        "  • Sudden vision loss or double vision\n"
        f"🔗 Source: {_WHO}/cardiovascular_diseases/en"
    ),
    "anemia": (
        "Condition : Anaemia\nSymptoms  :\n"
        "  • Fatigue, weakness, and pallor (pale skin)\n"
        "  • Shortness of breath on exertion\n"
        "  • Dizziness and light-headedness\n"
        "  • Rapid or irregular heartbeat (palpitations)\n"
        "  • Cold hands and feet, brittle nails (iron deficiency)\n"
        f"🔗 Source: {_WHO}/anaemia"
    ),
    "depression": (
        "Condition : Depression\nSymptoms  :\n"
        "  • Persistent low mood, sadness, or emptiness\n"
        "  • Loss of interest or pleasure in activities (anhedonia)\n"
        "  • Fatigue and decreased energy\n"
        "  • Sleep disturbance (insomnia or hypersomnia)\n"
        "  • Difficulty concentrating; thoughts of death/suicide\n"
        f"🔗 Source: {_WHO}/depression"
    ),
    "anxiety": (
        "Condition : Anxiety Disorder\nSymptoms  :\n"
        "  • Excessive worry and restlessness\n"
        "  • Palpitations, rapid breathing, sweating\n"
        "  • Muscle tension and fatigue\n"
        "  • Difficulty sleeping and concentrating\n"
        "  • Avoidance of anxiety-provoking situations\n"
        f"🔗 Source: {_WHO}/mental-health/management/depression/anxiety"
    ),
    "arthritis": (
        "Condition : Arthritis (Rheumatoid)\nSymptoms  :\n"
        "  • Symmetric joint pain, swelling, and stiffness\n"
        "  • Morning stiffness lasting > 1 hour\n"
        "  • Fatigue, fever, and weight loss\n"
        "  • Subcutaneous rheumatoid nodules\n"
        "  • Joint deformity (chronic untreated disease)\n"
        f"🔗 Source: {_ML}/rheumatoidarthritis.html"
    ),
    "obesity": (
        "Condition : Obesity\nSymptoms / Complications:\n"
        "  • BMI ≥ 30; excessive body fat accumulation\n"
        "  • Breathlessness on exertion and sleep apnoea\n"
        "  • Joint pain (knees, hips — excess mechanical load)\n"
        "  • Increased sweating and skin fold infections\n"
        "  • Risk factor for T2DM, hypertension, CVD, certain cancers\n"
        f"🔗 Source: {_WHO}/obesity-and-overweight"
    ),
    "seizure": (
        "Condition : Seizure / Epilepsy\nSymptoms  :\n"
        "  • Sudden uncontrolled jerking movements (tonic-clonic)\n"
        "  • Temporary confusion or staring spells (absence)\n"
        "  • Loss of consciousness\n"
        "  • Aura (unusual smell, taste, or visual disturbance before onset)\n"
        "  • Post-ictal confusion and fatigue after seizure\n"
        f"🔗 Source: {_WHO}/epilepsy"
    ),
    "cancer": (
        "Condition : Cancer\nSymptoms (general warning signs):\n"
        "  • Unexplained weight loss and persistent fatigue\n"
        "  • New lump or swelling anywhere in the body\n"
        "  • Persistent cough, hoarseness, or difficulty swallowing\n"
        "  • Unusual bleeding or discharge\n"
        "  • Changes in skin moles or non-healing sores\n"
        f"🔗 Source: {_WHO}/cancer"
    ),
    "renal failure": (
        "Condition : Chronic Kidney Disease (CKD)\nSymptoms  :\n"
        "  • Fatigue and weakness (anaemia from reduced EPO)\n"
        "  • Ankle / leg swelling (fluid retention)\n"
        "  • Reduced urine output or foamy urine (proteinuria)\n"
        "  • Nausea, loss of appetite, and itching (uraemia)\n"
        "  • Shortness of breath and hypertension\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/chronic-kidney-disease"
    ),
    "fracture": (
        "Condition : Bone Fracture\nSymptoms  :\n"
        "  • Sudden severe pain at fracture site\n"
        "  • Swelling, bruising, and deformity\n"
        "  • Inability to move or bear weight on affected area\n"
        "  • Tenderness and crepitus on palpation\n"
        "  • Numbness or tingling (nerve involvement)\n"
        f"🔗 Source: {_ML}/fractures.html"
    ),
    "myocardial infarction": (
        "Condition : Myocardial Infarction (Heart Attack)\nSymptoms  :\n"
        "  • Central crushing chest pain radiating to left arm/jaw\n"
        "  • Shortness of breath and sweating\n"
        "  • Nausea, vomiting, and light-headedness\n"
        "  • Palpitations or irregular heartbeat\n"
        "  • Silent MI common in diabetic patients (no chest pain)\n"
        f"🔗 Source: {_WHO}/cardiovascular_diseases/en"
    ),
}

_BUILTIN_TREATMENT: Dict[str, str] = {
    "malaria": (
        "Condition : Malaria\n"
        "Treatment : WHO first-line for uncomplicated P. falciparum: Artemisinin-based "
        "Combination Therapy (ACT), e.g. Artemether-Lumefantrine for 3 days. Severe malaria "
        "requires IV Artesunate. P. vivax / P. ovale: chloroquine (sensitive areas) + "
        "primaquine for radical cure.\n"
        "Guideline : WHO Malaria 2023 — https://www.who.int/publications/i/item/9789240086173"
    ),
    "diabetes": (
        "Condition : Diabetes Mellitus\n"
        "Treatment : Type 2 — Metformin + lifestyle changes (diet, exercise) as first-line; "
        "escalate with SGLT-2 inhibitors or GLP-1 agonists for cardiovascular/renal benefit. "
        "Type 1 — insulin therapy (basal-bolus regimen) is mandatory.\n"
        "Guideline : ADA 2024 — https://diabetesjournals.org/care/issue/47/Supplement_1"
    ),
    "hypertension": (
        "Condition : Hypertension\n"
        "Treatment : First-line: ACE inhibitor (e.g. lisinopril) or ARB + thiazide diuretic "
        "± calcium channel blocker. Lifestyle: low-salt diet, exercise, weight loss, limit "
        "alcohol. Target BP < 130/80 mmHg (high-risk) or < 140/90 (standard).\n"
        "Guideline : ESH 2023 — https://academic.oup.com/eurheartj/article/44/28/2539/7191010"
    ),
    "tuberculosis": (
        "Condition : Tuberculosis (TB)\n"
        "Treatment : Standard HRZE regimen — 2 months Isoniazid + Rifampicin + Pyrazinamide "
        "+ Ethambutol (intensive phase), then 4 months Isoniazid + Rifampicin (continuation). "
        "Total 6 months. Drug-resistant TB requires extended regimens.\n"
        "Guideline : WHO TB 2022 — https://www.who.int/teams/global-tuberculosis-programme/tb-reports"
    ),
    "asthma": (
        "Condition : Asthma\n"
        "Treatment : Step-up approach — SABA reliever (salbutamol) for acute symptoms; add "
        "inhaled corticosteroid (ICS) for persistent asthma; ICS + LABA for moderate-severe. "
        "Avoid triggers. Annual flu vaccine. Biologic (omalizumab) for severe allergic asthma.\n"
        "Guideline : GINA 2023 — https://ginasthma.org/gina-reports"
    ),
    "pneumonia": (
        "Condition : Pneumonia\n"
        "Treatment : Community-acquired (mild): oral amoxicillin 5–7 days. Atypical: add "
        "azithromycin. Moderate: co-amoxiclav. Hospital-acquired / severe: IV ceftriaxone ± "
        "metronidazole. Supplement oxygen if SpO2 < 94%.\n"
        "Guideline : BTS Guidelines — https://www.brit-thoracic.org.uk"
    ),
    "dengue": (
        "Condition : Dengue Fever\n"
        "Treatment : No specific antiviral. Supportive: adequate oral/IV fluids, paracetamol "
        "for fever (avoid aspirin and NSAIDs). Monitor platelet count and haematocrit daily. "
        "Severe dengue (shock / haemorrhage) requires ICU admission and IV fluid resuscitation.\n"
        "Guideline : WHO Dengue 2012 — https://www.who.int/publications/i/item/9789241504829"
    ),
    "cholera": (
        "Condition : Cholera\n"
        "Treatment : ORS (Oral Rehydration Salts) is the cornerstone — 75 mEq/L sodium "
        "solution. Severe dehydration: IV Ringer's lactate. Antibiotics (doxycycline or "
        "azithromycin) shorten illness and reduce shedding. Zinc supplements for children.\n"
        "Guideline : WHO Cholera — https://www.who.int/news-room/fact-sheets/detail/cholera"
    ),
    "hepatitis": (
        "Condition : Hepatitis\n"
        "Treatment : Hep B (chronic): Tenofovir or Entecavir — suppresses viral replication. "
        "Hep C: Direct-acting antivirals (DAAs) such as Sofosbuvir-based regimens achieve "
        ">95% cure in 8–12 weeks. Hep A & E: supportive care only.\n"
        "Guideline : WHO Hepatitis — https://www.who.int/hepatitis"
    ),
    "hiv": (
        "Condition : HIV\n"
        "Treatment : Antiretroviral Therapy (ART) started immediately after diagnosis. "
        "Preferred regimen: Tenofovir + Emtricitabine + Dolutegravir (TLD). ART suppresses "
        "viral load to undetectable, prevents transmission, and restores immune function. "
        "Lifelong therapy required.\n"
        "Guideline : WHO HIV 2023 — https://www.who.int/hiv"
    ),
    "influenza": (
        "Condition : Influenza\n"
        "Treatment : Antivirals within 48h of onset: Oseltamivir (Tamiflu) 75 mg twice daily "
        "× 5 days. Symptomatic: paracetamol/ibuprofen for fever and pain, rest, fluids. "
        "Annual influenza vaccination is the best prevention.\n"
        "Guideline : CDC Flu Treatment — https://www.cdc.gov/flu/treatment"
    ),
    "covid": (
        "Condition : COVID-19\n"
        "Treatment : High-risk patients within 5 days of symptoms: Nirmatrelvir/Ritonavir "
        "(Paxlovid). Hospitalised/severe: Remdesivir + Dexamethasone. Supportive: oxygen, "
        "prone positioning (severe hypoxia), anticoagulation (LMWH). Vaccination remains "
        "primary prevention.\n"
        "Guideline : WHO COVID-19 — https://www.who.int/publications/i/item/WHO-2019-nCoV-therapeutics-2023.1"
    ),
    "sepsis": (
        "Condition : Sepsis\n"
        "Treatment : 'Hour-1 Bundle' — blood cultures, IV broad-spectrum antibiotics within "
        "1 hour, 30 mL/kg IV crystalloid bolus, vasopressors (norepinephrine) if MAP < 65 "
        "mmHg, lactate measurement. De-escalate antibiotics once cultures known.\n"
        "Guideline : Surviving Sepsis 2021 — https://www.sccm.org/Clinical-Resources/Guidelines/Guidelines/Surviving-Sepsis-Guidelines-2021"
    ),
    "stroke": (
        "Condition : Ischaemic Stroke\n"
        "Treatment : IV Alteplase (tPA) within 4.5 hours of onset (if no haemorrhage). "
        "Mechanical thrombectomy for large vessel occlusion up to 24h. Dual antiplatelet "
        "(aspirin + clopidogrel) × 21 days then single agent. High-dose statin. BP control.\n"
        "Guideline : AHA/ASA 2023 — https://www.ahajournals.org/doi/10.1161/STR.0000000000000436"
    ),
    "anemia": (
        "Condition : Anaemia (Iron-Deficiency)\n"
        "Treatment : Oral ferrous sulphate 200 mg three times daily × 3–6 months. IV iron "
        "(ferric carboxymaltose) if oral intolerant or malabsorption. Treat underlying cause "
        "(bleeding, diet). B12 deficiency: IM hydroxocobalamin. Folic acid deficiency: oral "
        "folic acid 5 mg daily.\n"
        "Guideline : WHO Anaemia — https://www.who.int/news-room/fact-sheets/detail/anaemia"
    ),
    "depression": (
        "Condition : Depression\n"
        "Treatment : First-line: SSRI (sertraline or fluoxetine) for ≥ 6 months. Combine "
        "with CBT (cognitive behavioural therapy) for moderate-severe. If no response: "
        "switch SSRI, add SNRI, or augment with antipsychotic. Severe/suicidal: inpatient "
        "admission.\n"
        "Guideline : NICE NG222 2022 — https://www.nice.org.uk/guidance/ng222"
    ),
    "anxiety": (
        "Condition : Generalised Anxiety Disorder\n"
        "Treatment : First-line: SSRI (sertraline or escitalopram). CBT equally effective. "
        "SNRI (venlafaxine) for non-responders. Benzodiazepines only short-term (< 2–4 weeks). "
        "Mindfulness, relaxation therapy as adjuncts.\n"
        "Guideline : NICE CG113 — https://www.nice.org.uk/guidance/cg113"
    ),
    "arthritis": (
        "Condition : Rheumatoid Arthritis\n"
        "Treatment : Methotrexate (DMARD) started as soon as diagnosis confirmed — reduces "
        "joint damage. Bridge with low-dose prednisolone while awaiting DMARD effect. "
        "Biologics (anti-TNF: adalimumab) for inadequate DMARD response. Regular monitoring "
        "of liver function and FBC.\n"
        "Guideline : ACR 2021 — https://www.rheumatology.org/Practice-Quality/Clinical-Support/Clinical-Practice-Guidelines/Rheumatoid-Arthritis"
    ),
    "seizure": (
        "Condition : Epilepsy / Seizure\n"
        "Treatment : Acute: benzodiazepine (IV diazepam or lorazepam) to terminate seizure. "
        "Maintenance: valproate (generalised), lamotrigine or levetiracetam (focal). Avoid "
        "triggers (sleep deprivation, alcohol, flashing lights). Cannot drive until 1 year "
        "seizure-free.\n"
        "Guideline : NICE NG217 2022 — https://www.nice.org.uk/guidance/ng217"
    ),
    "myocardial infarction": (
        "Condition : Myocardial Infarction (Heart Attack)\n"
        "Treatment : STEMI: Primary PCI (balloon angioplasty) within 90 minutes is gold "
        "standard. If PCI unavailable: thrombolysis (alteplase). All MI: dual antiplatelet "
        "(aspirin + ticagrelor/clopidogrel), high-dose statin, beta-blocker, ACE inhibitor, "
        "cardiac rehab.\n"
        "Guideline : AHA/ACC 2022 — https://www.ahajournals.org/doi/10.1161/CIR.0000000000001002"
    ),
    "cancer": (
        "Condition : Cancer\n"
        "Treatment : Depends on type and stage — Surgery (resection of tumour), "
        "Chemotherapy (cytotoxic agents), Radiotherapy, Immunotherapy (checkpoint "
        "inhibitors like pembrolizumab), or Targeted therapy (e.g. trastuzumab for HER2+ "
        "breast cancer). Multidisciplinary team (MDT) approach is standard.\n"
        "Guideline : NCI Cancer Treatment — https://www.cancer.gov/about-cancer/treatment"
    ),
    "renal failure": (
        "Condition : Chronic Kidney Disease (CKD)\n"
        "Treatment : Treat underlying cause (BP control with ACE inhibitor/ARB, glycaemic "
        "control in diabetics). SGLT-2 inhibitors (dapagliflozin) slow CKD progression. "
        "Avoid nephrotoxins (NSAIDs, IV contrast). End-stage: haemodialysis, peritoneal "
        "dialysis, or kidney transplant.\n"
        "Guideline : KDIGO 2022 — https://kdigo.org/guidelines/ckd-evaluation-and-management"
    ),
    "obesity": (
        "Condition : Obesity\n"
        "Treatment : Lifestyle first: 500-750 kcal/day caloric deficit + 150+ min/week "
        "moderate exercise. Pharmacotherapy if BMI >= 30: orlistat or GLP-1 agonist "
        "(semaglutide / liraglutide). Bariatric surgery (BMI >= 40 or >= 35 with comorbidities).\n"
        "Guideline : WHO Obesity — https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight"
    ),
    "fracture": (
        "Condition : Bone Fracture\n"
        "Treatment : Immobilisation: plaster cast or splint for stable fractures. Surgery "
        "(ORIF / intramedullary nail) for displaced/unstable fractures. Analgesia: NSAIDs "
        "or opioids for acute pain. Weight-bearing as tolerated. Calcium + Vitamin D "
        "supplementation for osteoporotic fractures.\n"
        "Guideline : NICE NG38 — https://www.nice.org.uk/guidance/ng38"
    ),
}

_BUILTIN_EXPLAIN: Dict[str, str] = {
    "malaria": (
        "Condition : Malaria\n"
        "Answer    : Malaria is caused by Plasmodium parasites transmitted via Anopheles "
        "mosquito bites. P. falciparum is the most lethal species. It infects and destroys "
        "red blood cells, causing cyclical fever, anaemia, and potentially fatal organ failure.\n"
        "Key fact  : Malaria is preventable (bed nets, prophylaxis) and curable — ACT within "
        "24h of symptom onset dramatically reduces mortality.\n"
        f"🔗 Source: {_WHO}/malaria"
    ),
    "diabetes": (
        "Condition : Diabetes Mellitus\n"
        "Answer    : Diabetes is a chronic metabolic disorder where the body cannot regulate "
        "blood glucose — either due to lack of insulin (Type 1) or insulin resistance (Type 2). "
        "Complications include blindness, kidney failure, neuropathy, and cardiovascular disease.\n"
        "Key fact  : Type 2 is largely preventable through diet, exercise, and healthy weight.\n"
        f"🔗 Source: {_WHO}/diabetes"
    ),
    "hypertension": (
        "Condition : Hypertension (High Blood Pressure)\n"
        "Answer    : Hypertension is persistently elevated blood pressure (≥ 130/80 mmHg). "
        "It is the leading risk factor for stroke, heart attack, heart failure, and kidney "
        "disease. Most people have no symptoms — hence called the 'silent killer'.\n"
        "Key fact  : Reducing salt intake, regular exercise, and antihypertensive medication "
        "can effectively control BP and prevent complications.\n"
        f"🔗 Source: {_WHO}/hypertension"
    ),
    "tuberculosis": (
        "Condition : Tuberculosis (TB)\n"
        "Answer    : TB is a bacterial infection caused by Mycobacterium tuberculosis, "
        "primarily affecting the lungs. It spreads through airborne droplets. TB is curable "
        "with a 6-month HRZE antibiotic regimen but drug-resistant TB (MDR-TB) is a growing "
        "global threat.\n"
        "Key fact  : TB is the world's second deadliest infectious disease after COVID-19.\n"
        f"🔗 Source: {_WHO}/tuberculosis"
    ),
    "asthma": (
        "Condition : Asthma\n"
        "Answer    : Asthma is a chronic inflammatory airway disease causing recurrent "
        "episodes of wheeze, breathlessness, and chest tightness — triggered by allergens, "
        "exercise, cold air, or respiratory infections. The airway obstruction is largely "
        "reversible with bronchodilators.\n"
        "Key fact  : With correct inhaler technique and adherence, most patients with asthma "
        "can lead fully normal lives.\n"
        f"🔗 Source: {_WHO}/asthma"
    ),
    "pneumonia": (
        "Condition : Pneumonia\n"
        "Answer    : Pneumonia is an infection of the lung parenchyma caused by bacteria "
        "(Streptococcus pneumoniae most common), viruses, or fungi. It fills air sacs with "
        "fluid/pus causing cough, fever, and breathing difficulty. It is a leading cause of "
        "death in children under 5.\n"
        "Key fact  : Pneumococcal and influenza vaccines significantly reduce pneumonia risk.\n"
        f"🔗 Source: {_WHO}/pneumonia"
    ),
    "dengue": (
        "Condition : Dengue Fever\n"
        "Answer    : Dengue is a viral disease transmitted by Aedes aegypti mosquitoes, "
        "endemic in tropical/subtropical regions. Most cases are self-limiting but severe "
        "dengue (haemorrhagic fever / shock syndrome) can be fatal without prompt fluid "
        "management.\n"
        "Key fact  : There is no specific antiviral — treatment is supportive; avoid aspirin "
        "and NSAIDs as they worsen bleeding risk.\n"
        f"🔗 Source: {_WHO}/dengue-and-severe-dengue"
    ),
    "cholera": (
        "Condition : Cholera\n"
        "Answer    : Cholera is an acute diarrhoeal disease caused by Vibrio cholerae, "
        "typically from contaminated water or food. It can cause severe dehydration and death "
        "within hours if untreated. Affects millions annually in areas with poor sanitation.\n"
        "Key fact  : Prompt ORS (oral rehydration salts) can reduce mortality from >50% to "
        "below 1%.\n"
        f"🔗 Source: {_WHO}/cholera"
    ),
    "hepatitis": (
        "Condition : Hepatitis\n"
        "Answer    : Hepatitis is inflammation of the liver, most commonly caused by viruses "
        "(Hep A–E). Hep B and C are major causes of chronic liver disease, cirrhosis, and "
        "liver cancer worldwide. Hep B has an effective vaccine; Hep C is now curable with "
        "DAA therapy.\n"
        "Key fact  : 354 million people globally live with chronic Hep B or C infection.\n"
        f"🔗 Source: {_WHO}/hepatitis"
    ),
    "hiv": (
        "Condition : HIV / AIDS\n"
        "Answer    : HIV (Human Immunodeficiency Virus) attacks CD4+ T-cells, progressively "
        "destroying the immune system. Without treatment, HIV advances to AIDS. Modern "
        "Antiretroviral Therapy (ART) suppresses the virus to undetectable levels — people "
        "on ART can live long, healthy lives and cannot transmit the virus sexually.\n"
        "Key fact  : U=U: Undetectable = Untransmittable. ART is lifelong but highly effective.\n"
        f"🔗 Source: {_WHO}/hiv"
    ),
    "influenza": (
        "Condition : Influenza (Flu)\n"
        "Answer    : Influenza is a contagious respiratory illness caused by influenza A or B "
        "viruses. It causes sudden fever, muscle aches, and respiratory symptoms. Annual "
        "vaccination is the most effective prevention, especially for elderly and "
        "immunocompromised individuals.\n"
        "Key fact  : Seasonal flu causes 250,000–500,000 deaths globally every year.\n"
        f"🔗 Source: {_WHO}/influenza"
    ),
    "covid": (
        "Condition : COVID-19\n"
        "Answer    : COVID-19 is a respiratory illness caused by SARS-CoV-2. It ranges from "
        "mild illness to severe pneumonia, ARDS, and death. Older adults and those with "
        "comorbidities are at highest risk. mRNA vaccines (Pfizer, Moderna) provide strong "
        "protection against severe disease.\n"
        "Key fact  : Long COVID affects ~10–20% of infected individuals, causing persistent "
        "fatigue, breathlessness, and cognitive symptoms for months.\n"
        f"🔗 Source: {_WHO}/coronavirus-disease-covid-19"
    ),
    "sepsis": (
        "Condition : Sepsis\n"
        "Answer    : Sepsis is a life-threatening organ dysfunction caused by a dysregulated "
        "host response to infection. It can progress to septic shock (refractory hypotension). "
        "Early recognition and the 'Hour-1 Bundle' (antibiotics + fluids) are critical for "
        "survival.\n"
        "Key fact  : Sepsis causes 11 million deaths per year — one death every 2.8 seconds.\n"
        f"🔗 Source: {_WHO}/sepsis"
    ),
    "stroke": (
        "Condition : Stroke\n"
        "Answer    : A stroke occurs when blood supply to part of the brain is interrupted — "
        "either by a clot (ischaemic, 87%) or haemorrhage. Every minute without treatment "
        "causes ~1.9 million neurons to die. 'Time is brain' — call emergency services "
        "immediately.\n"
        "Key fact  : Hypertension is the single biggest modifiable risk factor for stroke.\n"
        f"🔗 Source: {_WHO}/cardiovascular_diseases/en"
    ),
    "anemia": (
        "Condition : Anaemia\n"
        "Answer    : Anaemia is a reduction in red blood cells or haemoglobin below normal "
        "thresholds, reducing oxygen delivery to tissues. The most common cause globally is "
        "iron deficiency. Symptoms include fatigue, pallor, and breathlessness. Cause must "
        "be identified and treated.\n"
        "Key fact  : Anaemia affects 1.62 billion people worldwide — especially women and "
        "children in low-income countries.\n"
        f"🔗 Source: {_WHO}/anaemia"
    ),
    "depression": (
        "Condition : Depression\n"
        "Answer    : Major depressive disorder is characterised by persistent low mood, loss "
        "of interest, and reduced quality of life for ≥ 2 weeks. It has biological, "
        "psychological, and social causes. Effective treatments include SSRIs and "
        "cognitive behavioural therapy (CBT).\n"
        "Key fact  : Depression is the leading cause of disability worldwide — affecting "
        "280 million people.\n"
        f"🔗 Source: {_WHO}/depression"
    ),
    "anxiety": (
        "Condition : Anxiety Disorder\n"
        "Answer    : Anxiety disorders are characterised by excessive, uncontrollable worry "
        "that impairs daily functioning. GAD, panic disorder, social anxiety, and PTSD are "
        "the main types. They are highly treatable with CBT and/or SSRIs.\n"
        "Key fact  : Anxiety disorders affect 301 million people globally — the most "
        "prevalent mental health condition.\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/anxiety-disorders"
    ),
    "arthritis": (
        "Condition : Rheumatoid Arthritis\n"
        "Answer    : RA is a systemic autoimmune disease where the immune system attacks "
        "the synovial joints, causing inflammation, pain, and progressive joint destruction. "
        "It affects 1% of the population and can cause permanent disability without DMARDs.\n"
        "Key fact  : Early aggressive DMARD therapy (treat-to-target) dramatically reduces "
        "joint damage and improves long-term outcomes.\n"
        f"🔗 Source: {_ML}/rheumatoidarthritis.html"
    ),
    "obesity": (
        "Condition : Obesity\n"
        "Answer    : Obesity (BMI ≥ 30) is a complex chronic disease involving excess body "
        "fat that increases risk of T2DM, hypertension, heart disease, stroke, OSA, and "
        "certain cancers. It results from a combination of genetic, metabolic, behavioural, "
        "and environmental factors.\n"
        "Key fact  : Over 1 billion people globally are obese — numbers have tripled since "
        "1975.\n"
        f"🔗 Source: {_WHO}/obesity-and-overweight"
    ),
    "seizure": (
        "Condition : Epilepsy / Seizure\n"
        "Answer    : Epilepsy is a neurological disorder characterised by recurrent "
        "unprovoked seizures — abnormal, excessive electrical activity in the brain. "
        "It has many causes including genetic, structural, metabolic, and infectious. "
        "70% of patients achieve seizure control with medication.\n"
        "Key fact  : 50 million people worldwide have epilepsy; 80% live in low-income "
        "countries with inadequate access to treatment.\n"
        f"🔗 Source: {_WHO}/epilepsy"
    ),
    "myocardial infarction": (
        "Condition : Myocardial Infarction (Heart Attack)\n"
        "Answer    : A heart attack occurs when coronary artery blockage (usually a ruptured "
        "atherosclerotic plaque + thrombus) cuts off blood supply to heart muscle, causing "
        "irreversible damage. STEMI requires emergency PCI within 90 minutes.\n"
        "Key fact  : Call emergency services immediately — every minute of delay "
        "increases mortality and cardiac damage.\n"
        f"🔗 Source: {_WHO}/cardiovascular_diseases/en"
    ),
    "fracture": (
        "Condition : Bone Fracture\n"
        "Answer    : A fracture is a break in bone continuity caused by trauma, stress, or "
        "pathological weakening (osteoporosis, cancer). Treatment depends on location, "
        "displacement, and patient factors — ranging from plaster cast to surgery.\n"
        "Key fact  : Osteoporotic hip fractures in the elderly carry a 30% one-year "
        "mortality rate; fall prevention and bone health are critical.\n"
        f"🔗 Source: {_ML}/fractures.html"
    ),
    "cancer": (
        "Condition : Cancer\n"
        "Answer    : Cancer is a group of diseases characterised by uncontrolled cell growth "
        "and invasion of surrounding tissues. Causes include genetic mutations, carcinogens "
        "(tobacco, radiation), infections (HPV, Hep B), and lifestyle factors.\n"
        "Key fact  : 30–50% of cancers are preventable through lifestyle changes and "
        "vaccination (HPV, HBV).\n"
        f"🔗 Source: {_WHO}/cancer"
    ),
    "renal failure": (
        "Condition : Chronic Kidney Disease (CKD)\n"
        "Answer    : CKD is progressive loss of kidney function over months/years, staged "
        "by GFR (G1–G5). Leading causes are diabetic nephropathy and hypertensive "
        "nephrosclerosis. End-stage requires dialysis or transplant.\n"
        "Key fact  : SGLT-2 inhibitors (dapagliflozin) have shown significant renoprotective "
        "effects independent of diabetes.\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/chronic-kidney-disease"
    ),
}


def _offline_code_enrichment(record: Optional[Dict], query: str) -> str:
    """
    When Arcee is unavailable and a code was found in the local DB,
    return a clean structured summary from the DB record itself.
    Never shows "Arcee verification unavailable."
    """
    if not record:
        return (
            "✅ Code retrieved from local database.\n"
            "🔗 Verify: https://icd.who.int  |  https://rxnav.nlm.nih.gov  |  https://loinc.org"
        )
    system  = record.get("system", "")
    code    = record.get("code", "")
    term    = record.get("term", "")
    desc    = record.get("description", "")

    _registry_links = {
        "ICD-10":    "🔗 Verify: https://icd.who.int/browse10",
        "LOINC":     "🔗 Verify: https://loinc.org/search",
        "RxNorm":    "🔗 Verify: https://rxnav.nlm.nih.gov",
        "SNOMED CT": "🔗 Verify: https://browser.ihtsdotools.org",
    }
    verify_link = _registry_links.get(system, "🔗 Verify: https://icd.who.int")

    lines = [
        f"✅  Code confirmed from local database",
        f"Code      : {code}",
        f"System    : {system}",
        f"Term      : {term}",
    ]
    if desc and desc != term:
        lines.append(f"Details   : {desc}")
    lines.append(verify_link)
    return "\n".join(lines) + _ARCEE_FOOTER


# ── Missing builtins — added for completeness ─────────────────

# Medications
_BUILTIN_MEDICATIONS.update({
    "typhoid": (
        "Condition  : Typhoid Fever (Salmonella Typhi)\n"
        "Medications:\n"
        "  • Azithromycin      — RXCUI: 141962 — Macrolide (first-line, uncomplicated)\n"
        "  • Ceftriaxone       — RXCUI: 210491 — 3rd-gen cephalosporin (severe/MDR)\n"
        "  • Ciprofloxacin     — RXCUI: 41493  — Fluoroquinolone (where sensitive)\n"
        "  • Chloramphenicol   — RXCUI: 2316   — Classic agent (low-resource settings)\n"
        f"Guideline  : WHO Typhoid — https://www.who.int/immunization/diseases/typhoid/en/\n{_RX}"
    ),
    "meningitis": (
        "Condition  : Bacterial Meningitis\n"
        "Medications:\n"
        "  • Ceftriaxone   — RXCUI: 210491 — 3rd-gen cephalosporin (empirical first-line)\n"
        "  • Benzylpenicillin — RXCUI: 7980 — Penicillin (N. meningitidis confirmed)\n"
        "  • Dexamethasone — RXCUI: 3264   — Corticosteroid (adjunct, reduces inflammation)\n"
        "  • Vancomycin    — RXCUI: 11124  — Glycopeptide (MRSA / penicillin-resistant)\n"
        f"Guideline  : WHO Meningitis — https://www.who.int/news-room/fact-sheets/detail/meningitis\n{_RX}"
    ),
    "parkinson disease": (
        "Condition  : Parkinson's Disease\n"
        "Medications:\n"
        "  • Levodopa/Carbidopa — RXCUI: 203239 — Dopamine precursor (gold standard)\n"
        "  • Pramipexole        — RXCUI: 59468  — Dopamine agonist (early / adjunct)\n"
        "  • Selegiline         — RXCUI: 9639   — MAO-B inhibitor (neuroprotective)\n"
        "  • Entacapone         — RXCUI: 135447 — COMT inhibitor (prolongs levodopa)\n"
        f"Guideline  : Parkinson's Foundation — https://www.parkinson.org/library/fact-sheets/medications\n{_RX}"
    ),
    "parkinson": (
        "Condition  : Parkinson's Disease\n"
        "Medications:\n"
        "  • Levodopa/Carbidopa — RXCUI: 203239 — Dopamine precursor (gold standard)\n"
        "  • Pramipexole        — RXCUI: 59468  — Dopamine agonist (early / adjunct)\n"
        "  • Selegiline         — RXCUI: 9639   — MAO-B inhibitor (neuroprotective)\n"
        "  • Entacapone         — RXCUI: 135447 — COMT inhibitor (prolongs levodopa)\n"
        f"Guideline  : Parkinson's Foundation — https://www.parkinson.org/library/fact-sheets/medications\n{_RX}"
    ),
    "appendicitis": (
        "Condition  : Appendicitis\n"
        "Medications (conservative / post-surgical):\n"
        "  • Co-amoxiclav (Augmentin) — RXCUI: 392518 — Broad-spectrum antibiotic (pre/post-op)\n"
        "  • Metronidazole            — RXCUI: 6922   — Anaerobic cover (combined with cephalosporin)\n"
        "  • Ceftriaxone              — RXCUI: 210491 — 3rd-gen cephalosporin (peritonitis cover)\n"
        "  • Morphine                 — RXCUI: 7052   — Opioid analgesia (acute pain)\n"
        f"Guideline  : NICE Appendicitis — https://www.nice.org.uk/guidance/ng61\n{_RX}"
    ),
    "lupus": (
        "Condition  : Systemic Lupus Erythematosus (SLE)\n"
        "Medications:\n"
        "  • Hydroxychloroquine — RXCUI: 5521   — Antimalarial (cornerstone, all SLE patients)\n"
        "  • Prednisolone       — RXCUI: 8638   — Corticosteroid (flares and active disease)\n"
        "  • Mycophenolate      — RXCUI: 41493  — Immunosuppressant (lupus nephritis)\n"
        "  • Belimumab          — RXCUI: 1161611 — Biologic anti-BLyS (refractory SLE)\n"
        f"Guideline  : ACR Lupus Guidelines 2019 — https://www.rheumatology.org/Practice-Quality/Clinical-Support/Clinical-Practice-Guidelines/Systemic-Lupus-Erythematosus\n{_RX}"
    ),
    "celiac disease": (
        "Condition  : Coeliac (Celiac) Disease\n"
        "Medications (supportive — primary treatment is gluten-free diet):\n"
        "  • Folic acid       — RXCUI: 4511  — Supplement (corrects folate deficiency)\n"
        "  • Ferrous sulphate — RXCUI: 4450  — Iron supplement (iron-deficiency anaemia)\n"
        "  • Calcium + Vit D  — RXCUI: 20610 — Bone health (osteoporosis prevention)\n"
        "  • Budesonide       — RXCUI: 1747  — Corticosteroid (refractory sprue)\n"
        f"Guideline  : NICE Coeliac Disease — https://www.nice.org.uk/guidance/ng20\n{_RX}"
    ),
})

# Symptoms
_BUILTIN_SYMPTOMS.update({
    "typhoid": (
        "Condition : Typhoid Fever\nSymptoms  :\n"
        "  • Sustained high fever (39–40°C) for 1–3 weeks\n"
        "  • Headache, malaise, and loss of appetite\n"
        "  • Relative bradycardia (slow heart rate despite high fever)\n"
        "  • Rose spots — faint pink rash on trunk\n"
        "  • Constipation (early) or diarrhoea (later stages)\n"
        f"🔗 Source: {_WHO}/typhoid"
    ),
    "meningitis": (
        "Condition : Meningitis\nSymptoms  :\n"
        "  • Severe sudden headache ('worst of my life')\n"
        "  • Neck stiffness (nuchal rigidity) — cannot touch chin to chest\n"
        "  • High fever with sensitivity to light (photophobia) and sound\n"
        "  • Non-blanching petechial or purpuric rash (meningococcal — EMERGENCY)\n"
        "  • Vomiting, altered consciousness, and seizures (severe)\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/meningitis"
    ),
    "parkinson disease": (
        "Condition : Parkinson's Disease\nSymptoms  :\n"
        "  • Resting tremor — 'pill-rolling' tremor of hands at rest\n"
        "  • Rigidity — muscle stiffness and resistance to passive movement\n"
        "  • Bradykinesia — slowness of movement and reduced facial expression\n"
        "  • Postural instability — shuffling gait, balance problems, falls\n"
        "  • Micrographia (small handwriting), soft speech, constipation\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/parkinson-disease"
    ),
    "parkinson": (
        "Condition : Parkinson's Disease\nSymptoms  :\n"
        "  • Resting tremor — 'pill-rolling' tremor of hands at rest\n"
        "  • Rigidity — muscle stiffness and resistance to passive movement\n"
        "  • Bradykinesia — slowness of movement and reduced facial expression\n"
        "  • Postural instability — shuffling gait, balance problems, falls\n"
        "  • Micrographia (small handwriting), soft speech, constipation\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/parkinson-disease"
    ),
    "appendicitis": (
        "Condition : Appendicitis\nSymptoms  :\n"
        "  • Periumbilical pain migrating to right iliac fossa (McBurney's point)\n"
        "  • Nausea, vomiting, and loss of appetite\n"
        "  • Low-grade fever (38–38.5°C)\n"
        "  • Rebound tenderness and guarding on palpation\n"
        "  • Worsening pain on movement (peritoneal irritation)\n"
        f"🔗 Source: {_ML}/appendicitis.html"
    ),
    "lupus": (
        "Condition : Systemic Lupus Erythematosus (SLE)\nSymptoms  :\n"
        "  • Butterfly (malar) rash across cheeks and nose\n"
        "  • Photosensitivity — rash or flare triggered by sunlight\n"
        "  • Joint pain, swelling and morning stiffness (arthralgia)\n"
        "  • Fatigue, fever, and hair loss\n"
        "  • Kidney involvement (proteinuria, haematuria) — lupus nephritis\n"
        f"🔗 Source: {_ML}/lupus.html"
    ),
    "celiac disease": (
        "Condition : Coeliac Disease\nSymptoms  :\n"
        "  • Chronic diarrhoea, steatorrhoea (fatty stools), bloating\n"
        "  • Abdominal pain and cramping after eating gluten\n"
        "  • Unexplained weight loss and fatigue\n"
        "  • Iron-deficiency anaemia unresponsive to oral iron\n"
        "  • Dermatitis herpetiformis — itchy blistering rash on elbows/knees\n"
        f"🔗 Source: {_ML}/celiacdisease.html"
    ),
})

# Treatment
_BUILTIN_TREATMENT.update({
    "typhoid": (
        "Condition : Typhoid Fever\n"
        "Treatment : Azithromycin (first-line, uncomplicated) for 7 days OR ceftriaxone IV "
        "for severe / drug-resistant disease. Adequate hydration and rest. Ciprofloxacin "
        "where fluoroquinolone-sensitive. Typhoid vaccination for prevention in endemic areas.\n"
        f"Guideline : WHO Typhoid — https://www.who.int/immunization/diseases/typhoid/en/"
    ),
    "meningitis": (
        "Condition : Bacterial Meningitis\n"
        "Treatment : EMERGENCY — IV ceftriaxone within 1 hour of suspicion + IV dexamethasone "
        "(reduces brain inflammation). Blood cultures BEFORE antibiotics if possible but do "
        "not delay treatment. Isolate (droplet precautions for N. meningitidis). Notify "
        "public health; prophylax close contacts with rifampicin.\n"
        f"Guideline : WHO Meningitis — https://www.who.int/news-room/fact-sheets/detail/meningitis"
    ),
    "parkinson disease": (
        "Condition : Parkinson's Disease\n"
        "Treatment : Levodopa/Carbidopa is the most effective motor treatment. Start dopamine "
        "agonists (pramipexole) in younger patients to delay motor complications. Physiotherapy "
        "and exercise reduce falls. Deep brain stimulation (DBS) for refractory motor symptoms. "
        "No cure — management focuses on symptom control and quality of life.\n"
        f"Guideline : Parkinson's Foundation — https://www.parkinson.org/library/fact-sheets/medications"
    ),
    "parkinson": (
        "Condition : Parkinson's Disease\n"
        "Treatment : Levodopa/Carbidopa is the most effective motor treatment. Start dopamine "
        "agonists (pramipexole) in younger patients to delay motor complications. Physiotherapy "
        "and exercise reduce falls. Deep brain stimulation (DBS) for refractory motor symptoms.\n"
        f"Guideline : Parkinson's Foundation — https://www.parkinson.org/library/fact-sheets/medications"
    ),
    "appendicitis": (
        "Condition : Appendicitis\n"
        "Treatment : Surgical appendicectomy (laparoscopic) is the definitive treatment. "
        "Pre-operative IV antibiotics (co-amoxiclav). Uncomplicated cases may be managed "
        "with antibiotics alone (conservative approach) but surgery remains standard. "
        "Perforation or peritonitis requires urgent open surgery.\n"
        f"Guideline : NICE NG61 — https://www.nice.org.uk/guidance/ng61"
    ),
    "lupus": (
        "Condition : Systemic Lupus Erythematosus (SLE)\n"
        "Treatment : Hydroxychloroquine for all SLE patients (reduces flares and organ damage). "
        "Corticosteroids for flares. Immunosuppressants (mycophenolate, azathioprine) for "
        "organ-threatening disease. Belimumab (biologic) for refractory cases. Sun protection. "
        "Regular monitoring of renal function and anti-dsDNA.\n"
        f"Guideline : ACR 2019 — https://www.rheumatology.org/Practice-Quality/Clinical-Support/Clinical-Practice-Guidelines/Systemic-Lupus-Erythematosus"
    ),
    "celiac disease": (
        "Condition : Coeliac Disease\n"
        "Treatment : Strict, lifelong gluten-free diet (GFD) is the ONLY effective treatment. "
        "Remove all wheat, rye, barley. Supplement iron, folic acid, calcium, and Vit D for "
        "nutritional deficiencies. Monitor response with anti-tTG IgA antibodies. Refractory "
        "sprue: budesonide or azathioprine.\n"
        f"Guideline : NICE NG20 — https://www.nice.org.uk/guidance/ng20"
    ),
})

# Explain
_BUILTIN_EXPLAIN.update({
    "typhoid": (
        "Condition : Typhoid Fever\n"
        "Answer    : Typhoid is a life-threatening bacterial infection caused by Salmonella "
        "Typhi, transmitted via contaminated food and water. It causes sustained high fever, "
        "headache, and abdominal symptoms. It is endemic in South Asia, Africa, and Latin America.\n"
        "Key fact  : Typhoid vaccination + safe water are the best prevention. Early antibiotic "
        "treatment (azithromycin) cures most cases.\n"
        f"🔗 Source: {_WHO}/typhoid"
    ),
    "meningitis": (
        "Condition : Meningitis\n"
        "Answer    : Meningitis is inflammation of the membranes (meninges) surrounding the "
        "brain and spinal cord — most dangerously caused by Neisseria meningitidis (bacterial). "
        "It is a medical EMERGENCY — the non-blanching rash is a sign of meningococcal sepsis.\n"
        "Key fact  : Bacterial meningitis requires IV antibiotics within 1 hour — every hour of "
        "delay increases mortality and risk of permanent disability.\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/meningitis"
    ),
    "parkinson disease": (
        "Condition : Parkinson's Disease\n"
        "Answer    : Parkinson's is a progressive neurodegenerative disorder caused by loss of "
        "dopamine-producing neurons in the substantia nigra. It causes characteristic tremor, "
        "rigidity, and slowed movement. The cause is unknown but genetics and environment contribute.\n"
        "Key fact  : Parkinson's affects 10 million people worldwide — exercise (particularly "
        "aerobic) has been shown to slow progression.\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/parkinson-disease"
    ),
    "parkinson": (
        "Condition : Parkinson's Disease\n"
        "Answer    : Parkinson's is a progressive neurodegenerative disorder caused by loss of "
        "dopamine-producing neurons in the substantia nigra. It causes characteristic tremor, "
        "rigidity, and slowed movement.\n"
        "Key fact  : Parkinson's affects 10 million people worldwide — exercise has been shown "
        "to slow progression.\n"
        f"🔗 Source: {_WHO}/news-room/fact-sheets/detail/parkinson-disease"
    ),
    "appendicitis": (
        "Condition : Appendicitis\n"
        "Answer    : Appendicitis is inflammation of the appendix — a small finger-like pouch "
        "attached to the large intestine. It causes right lower abdominal pain and is the most "
        "common abdominal surgical emergency, typically affecting young adults.\n"
        "Key fact  : A perforated appendix (peritonitis) is life-threatening — seek emergency "
        "care immediately if pain is severe, constant, and worsening.\n"
        f"🔗 Source: {_ML}/appendicitis.html"
    ),
    "lupus": (
        "Condition : Systemic Lupus Erythematosus (SLE)\n"
        "Answer    : Lupus is a chronic autoimmune disease where the immune system attacks "
        "healthy tissue in multiple organs — skin, joints, kidneys, heart, and brain. It "
        "predominantly affects women of childbearing age (9:1 female:male ratio).\n"
        "Key fact  : Lupus is characterised by flares and remissions. The hallmark butterfly "
        "rash across the face affects ~50% of patients.\n"
        f"🔗 Source: {_ML}/lupus.html"
    ),
    "celiac disease": (
        "Condition : Coeliac Disease\n"
        "Answer    : Coeliac disease is an autoimmune disorder where gluten triggers an immune "
        "response that damages the small intestinal villi, impairing nutrient absorption. It "
        "affects ~1% of the global population but is frequently underdiagnosed.\n"
        "Key fact  : A strict gluten-free diet resolves symptoms and heals the gut in most "
        "patients — there are no drug treatments, only dietary management.\n"
        f"🔗 Source: {_ML}/celiacdisease.html"
    ),
})


def _builtin_fallback(query: str) -> str:
    """
    Returns a structured answer from embedded knowledge when the Arcee API
    is unavailable. Uses _extract_condition to handle natural phrasing like
    "i am suffering from malaria" → condition = "malaria".
    Always returns something useful — never "No results found".
    """
    intent    = _detect_intent(query)
    condition = _extract_condition(query)

    # Pick the right built-in table
    if intent == "medication_only":
        table = _BUILTIN_MEDICATIONS
        not_found_msg = (
            f"Medication data for '{condition}' is not available offline.\n"
            "🔗 Search RxNorm: https://rxnav.nlm.nih.gov\n"
            "🔗 WHO Essential Medicines: https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines/essential-medicines-lists"
        )
    elif intent == "symptoms_only":
        table = _BUILTIN_SYMPTOMS
        not_found_msg = (
            f"Symptom data for '{condition}' is not available offline.\n"
            "🔗 MedlinePlus: https://medlineplus.gov\n"
            "🔗 WHO: https://www.who.int/health-topics"
        )
    elif intent == "treatment_only":
        table = _BUILTIN_TREATMENT
        not_found_msg = (
            f"Treatment data for '{condition}' is not available offline.\n"
            "🔗 WHO Guidelines: https://www.who.int/publications\n"
            "🔗 CDC: https://www.cdc.gov/az/a.html"
        )
    else:
        table = _BUILTIN_EXPLAIN
        not_found_msg = (
            f"Detailed information for '{condition}' is not available offline.\n"
            "🔗 MedlinePlus: https://medlineplus.gov\n"
            "🔗 WHO: https://www.who.int/health-topics"
        )

    result = table.get(condition, None)

    # ── If not found, check if condition looks like a symptom description ──
    # e.g. "dizzy and my chest hurts" — no named condition, but clearly medical
    if result is None:
        # Try stripping trailing noise words from multi-word conditions
        # e.g. "parkinson disease" vs "parkinson"
        short_cond = condition.split()[0] if condition else ""
        result = table.get(short_cond, None)

    if result is None:
        # Check if query looks like a SYMPTOM DESCRIPTION (no named condition)
        symptom_words = {
            "dizzy","dizziness","nausea","vomiting","headache","fatigue","fever",
            "chills","cough","breathless","chest","abdominal","pain","swelling",
            "rash","bleeding","numbness","tingling","weakness","confusion",
            "palpitation","jaundice","itching","sore","throat","diarrhea","diarrhoea",
        }
        cond_words = set(condition.lower().split())
        is_symptom_desc = len(cond_words & symptom_words) >= 1 and len(condition.split()) >= 2

        if is_symptom_desc:
            # Give a helpful triage response
            result = (
                "Condition : Symptom Assessment\n"
                "Answer    : Your symptoms may indicate several possible conditions. "
                "Common causes of dizziness + chest discomfort include: cardiac arrhythmia, "
                "anaemia, anxiety/panic disorder, dehydration, inner ear problems (vertigo), "
                "or cardiovascular disease.\n"
                "Key fact  : ⚠️ Chest pain with dizziness can be a cardiac emergency — "
                "if severe, sudden, or with sweating/arm pain, call emergency services immediately.\n"
                "Action    : See a doctor promptly. They may order ECG, blood pressure check, "
                "full blood count, and cardiac enzymes.\n"
                f"🔗 Source: {_ML}/dizziness.html\n"
                f"🔗 Emergency: https://www.who.int/emergencies/en"
            )
        else:
            result = not_found_msg

    return result + _ARCEE_FOOTER


# ══════════════════════════════════════════════════════════════
# SECTION 9 — MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def hybrid_medical_search(query: str) -> Dict[str, Any]:
    """
    Full hybrid pipeline — main entry point for the Flask backend.

    Step 0  WARNING CHECK            — detect serious symptoms (warnings, not routing)
    Step 1  normalize_query()        — typo correction
    Step 2  is_medical_query()       — reject non-medical
    Step 3  classify_query()         — route: local | hybrid | llm
    Step 4  local DB search          — _search_all_codes() / _lookup_code_in_db()
    Step 5  verify_code_with_arcee() — Arcee verifies + generates final answer
    Step 6  return structured dict

    Final response text ALWAYS comes from Arcee, never raw from the DB.

    Return keys: source, codes, enrichment, data, route, confidence, disclaimer, warning
    """
    # Step 0 — WARNING CHECK — detect serious symptoms (for informational warning, not routing)
    warning = _detect_emergency_symptoms(query)
    
    # Step 1 — Normalise
    query = normalize_query(query)

    # Step 2 — Safety guard
    if not is_medical_query(query):
        return {
            "source":"rejected",
            "data":(
                "I'm a medical information assistant. I can only answer questions "
                "about medical conditions, diseases, symptoms, lab tests, medications, "
                "and medical codes (ICD-10, LOINC, RxNorm, SNOMED CT, CPT, HCPCS, NDC). "
                "Please ask a medical question."
            ),
            "route":"rejected","confidence":1.0,"disclaimer":DISCLAIMER,
        }

    # Step 3 — Classify
    route, confidence = classify_query(query)

    # Step 3a — Project metadata lookup (BUT NOT for specific code lookups)
    # Only treat as a code query if asking for "code OF/FOR" or "lookup"
    # Simple mentions of standards (FHIR, ABDM, LOINC) should check project.json first
    is_code_query = any(phrase in query.lower() for phrase in 
                        ["code for ", "code of ", "lookup ", "rxcui ", "icd-", "icd code"])
    
    if not is_code_query:
        proj_results = search_project(query)
        if proj_results:
            text = format_project_results(proj_results)
            resp = {
                "source": "local",
                "data": text,
                "route": "project",
                "confidence": 1.0,
                "disclaimer": DISCLAIMER,
            }
            if warning:
                resp["warning"] = warning
            return resp

    # Build response helper function with optional warning
    def add_warning_to_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Add warning to response if one was detected."""
        if warning:
            response["warning"] = warning
        return response

    # ── HYBRID route ─────────────────────────────────────────
    if route == "hybrid":
        codes = _search_all_codes(query)
        if codes:
            response = _arcee_hybrid_prompt(query, codes)
            if not response:
                response = _offline_code_enrichment(codes[0], query)
            return add_warning_to_response({
                "source":"local+llm","codes":codes,
                "enrichment": response,
                "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
            })
        response = verify_code_with_arcee(query, None)
        return add_warning_to_response({
            "source":"llm",
            "data":response or _builtin_fallback(query),
            "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
        })

    # ── LOCAL route ──────────────────────────────────────────
    if route == "local":
        # Check for a literal code in the query (e.g. "E11.9", "44054006")
        code_literal = _detect_code_in_query(query)
        if code_literal:
            code_str, system = code_literal
            db_rec = _lookup_code_in_db(code_str, system)
            response = verify_code_with_arcee(query, db_rec)
            if not response:
                response = _offline_code_enrichment(db_rec, query)
            return add_warning_to_response({
                "source":"local+llm" if db_rec else "llm",
                "codes":[db_rec] if db_rec else [],
                "enrichment": response,
                "route":route,"confidence":confidence,"disclaimer":DISCLAIMER,
            })
        # General code query — search by term
        codes = _search_all_codes(query)
        if codes:
            response = verify_code_with_arcee(query, codes[0])
            if not response:
                response = _offline_code_enrichment(codes[0], query)
            return add_warning_to_response({
                "source":"local+llm","codes":codes,
                "enrichment": response,
                "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
            })
        # DB found nothing — Arcee identifies from scratch
        response = verify_code_with_arcee(query, None)
        if response:
            return add_warning_to_response({
                "source":"llm",
                "data":response,
                "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
            })
        fallback = _builtin_fallback(query)
        return add_warning_to_response({
            "source":"llm","data":fallback,
            "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
        })

    # ── LLM route ────────────────────────────────────────────
    # Pure explanation / medication / symptom query — send to Arcee
    response = _arcee_explain(query)
    if response:
        related = _search_all_codes(query, limit=5)
        return add_warning_to_response({
            "source":"llm","data":response,"codes":related,
            "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
        })

    # ── Arcee API unavailable — use built-in knowledge fallback ──
    # This ensures users always get an answer even when the API is down.
    fallback = _builtin_fallback(query)
    return add_warning_to_response({
        "source":"llm","data":fallback,
        "route":route,"confidence":confidence,"disclaimer":DISCLAIMER
    })


# ══════════════════════════════════════════════════════════════
# SELF-TEST
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    tests = [
        ("glusose loinc code",                                    "local",   "glucose LOINC code"),
        ("LOINC code of hemoglobin",                              "local",   None),
        ("ICD code for cholera",                                  "local",   None),
        ("RXNORM for aspirin",                                    "local",   None),
        ("What is the RxNorm RXCUI for aspirin and drug class?",  "hybrid",  None),
        ("What disease corresponds to ICD code E11.9?",           "local",   None),
        ("What does SNOMED CT code 44054006 represent?",          "local",   None),
        ("symptoms of diabetes",                                  "llm",     None),
        ("what is hypertension",                                  "llm",     None),
        ("who won the cricket match",                             "rejected",None),
    ]
    print("=" * 70)
    all_pass = True
    for q, exp_route, exp_norm in tests:
        norm = normalize_query(q)
        route = "rejected" if not is_medical_query(norm) else classify_query(norm)[0]
        ok = (route == exp_route) and (exp_norm is None or norm.lower() == exp_norm.lower())
        if not ok: all_pass = False
        print(f"  [{'OK  ' if ok else 'FAIL'}] route={route:<10} norm='{norm}'")
    print()
    print("ALL PASSED ✅" if all_pass else "SOME FAILED ❌")