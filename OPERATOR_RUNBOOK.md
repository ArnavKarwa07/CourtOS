# CourtOS Operator Runbook & Documentation

This runbook guides operators and developers through starting, seeding, using, and troubleshooting CourtOS.

---

## 1. Getting Started (Local Run)

### 1.1 Prerequisite Check
Ensure you have Python 3.12+ and Node.js 22+ installed.

### 1.2 Running Backend & Frontend Jointly
1. In the root directory, install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Build the frontend client:
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
3. Start the combined FastAPI production server:
   ```bash
   python -m uvicorn courtos.app:app --host 127.0.0.1 --port 8000
   ```
   *Note: FastAPI dynamically serves the static assets same-origin from the `/frontend/dist` folder when it exists.*

---

## 2. Seeding & Mocking CLI

You can seed the database with mock events using the seed command:
```bash
python -m courtos.seed --count 150
```
This inserts a batch of kinematic, network, and game state events into the active database configured by `COURTOS_DB_URL`.

---

## 3. Keyboard Operator Navigation Map

CourtOS is designed for screen readers and keyboard-only operators. Tab order flows in a logical 2-column pattern:

1. **Header**: Theme toggler (Light/Dark).
2. **Game Status**: Informative only (skipped by keyboard focus, read via headings).
3. **Active Incidents List**: 
   - Focus lands on the first active incident card.
   - Operators can press `Tab` to navigate to the "Resolve" button on that card.
   - Pressing `Enter` or `Space` resolves the incident immediately (using Optimistic UI). Focus naturally shifts to the next card's resolve button.
4. **Court Overlay Controls**:
   - Focus lands on the active overlay chips (remove buttons). Press `Enter` to remove.
   - Tab to the "Enter overlay ID" text input, type the name, and tab to "Add" button and press `Enter`.
5. **Network recommendations**:
   - Focus lands on the "Recalculate Allocations" button. Press `Enter` to force-recalculate.
6. **Telemetry Feed**: Scrollable list (skipped by tab order to avoid keyboard traps; read via screen reader document virtual cursor).

---

## 4. API & Swagger Verification
Verify direct API contracts and Swagger UI here:
* **Interactive OpenAPI Specs**: `http://127.0.0.1:8000/docs` (Swagger)
* **Alt Interactive Specs**: `http://127.0.0.1:8000/redoc` (Redoc)
* **Raw Schema Contract**: `http://127.0.0.1:8000/openapi.json`
* **Raw Health Payload**: `http://127.0.0.1:8000/api/v1/health`

---

## 5. Troubleshooting & Stale States

### 5.1 SSE Connection Disconnected
* **Symptom**: SSE status displays `DISCONNECTED` or `RECONNECTING` (red indicator) and toasts stack up.
* **Fix**: The client automatically retries connection using exponential backoff. Check if the backend uvicorn process is still running. Once restored, the frontend automatically receives the latest `state_snapshot` payload and reconciles.

### 5.2 SQLite WAL Locking
* **Symptom**: Database writes block or return database locked exceptions.
* **Fix**: SQLite adapter automatically configures WAL mode. If contention persists, verify that no other external tools (like database browsers) hold exclusive write locks on `./data/courtos.db`.
