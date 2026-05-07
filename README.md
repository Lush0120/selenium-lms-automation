# 🤖 Moodle LMS Automation Tool

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-WebDriver-43B02A?style=flat&logo=selenium&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat)
![python-docx](https://img.shields.io/badge/python--docx-document%20generation-2B579A?style=flat)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen?style=flat)

> Automation tool that reduced a 7-minute manual process to under 30 seconds — a **93% performance improvement** — for an e-learning platform managing technical assessments at scale.

**[▶ Watch the demo](#demo)**

---

## The Problem It Solves

Managing technical assessments on a Moodle-based e-learning platform required an operator to manually:

- Search or create a candidate user
- Set access credentials and time windows
- Enroll the user in multiple courses
- Clear previous quiz attempts
- Generate a Word document with access details to send by email

For each candidate, this took **~7 minutes** of repetitive clicking. With dozens of candidates per day, it became a significant bottleneck.

---

## The Solution

A Python automation tool that handles the entire flow end-to-end:

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Login + session setup | ~25s | ~5s | 80% |
| User search | ~30s | ~7s | 77% |
| Password update | ~40s | ~11s | 72% |
| Clear quiz attempts (none) | ~60s | ~2s | 97% |
| Clear quiz attempts (existing) | ~90s | ~5s | 94% |
| Participant filter | ~100s | ~3s | 97% |
| Enroll / reactivate | ~84s | ~8s | 90% |
| Document generation | N/A | ~1s | ✨ |
| **Total (1 test, 2 quizzes)** | **~7 min** | **~25–30s** | **~93%** |

---

## Features

- ✅ User creation and management (create or update existing)
- ✅ Course catalog synchronization (local cache)
- ✅ Enrollment and reactivation
- ✅ Technical and diagnostic test assignment
- ✅ Automatic quiz attempt cleanup
- ✅ Professional Word document generation with dynamic tables
- ✅ Multi-candidate loop (no re-login required)
- ✅ Automatic SMOWL modal dismissal
- ✅ Search filter cleanup between candidates
- 🔄 Batch processing from Excel (in development)
- 🔄 Automated email via n8n webhook (pending)
- 🔄 Results export to Excel (pending)
- 🔄 GUI interface with Tkinter/PyQt (pending)

---

## Demo

[![Demo Video](https://img.youtube.com/vi/kby2bmafZKw/maxresdefault.jpg)](https://youtu.be/kby2bmafZKw)

> 🎬 **[Watch full demo on YouTube](https://youtu.be/kby2bmafZKw)**

The demo shows the full flow: login → candidate lookup/creation → test assignment → document generation, processing a candidate in under 30 seconds.

---

## Architecture

The project follows **Atomic Design** adapted for backend automation, separating concerns into atoms (core utilities), molecules (specific operations), and organisms (business flows).

```
moodle-automation/
│
├── core/                     # Atoms: base utilities
│   ├── config.py             # Centralized configuration
│   ├── exceptions.py         # Custom exceptions
│   ├── logger.py             # Colored logging with rotation
│   └── browser.py            # WebDriver management (optimized)
│
├── components/               # Molecules: specific operations
│   ├── auth.py               # Authentication (login/logout)
│   ├── user.py               # User management
│   ├── course.py             # Course management
│   ├── enrollment.py         # Enrollment and reactivation
│   └── quiz.py               # Quiz attempt cleanup
│
├── services/                 # Organisms: business flows
│   ├── course_cache.py       # Local course cache
│   ├── candidate_service.py  # Main flow orchestrator
│   ├── document_generator.py # Word document generator
│   └── excel_reader.py       # 🔄 Excel batch reader (in dev)
│
├── models/                   # Pydantic data structures
│   ├── user.py               # UserData, UserSearchResult, UserCredentials
│   ├── course.py             # CourseData, CourseCatalog, QuizData
│   └── enrollment.py         # EnrollmentData, EnrollmentResult
│
├── utils/
│   └── excel_template.py     # 🔄 Excel template generator (in dev)
│
├── assets/                   # Static resources (signatures, etc.)
├── data/courses.json         # Generated course cache
├── output/                   # Generated Word documents
├── logs/                     # Rotating log files
├── screenshots/              # Error screenshots
│
├── main.py                   # Entry point with interactive menu
└── test_full_flow.py         # Interactive test script
```

---

## Main Flow

```
Login → Find/Create User → Set Access Window → Select Tests
  → For each test: Clear Attempts → Enroll/Reactivate
  → Generate Word Document → Next Candidate?
```

Full timing breakdown per step:
- Login + cookies: ~5s
- User lookup: ~7s
- Password update or user creation: ~11s
- Per quiz cleanup: ~2–3s
- Enrollment/reactivation: ~8s
- Document generation: ~1s

---

## Technical Highlights

### SMOWL Modal Handler
The platform introduced a monitoring consent modal that blocked clicks during enrollment. Solved with targeted JS execution:

```python
def _close_smowl_modal(self) -> bool:
    smowl_btn = self.browser.driver.find_element(By.ID, "btn-smowl-entendido")
    if smowl_btn.is_displayed():
        self.browser.driver.execute_script("arguments[0].click();", smowl_btn)
        return True
    return False
```

### Search Filter Cleanup
Multi-candidate sessions accumulated search filters, causing lookup failures. Solved with explicit filter reset between candidates:

```python
def _clear_search_filters(self) -> None:
    clear_btn = self.browser.driver.find_element(By.ID, "id_removeall")
    if clear_btn.is_displayed():
        self.browser.driver.execute_script("arguments[0].click();", clear_btn)
```

### Performance Optimization
Key improvement: switching from `wait_for_page_load()` to `page_load_strategy = "eager"`, eliminating unnecessary waits for non-critical resources. Combined with cookie-based session reuse for subsequent operations.

### Dynamic Word Document Generation
Documents include a dynamic table that supports merged cells for multi-level diagnostic tests, auto-calculated access dates, and embedded corporate signature image.

---

## Planned: Full Automation Pipeline

```
Excel input (batch candidates)
    ↓
Python: Login once → process all candidates
    ↓
For each: create user + assign tests + generate Word doc
    ↓
POST to n8n webhook → send email with Word attachment
    ↓
Update Excel with status + results
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/moodle-automation.git
cd moodle-automation

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install selenium pydantic pydantic-settings python-dotenv colorama "pydantic[email]" python-docx openpyxl
```

---

## Configuration

**Option 1 — `.env` file:**
```env
MOODLE_BASE_URL=https://your-moodle-instance.com
MOODLE_USERNAME=admin_user
MOODLE_PASSWORD=admin_password
```

**Option 2 — Interactive prompt** (recommended for security):
The script will ask for credentials at runtime if no `.env` is present.

---

## Usage

```bash
python main.py
```

**Menu options:**
1. Assign tests (multi-candidate loop)
2. Sync course catalog
3. View available courses (local cache)
4. Generate test document (sample data)
0. Exit

---

## Problems Solved During Development

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| SMOWL modal blocking clicks | New consent overlay | `_close_smowl_modal()` via JS click |
| Search filters accumulating | Not cleared between candidates | `_clear_search_filters()` before each lookup |
| Filter input not appearing | Browser window without focus | Force window focus + retry up to 3x |
| 50s+ on participant filter | Wrong selector | `input[id^='form_autocomplete_input']` |
| Attempts not deleting | Submit button vs link | `input#deleteattemptsbutton` |
| Confirmation modal failing | YUI modal structure | `input.btn-primary[value='Sí']` |
| Slow page transitions | Waiting for all resources | `page_load_strategy = "eager"` |

---

## Roadmap

- [x] Core automation flow
- [x] Multi-candidate loop
- [x] Word document generation
- [x] Course catalog caching
- [ ] Excel batch processing
- [ ] n8n email integration
- [ ] Results export
- [ ] GUI (Tkinter or PyQt)

---

## Tech Stack

- **Python 3.10+**
- **Selenium WebDriver** — browser automation
- **Pydantic v2** — data validation and modeling
- **python-docx** — Word document generation
- **openpyxl** — Excel reading/writing
- **colorama** — colored terminal output
- **python-dotenv** — environment configuration

---

*Built during a software development internship to solve a real operational bottleneck. Currently maintained as an independent project.*