
# Facilitron-ready School Scheduler (Low-impact)

## What this does
- Upload a Notion-exported CSV of schools (`school_name, school_url` min)
- Low-impact crawl (homepage only) → AI chooses **Bell** & **Calendar** links
- Download those 2 pages, extract text (HTML/PDF)
- Parse dismissal times + no-school dates
- Build weekly schedule candidates within your quarter dates
- **Evenly spread** assignments across weekdays (soft caps + penalty)
- Export **Facilitron-ready CSV**
- Test
## Quickstart
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Optional: OpenAI link picker
Set `OPENAI_API_KEY` env var to enable LLM link picking. Without it, heuristics are used.

```bash
export OPENAI_API_KEY=sk-...   # Windows: setx OPENAI_API_KEY your_key
```

## Inputs
- CSV with columns: `school_name, school_url`
- UI settings: quarter start/end, buffer, session duration, target/min sessions
- Even spread: per-weekday soft caps + penalty α

## Output
- `facilitron_ready_schedule.csv` including:
  - recommended day/time
  - start/end dates
  - total sessions
  - excluded dates (holidays)
  - bell & calendar URLs
  - diagnostics (dismissal map, term window, etc.)

## Notes
- Requests per school: ~3 (homepage + 2 chosen pages)
- PDF calendars parsed via PyPDF2 (scanned PDFs may need OCR outside scope)
- If parsing weak, adjust quarter dates or add avoid dates manually.

## Safety
- Respect robots.txt, reasonable delays, and domain rate limits.


## VS Code Setup
1. **Open Folder**: File → Open Folder → select this project.
2. **Create venv** (recommended):
   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows
   .venv\Scripts\activate
   ```
3. **Install deps**:
   ```bash
   pip install -r requirements.txt
   ```
4. **(Optional) OpenAI key**:
   - Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
5. **Run**:
   - Press **F5** or go to **Run and Debug** → **Run Streamlit app**.
   - Or in terminal: `streamlit run app.py`.
