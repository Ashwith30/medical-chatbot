# Manual Fix Instructions for search.py

Due to IDE auto-formatting issues that keep converting 4-space indentation to 3-space, you'll need to manually fix the indentation in the file. Here's what to do:

## Step 1: Open search.py in a text editor (Notepad++, VS Code, or similar)

## Step 2: Fix Indentation Errors

Find and fix these lines(they have 3 spaces instead of 4):

### Line ~196 (in load_loinc_data function):
Change: `  try:`  (3 spaces)
To:     `   try:` (4 spaces)

Also fix all lines inside this try block to maintain consistent 4-space indentation:
```python
def load_loinc_data() -> List[Dict]:
    """Load LOINC data from JSON file"""
    global _database_available
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
   loinc_data = []
    
   try:  # <-- Make sure this has 4 spaces
       loinc_path = os.path.join(data_dir, 'loinc.json')  # 8 spaces
        if os.path.exists(loinc_path):  # 8 spaces
            with open(loinc_path, 'r',encoding='utf-8') as f:  # 12 spaces
               loinc_data = json.load(f)  # 12 spaces
            
            if loinc_data:  # 12 spaces
                _database_available = True  # 12 spaces
        return loinc_data  # 8 spaces
    except Exception as e:  # 4 spaces
        print(f"Warning: Error loading LOINC data: {e}")  # 8 spaces
        _database_available = False  # 8 spaces
        return []  # 8 spaces
```

### Line ~215 (in load_project_terminology function):
Change: `  try:`  (3 spaces)
To:     `   try:` (4 spaces)

Fix the entire function:
```python
def load_project_terminology() -> Dict[str, Any]:
    """Load medical coding terminology from project.json"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    
   try:  # <-- Make sure this has 4 spaces
        project_path = os.path.join(data_dir, 'project.json')
        if os.path.exists(project_path):
            with open(project_path, 'r',encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Error loading project terminology: {e}")
    
    return {}
```

## Step 3: Verify All New Functions Are Present

Make sure these functions exist in the file (should be before `search_rxnorm`):

1. `load_loinc_data()` - Loads LOINC data from loinc.json
2. `load_project_terminology()` - Loads medical terminology from project.json  
3. `search_loinc()` - Searches LOINC database for lab codes
4. `autocorrect_medical_term()` - Corrects spelling mistakes in medical terms
5. `get_medical_terminology_info()` - Gets info about medical coding standards

## Step 4: Update search_medical_codes Function

Find the `search_medical_codes` function and add LOINC search:

```python
def search_medical_codes(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    
    # ADD THIS BEFORE SNOMED search:
    # Search LOINC data for LOINC queries or lab test queries
    if any(kw in query_lower for kw in ['loinc', 'laboratory', 'lab test', 'clinical observation']):
       loinc_results = search_loinc(query, limit=limit)
        all_results.extend(loinc_results)
    
    # Search SNOMED CT data for SNOMED queries or numeric codes
    if any(kw in query_lower for kw in ['snomed', 'sct']) or re.search(r'\b\d{6,18}\b', query):
        snomed_results = search_snomed(query, limit=limit)
        all_results.extend(snomed_results)
    
    # ... rest of function ...
```

## Step 5: Test Compilation

Run this command to check if indentation is correct:
```bash
python -m py_compile "c:\Users\Hp\OneDrive\Desktop\Medical ChatBot\engine\search.py"
```

If no errors appear, success! If there are still indentation errors, go back to Step 2.

## Step 6: Test the Functionality

Test LOINC search:
```python
from engine.search import search_loinc, autocorrect_medical_term, get_medical_terminology_info

# Test LOINC search
results = search_loinc("glucose", limit=3)
for r in results:
    print(f"{r['code']}: {r['term']}")

# Test autocorrect
corrected = autocorrect_medical_term("glusose", ["glucose", "hemoglobin"])
print(f"Corrected 'glusose' to: {corrected}")

# Test terminology lookup
info = get_medical_terminology_info("LOINC")
print(f"LOINC description: {info['description'][:100]}")
```

## Summary of Features Added

1. **LOINC Code Support**: Can now search LOINC laboratory test codes from loinc.json
2. **Project.json Integration**: Medical coding terminology explanations come from project.json
3. **Autocorrect**: Spelling mistakes in medical terms are automatically corrected using difflib
4. **Enhanced Query Classification**: LOINC patterns added to detect lab test queries
5. **Terminology Information**: Get detailed info about medical coding standards (LOINC, RxNorm, SNOMED CT, ICD, FHIR, etc.)

## Example Usage

```python
from engine.search import hybrid_medical_search, autocorrect_medical_term

# Autocorrect misspelled input
user_input = "glusose test loinc code"
corrected_input = autocorrect_medical_term(user_input, ["glucose", "test", "loinc", "code"])

# Search with corrected input
result = hybrid_medical_search(corrected_input)
print(result)
```
