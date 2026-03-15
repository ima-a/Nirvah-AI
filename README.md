# Nirvaah AI

Nirvaah AI is an intelligent healthcare data processing pipeline designed to assist ASHA (Accredited Social Health Activist) workers in India. The system allows workers to log health visits and patient data using WhatsApp (via Twilio), processes the input using a multi-agent AI pipeline, and syncs the structured data to government health databases.

## 🌟 Key Features

- **WhatsApp Integration:** ASHA workers can send text, voice notes, or photos of printed official documents directly to a Twilio WhatsApp number.
- **Multi-Modal Input Processing:** 
   - **Voice:** Transcribed accurately using ElevenLabs.
   - **Text:** Normalised for clinical data extraction.
   - **Image (OCR):** Printed documents (Aadhaar, BPL cards, health forms) are scanned using Tesseract OCR with dual English and Malayalam support.
- **Intelligent Pipeline (LangGraph):** The core logic is orchestrated through an advanced multi-agent system built on LangGraph.
- **Automated Validation:** Cross-checks clinical data (like BP, Hemoglobin) against Kerala state protocol validation rules.
- **Anomaly Detection:** Flags suspicious submission patterns using a locally-trained IsolationForest model.
- **Dropout Risk Insights:** Predicts the risk of patients dropping out of care programs using an XGBoost classifier and checks eligibility for government schemes.
- **Interactive Dashboard:** A React frontend (`dashboard/`) provides real-time monitoring and analytics.

## 🏗️ Architecture

The backend is built with **FastAPI** and **LangGraph**, and is divided into several specialised agents:

1. **Extraction Agent:** Uses Groq to extract structured clinical fields from raw transcripts or OCR data.
2. **Validation Agent:** Validates clinical ranges and checks for missing or anomalous data based on state protocols.
3. **Clarification Agent:** (Optional hook) Prompts the ASHA worker for missing or unclear information via WhatsApp.
4. **Form Mapping Agent:** Maps extracted fields into formats required by government registries (e.g., HMIS, MCTS, Kerala HIMS).
5. **Sync Agent:** Saves the validated record to Supabase and manages database synchronisation.
6. **Anomaly Detection Agent:** Uses an IsolationForest model mapped over metadata to flag potentially fraudulent or accidental bulk submissions.
7. **Insights Agent:** Uses an XGBoost model to compute a patient's dropout risk and evaluates eligibility for health schemes. Generates a readable summary via Groq.

## 📂 Repository Structure

The repository is structured to seamlessly support deployment to services like Render:

```
Nirvah-AI/
├── Procfile                    # Render entry point command
├── requirements.txt            # Python dependencies
├── app/                        # FastAPI backend and LangGraph pipeline
│   ├── agents/                 # Individual AI node definitions
│   ├── main.py                 # FastAPI application
│   ├── webhook.py              # Twilio WhatsApp webhook endpoint
│   ├── pipeline.py             # LangGraph state machine builder
│   └── ...                    
├── dashboard/                  # React + Vite frontend dashboard
├── docs/                       # Agent and pipeline documentation
├── data/                       # Validation rules, prompt templates, and schema definitions
├── models/                     # Pre-trained ML models (Anomaly Detection, XGBoost)
├── scripts/                    # Scripts for training models and manual validation
└── tests/                      # Pytest suite for the pipeline and agents
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for the dashboard)
- **Tesseract OCR:** Required to process printed documents. Must be installed with English (`eng`) and Malayalam (`mal`) language packs.
- API Keys: Twilio, Supabase, Groq, ElevenLabs.

### Environment Variables

Create a `.env` file at the root of the project drawing from `.env.example`:

```ini
# FastAPI
PORT=8000
ENVIRONMENT=development

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_SANDBOX_NUMBER=whatsapp:+14155238886

# Supabase
SUPABASE_URL=your_project_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# AI Providers
GROQ_API_KEY=your_groq_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

### Running the Backend

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the FastAPI server (uses Uvicorn):
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Running the Frontend Dashboard

1. Navigate to the dashboard directory:
   ```bash
   cd dashboard
   ```
2. Install Node modules:
   ```bash
   npm install
   ```
3. Start the dev server:
   ```bash
   npm run dev
   ```

## 🧪 Testing

The backend includes a comprehensive pytest suite to verify extraction correctness, clinical validation, sync logic, and LangGraph connectivity.

Run the test suite from the root directory:
```bash
pytest tests/ -v
```

## ⚙️ Deployment

This project is configured out-of-the-box for **Render**. 
- The root `Procfile` uses the command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Make sure to attach a disk or handle the `models/` directory correctly, and ensure that `tesseract-ocr`, `tesseract-ocr-eng`, and `tesseract-ocr-mal` are installed in your deployment environment if you intend to use the image OCR capabilities.
