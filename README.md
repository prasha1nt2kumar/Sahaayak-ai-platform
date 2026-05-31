# Sahaayak: Enterprise AI for Manufacturing & SLM

**Sahaayak** is an intelligent, AI-powered Manufacturing Intelligence Platform. Designed to sit on top of Service Lifecycle Management (SLM) and PLM architectures (like PTC Windchill), it enables engineers and managers to converse with product data, automate document revisions, and visualize Change Management bottlenecks in real-time.

---

## Project Overview
Traditional enterprise manufacturing relies on rigid PLM software, manual Excel/CSV edits, and static PDF SOPs. **Sahaayak** modernizes this workflow using a **Retrieval & Modification AI Engine**. 

Users can upload PFMEAs, Control Plans, Process Flow Diagrams (PFDs), or standard operating procedure (SOP) PDFs. The LLM understands the user's intent to automatically rewrite documents, recalculate risk formulas, update Excel cells via fuzzy matching, and instantly generate downloadable revised files—all while rendering real-time analytical dashboards.

---

## Key Features

### 1. Smart Document Editor (Spreadsheets)
* **Dataset Support:** Upload `.csv`, `.xlsx`, or `.xls` files.
* **Intelligent Modification:** Type commands like *"Change the occurrence of 'Robot path deviation' to 8"*. The AI automatically finds the row, fuzzy-matches the exact column, and updates the data.
* **Auto-Recalculations:** Automatically detects PFMEA structures and recalculates Risk Priority Numbers (RPNs) on the fly.
* **Version Control & Logging:** Tracks document revisions (e.g., Rev A.1 -> A.2) and generates a visual diff log of old vs. new values.

### 2. AI Document Rewriter (PDF / Text)
* **Text Extraction & Summarization:** Extracts text from `.pdf` and `.txt` files to instantly generate executive summaries, key findings, and risk profiles.
* **Contextual Rewriting:** Ask the AI to *"Rewrite this SOP to include daily safety checks"* or *"Translate this document to Spanish"*. 
* **PDF Generation:** Automatically compiles the LLM's rewritten output into a freshly formatted, downloadable PDF file.

### 3. Dynamic Analytics Dashboards
* **Automated KPIs:** Instantly calculates dataset rows, columns, and numeric distributions (Mean, Max, Min).
* **Interactive Charts:** Renders Bar, Pie, and Line charts dynamically based on the active dataset using Recharts.
* **Context-Aware UI:** The dashboard gracefully adapts, hiding irrelevant charts when reading text documents and highlighting critical SLA risks.

### 4. Conversational PLM & Change Management
* **Database Mocking:** Queries mocked Windchill Part BOMs, stock levels, and wear rates using natural language.
* **CR Workflow Tracking:** Tracks Change Requests (CRs), triages priority, calculates SLA days remaining, and flags department bottlenecks.

---

## System Architecture

* **Frontend:** React.js, Recharts, React-Markdown.
* **Backend:** Python, FastAPI, Pandas, PyPDF, FPDF.
* **AI Engine:** LangChain, Ollama (Local LLaMA 3 model).
* **Communication:** RESTful APIs, Axios, Multipart Form Data.
