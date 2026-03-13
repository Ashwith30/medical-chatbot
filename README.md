# Medical ChatBot Application

A Flask-based medical chatbot that provides medical information search functionality using ICD-10 medical data.

## Features

- 🔍 **Medical Search**: Search through comprehensive ICD-10 medical database
- �️ **Project Metadata Lookup**: Ask about FHIR, ABDM, HL7, Mirth Connect, OCR, DigiYatra, and other standards defined in `data/project.json`
- �💬 **Chat Interface**: Clean, user-friendly chat interface with Apple-inspired design
- 🏥 **Medical Information**: Provides medical terms, codes, and descriptions
- ⚠️ **Disclaimer System**: Clear medical disclaimer for responsible use
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🔧 **Keyboard Shortcuts**: Ctrl/Cmd + K to focus search, Enter to submit

## Project Structure

```
Medical ChatBot/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── Templates/             # HTML templates
│   └── index.html        # Main chat interface
├── Static/               # Static assets
│   ├── styles-light.css  # Styling
│   ├── medical-lookup.js # Medical search logic
│   └── script.js         # Main application script
├── engine/               # Search engine module
│   ├── __init__.py       # Package initializer
│   └── search.py         # Search functionality
└── data/                 # Data files
    └── record.json       # ICD-10 medical data
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

The `.env` file contains:
```
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production
```

If you want the application to automatically query the Grok API when a question
is not present in the local medical dataset, add the following variables:
```
GROK_API_KEY=your_grok_api_key_here
# optional: override default endpoint if your provider uses a different URL
GROK_API_URL=https://api.openai.com/v1/completions
```
The Grok fallback will only be used for queries that return no results locally,
and the request is constrained by a prompt that instructs the model to stay
within the medical domain. Do **not** use this service for non‑medical queries.

### 3. Run the Application

```bash
python app.py
```

The application will be available at: http://127.0.0.1:5000

## API Endpoints

- `GET /` - Serve the main chat interface
- `POST /search` - Search medical records (JSON: `{"query": "search term"}`)
- `GET /health` - Health check endpoint

## How It Works

1. **User Input**: Users enter medical questions in the chat interface
2. **Query Processing**: The system preprocesses and cleans the search query
3. **Database Search**: Searches through the ICD-10 medical database
4. **Relevance Scoring**: Uses text similarity to rank results
5. **Response Formatting**: Formats results with medical information and disclaimer

## Example Usage

Ask questions like:
- "What is cholera?"
- "Typhoid fever symptoms"
- "ICD code for diabetes"
- "Malaria treatment"
- "Tell me about FHIR" (reads from project.json)
- "What is ABDM?" (metadata lookup)
- "Explain HL7" or "Describe Mirth Connect"

## Important Disclaimer

⚠️ **This application is for educational purposes only and should not replace professional medical advice, diagnosis, or treatment. Always consult with qualified healthcare providers for medical concerns.**

## Development Notes

- The search engine uses fuzzy text matching for better results
- Results are limited to 10 items by default
- Similarity threshold is set to 0.3 (adjustable in `engine/search.py`)
- The application includes proper error handling and logging

## Customization

### Adjust Search Sensitivity
In `engine/search.py`, modify the similarity threshold:
```python
if score > 0.3:  # Lower = more results, Higher = more precise
```

### Modify Result Limit
```python
def search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
```

### Update Styling
Modify `Static/styles-light.css` for visual changes

## Troubleshooting

### Common Issues

1. **Module Import Errors**: Ensure all dependencies are installed
2. **File Not Found**: Check that `data/record.json` exists
3. **CORS Issues**: Flask-CORS is configured for all routes
4. **Static Files Not Loading**: Check file paths in templates

### Debug Mode

Enable detailed logging by setting `FLASK_DEBUG=True` in `.env`

## Security Considerations

- Change the `SECRET_KEY` in production
- Use a production WSGI server (Gunicorn, uWSGI) for deployment
- Implement rate limiting for production use
- Consider adding input validation and sanitization

## License

This is a demonstration application. Use responsibly and ensure compliance with medical data regulations in your jurisdiction.