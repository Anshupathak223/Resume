# TalentLens — Resume screening

A React workspace for comparing resumes with job descriptions. Resume extraction, PII redaction, and scoring use the existing Python screening engine; the browser never receives the Gemini API key.

## Run locally

1. Add `GEMINI_API_KEY=...` to `.env` (see `.env.example`).
2. Install the Python dependencies and start the API:

   ```powershell
   python -m pip install -r requirements.txt
   uvicorn server:app --reload
   ```

3. In another terminal, install and start the React app:

   ```powershell
   npm install
   npm run dev
   ```

Open the local URL printed by Vite (usually `http://localhost:5173`). The development server forwards `/api` requests to the Python service on port 8000.

## Included

- Resume screening for PDF, DOCX, and TXT files, with optional contact detail redaction.
- Match breakdowns, candidate search, filters, recruiter decisions, private notes, and side-by-side comparison.
- Candidate CSV export and score and skill-gap analytics.
- Recruiter decisions and notes saved in the current browser's local storage.

## M17 candidate status and notifications

Candidate status and notification history are stored in `data/talentlens.sqlite3` (or the path in `CANDIDATE_DB_PATH`). The generated database directory is git-ignored. Candidate rows include `status` and `status_updated_at`; the lifecycle is Applied, Under Review, Shortlisted, Interview Scheduled, Rejected, and Hired.

- `PATCH /api/candidates/{candidate_id}/status` updates one candidate.
- `POST /api/candidates/status/bulk` accepts `{"candidate_ids": [1, 2], "status": "Shortlisted"}`.
- `GET /api/notifications?limit=50` returns recent notification history; `candidate_id` can scope it to one candidate.
- Status changes to Shortlisted, Interview Scheduled, and Rejected create a simulated email and a history row. No real email is sent.

The simulated sender and the three templates are in `notifications.py`; status orchestration is centralized in `update_candidate_status`. `candidate_store.py` owns SQLite persistence. For real delivery later, replace `send_simulated_email` with an SMTP or provider adapter and keep credentials in `.env` environment variables. `.env` is listed in `.gitignore`.

Screened resumes with no detectable email can still be status-tracked. If they move into a notifying status, that status is saved, a failed notification is recorded, and the reason is shown in history. Repeating the current status is a no-op and does not send another message. Backward transitions are allowed; moving to a notifying status after another transition creates a new notification.

Candidate results saved in browser storage before M17 have no database ID or stored contact email. Screen those resumes again to register them for status tracking and notification history.

Match scores are job-related decision support. They are not hiring decisions.
