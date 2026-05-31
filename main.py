# =========================================================
# IMPORTS
# =========================================================

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from langchain_ollama import ChatOllama

import pandas as pd
import pypdf
import io
import re
import numpy as np
import json

# <-- NEW: Safe import for PDF Generation
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# =========================================================
# FASTAPI INITIALIZATION
# =========================================================

app = FastAPI(
    title="Sahaayak Enterprise AI Platform"
)

# =========================================================
# CORS CONFIGURATION
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# LLM INITIALIZATION
# =========================================================

llm = ChatOllama(
    model="llama3",
    temperature=0
)

# =========================================================
# TEMP STORAGE & VERSIONING STORE
# =========================================================

uploaded_df = None
uploaded_text = "" # <-- NEW: Store text for PDF/TXT files

document_store = {
    "active": False,
    "filename": "",
    "document_type": "Generic Dataset",
    "versions": {},
    "version_count": 0,
    "change_logs": {},
    "revision": "A.1",
    "version_revisions": {}, 
    "checkout_status": "Checked In"
}

# =========================================================
# MOCK WINDCHILL DATABASE
# =========================================================

mock_database = {
    "TVS-ENG-001": {
        "name": "Apache RTR 160 Engine Assembly",
        "lifecycle_state": "Released",
        "revision": "B.1",
        "components": [
            {"id": "P-101", "name": "Piston Assembly", "quantity": 1, "wear_rate": "High", "stock": 45},
            {"id": "P-102", "name": "Clutch Friction Plate", "quantity": 4, "wear_rate": "Medium", "stock": 120},
            {"id": "P-103", "name": "Spark Plug", "quantity": 1, "wear_rate": "High", "stock": 300}
        ]
    },
    "TVS-CHAS-005": {
        "name": "Jupiter 110 Frame",
        "lifecycle_state": "In Work",
        "revision": "A.3",
        "components": [
            {"id": "P-201", "name": "Steering Stem", "quantity": 1, "wear_rate": "Low", "stock": 12},
            {"id": "P-202", "name": "Suspension Fork", "quantity": 2, "wear_rate": "Medium", "stock": 34}
        ]
    }
}

# =========================================================
# MOCK CHANGE MANAGEMENT DATABASE
# =========================================================

mock_change_requests = {
    "CR-1001": {"title": "Engine vibration issue fix", "priority": "High", "status": "Pending Approval", "department": "Manufacturing", "sla_days_left": 1, "assigned_to": "Ravi Kumar", "impact": "Production Line", "risk": "High", "description": "Engine vibration issue detected during high-speed testing."},
    "CR-1002": {"title": "Brake assembly redesign", "priority": "Critical", "status": "Under Review", "department": "Design", "sla_days_left": 0, "assigned_to": "Ananya Sharma", "impact": "Vehicle Safety", "risk": "Critical", "description": "Brake assembly redesign required after safety audit findings."},
    "CR-1003": {"title": "Supplier material update", "priority": "Medium", "status": "Approved", "department": "Supply Chain", "sla_days_left": 5, "assigned_to": "Karthik N", "impact": "Procurement", "risk": "Medium", "description": "Supplier changed raw material grade specification."}
}

# =========================================================
# MOCK PFMEA DATABASE
# =========================================================

mock_pfmea_database = {
    "PFMEA-001": {"process": "Engine Assembly", "failure_mode": "Improper Torque Application", "severity": 9, "occurrence": 7, "detection": 4, "rpn": 252, "recommended_action": "Calibrate torque sensor weekly", "responsible_team": "Manufacturing Quality"},
    "PFMEA-002": {"process": "Brake Assembly", "failure_mode": "Brake Disc Misalignment", "severity": 10, "occurrence": 5, "detection": 3, "rpn": 150, "recommended_action": "Install automated alignment inspection", "responsible_team": "Assembly Operations"}
}

# =========================================================
# MOCK CONTROL PLAN DATABASE
# =========================================================

mock_control_plan_database = {
    "CP-001": {"process": "Brake Assembly", "control_parameter": "Disc Thickness", "inspection_frequency": "Every 2 Hours", "inspection_method": "Digital Vernier", "reaction_plan": "Stop production and notify quality team", "spc_required": "Yes"},
    "CP-002": {"process": "Engine Mounting", "control_parameter": "Torque Validation", "inspection_frequency": "Every Shift", "inspection_method": "Torque Analyzer", "reaction_plan": "Recalibrate torque equipment", "spc_required": "No"}
}

# =========================================================
# MOCK PFD DATABASE
# =========================================================

mock_pfd_database = {
    "PFD-001": {"process_name": "Brake Assembly Manufacturing", "process_flow": ["Material Loading", "Disc Assembly", "Hydraulic Fitment", "Torque Tightening", "Inspection", "Packaging"], "bottleneck_operation": "Inspection"},
    "PFD-002": {"process_name": "Engine Assembly", "process_flow": ["Block Preparation", "Piston Installation", "Crankshaft Fitment", "Oil Filling", "Testing", "Dispatch"], "bottleneck_operation": "Testing"}
}

# =========================================================
# SAFE JSON CONVERTER
# =========================================================

def convert_to_python_type(value):
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    return value

# =========================================================
# VERSIONING & MODIFICATION HELPERS
# =========================================================

def detect_modification_intent(user_input: str) -> bool:
    keywords = ["duplicate", "copy", "modify", "revise", "change", "replace", "update", "create new version", "clone", "add", "rewrite"]
    return any(kw in user_input.lower() for kw in keywords)

def mock_windchill_checkout():
    document_store["checkout_status"] = "Checked Out"

def mock_windchill_checkin():
    document_store["checkout_status"] = "Checked In"
    rev = document_store["revision"]
    if "." in rev:
        parts = rev.split(".")
        document_store["revision"] = f"{parts[0]}.{int(parts[1])+1}"

def extract_changes_via_llm(instruction: str, columns: list) -> list:
    prompt = f"""
    Extract the requested dataframe modifications based on this instruction.
    Columns available in document: {columns}
    User instruction: "{instruction}"
    
    Identify the target column from the list above, the search keyword to find the correct row, and the new value.
    Output ONLY a valid JSON array of objects with exact keys: "column", "search_keyword", "new_value".
    Example: [{{"column": "Severity", "search_keyword": "battery", "new_value": 9}}]
    If no specific data change is detected or you cannot match the columns, output [].
    """
    try:
        result = llm.invoke(prompt).content
        start = result.find('[')
        end = result.rfind(']') + 1
        if start != -1 and end != -1:
            result = result[start:end]
        return json.loads(result)
    except:
        return []

def modify_generic_dataset(df, changes):
    log = []
    for change in changes:
        raw_col = change.get("column")
        search = str(change.get("search_keyword", ""))
        new_val = change.get("new_value")
        
        actual_col = None
        if raw_col in df.columns:
            actual_col = raw_col
        else:
            for c in df.columns:
                core_name = re.sub(r'\(.*?\)', '', c).strip().lower()
                if raw_col and (core_name in str(raw_col).lower() or str(raw_col).lower() in core_name):
                    actual_col = c
                    break

        if actual_col and search:
            mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
            if mask.any():
                old_vals = df.loc[mask, actual_col].tolist()
                df.loc[mask, actual_col] = new_val
                log.append({"field": actual_col, "search": search, "old": old_vals[0], "new": new_val})
    return df, log

def modify_pfmea(df):
    lower_map = {col.lower(): col for col in df.columns}
    sev_col = next((v for k, v in lower_map.items() if "severity" in k), None)
    occ_col = next((v for k, v in lower_map.items() if "occurrence" in k), None)
    det_col = next((v for k, v in lower_map.items() if "detection" in k), None)
    if sev_col and occ_col and det_col:
        df["Calculated_RPN"] = (
            pd.to_numeric(df[sev_col], errors="coerce").fillna(0) *
            pd.to_numeric(df[occ_col], errors="coerce").fillna(0) *
            pd.to_numeric(df[det_col], errors="coerce").fillna(0)
        )
    return df

# =========================================================
# FETCH FUNCTIONS
# =========================================================

def fetch_windchill_sbom(part_number: str):
    part_number = part_number.upper().strip()
    if part_number in mock_database:
        return mock_database[part_number]
    return {"error": f"Part number {part_number} not found."}

def fetch_change_request(cr_id: str):
    cr_id = cr_id.upper().strip()
    if cr_id in mock_change_requests:
        return mock_change_requests[cr_id]
    return {"error": f"Change Request {cr_id} not found."}

def fetch_pfmea(pfmea_id: str):
    pfmea_id = pfmea_id.upper().strip()
    if pfmea_id in mock_pfmea_database:
        return mock_pfmea_database[pfmea_id]
    return {"error": f"PFMEA {pfmea_id} not found."}

def fetch_control_plan(cp_id: str):
    cp_id = cp_id.upper().strip()
    if cp_id in mock_control_plan_database:
        return mock_control_plan_database[cp_id]
    return {"error": f"Control Plan {cp_id} not found."}

def fetch_pfd(pfd_id: str):
    pfd_id = pfd_id.upper().strip()
    if pfd_id in mock_pfd_database:
        return mock_pfd_database[pfd_id]
    return {"error": f"PFD {pfd_id} not found."}

# =========================================================
# CHANGE MANAGEMENT ANALYTICS
# =========================================================

def get_cr_analytics():
    total_crs = len(mock_change_requests)
    pending = 0
    critical = 0
    sla_risk = 0
    bottleneck_departments = {}

    for cr_id, cr in mock_change_requests.items():
        if cr["status"] != "Approved": pending += 1
        if cr["priority"] == "Critical": critical += 1
        if cr["sla_days_left"] <= 1: sla_risk += 1
        dept = cr["department"]
        bottleneck_departments[dept] = bottleneck_departments.get(dept, 0) + 1

    return {
        "total_change_requests": total_crs,
        "pending_approvals": pending,
        "critical_change_requests": critical,
        "sla_risk_change_requests": sla_risk,
        "department_load": bottleneck_departments
    }

# =========================================================
# ROOT ROUTE
# =========================================================

@app.get("/")
async def root():
    return {"status": "TVS Buddy Backend Running"}

# =========================================================
# FILE UPLOAD ANALYTICS
# =========================================================

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    global uploaded_df
    global uploaded_text # <-- NEW: Clear old text when uploading dataframe
    global document_store

    try:
        content = await file.read()
        uploaded_text = "" 

        if file.filename.endswith(".csv"):
            uploaded_df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        elif file.filename.endswith(".xlsx") or file.filename.endswith(".xls"):
            uploaded_df = pd.read_excel(io.BytesIO(content))
        else:
            return {"error": "Unsupported file type."}

        uploaded_df = uploaded_df.fillna("")
        
        joined_columns = " ".join(uploaded_df.columns.astype(str)).lower()
        
        pfmea_keywords = ["severity", "occurrence", "detection", "failure mode", "rpn"]
        cp_keywords = ["control parameter", "inspection", "reaction plan", "spc"]
        pfd_keywords = ["process flow", "cycle time", "bottleneck", "operation"]
        
        is_pfmea = any(keyword in joined_columns for keyword in pfmea_keywords)
        is_cp = any(keyword in joined_columns for keyword in cp_keywords)
        is_pfd = any(keyword in joined_columns for keyword in pfd_keywords)
        
        document_type = "Generic Dataset"
        if is_pfmea: document_type = "PFMEA"
        elif is_cp: document_type = "Control Plan"
        elif is_pfd: document_type = "PFD"

        pfmea_analysis = None
        document_analysis = {}
        ai_insights = ""
        
        lower_map = {col.lower(): col for col in uploaded_df.columns}

        if document_type == "PFMEA":
            sev_col = next((v for k, v in lower_map.items() if "severity" in k), None)
            occ_col = next((v for k, v in lower_map.items() if "occurrence" in k), None)
            det_col = next((v for k, v in lower_map.items() if "detection" in k), None)
            
            if sev_col and occ_col and det_col:
                uploaded_df["Calculated_RPN"] = (
                    pd.to_numeric(uploaded_df[sev_col], errors="coerce").fillna(0) *
                    pd.to_numeric(uploaded_df[occ_col], errors="coerce").fillna(0) *
                    pd.to_numeric(uploaded_df[det_col], errors="coerce").fillna(0)
                )
                top_risk_rows = uploaded_df.nlargest(5, "Calculated_RPN")
                
                pfmea_analysis = {
                    "pfmea_detected": True,
                    "average_rpn": float(round(uploaded_df["Calculated_RPN"].mean(), 2)),
                    "highest_rpn": float(uploaded_df["Calculated_RPN"].max()),
                    "top_risk_records": top_risk_rows.to_dict(orient="records")
                }
                
            prompt = f"Analyze this PFMEA summary: {pfmea_analysis}. Generate mitigation recommendations and identify high-risk failure modes. Be concise."
            ai_insights = llm.invoke(prompt).content

        elif document_type == "Control Plan":
            document_analysis["total_controls"] = len(uploaded_df)
            prompt = f"Analyze this Control Plan dataset with columns: {list(uploaded_df.columns)}. Identify missing controls, analyze inspection frequency, and detect process gaps. Be concise."
            ai_insights = llm.invoke(prompt).content

        elif document_type == "PFD":
            ct_col = next((v for k, v in lower_map.items() if "cycle time" in k), None)
            if ct_col:
                document_analysis["highest_cycle_time"] = float(pd.to_numeric(uploaded_df[ct_col], errors="coerce").max())
                
            prompt = f"Analyze this Process Flow Document (PFD) with columns: {list(uploaded_df.columns)}. Identify potential bottlenecks, high cycle times, and summarize flow risks. Be concise."
            ai_insights = llm.invoke(prompt).content

        else:
            prompt = f"Analyze this manufacturing dataset summary. Rows: {len(uploaded_df)}, Columns: {list(uploaded_df.columns)}. Provide key insights, anomalies, and recommendations. Be concise."
            ai_insights = llm.invoke(prompt).content

        numeric_cols = uploaded_df.select_dtypes(include='number').columns
        numeric_summary = {}

        for col in numeric_cols:
            numeric_summary[col] = {
                "mean": float(round(uploaded_df[col].mean(), 2)),
                "max": float(round(uploaded_df[col].max(), 2)),
                "min": float(round(uploaded_df[col].min(), 2))
            }

        document_store["active"] = True
        document_store["filename"] = file.filename
        document_store["document_type"] = document_type
        document_store["versions"] = {1: uploaded_df.copy()}
        document_store["version_count"] = 1
        document_store["change_logs"] = {}
        document_store["revision"] = "A.1"
        document_store["version_revisions"] = {1: "A.1"}
        document_store["checkout_status"] = "Checked In"

        return {
            "message": "File uploaded successfully.",
            "document_type": document_type,
            "rows": int(len(uploaded_df)),
            "columns": list(uploaded_df.columns),
            "analytics": numeric_summary,
            "insights": ai_insights,
            "document_analysis": document_analysis,
            "pfmea_analysis": pfmea_analysis
        }

    except Exception as e:
        return {"error": str(e)}

# =========================================================
# DOCUMENT SUMMARIZATION
# =========================================================

@app.post("/upload-and-summarize")
async def upload_and_summarize(file: UploadFile = File(...)):
    global uploaded_df 
    global uploaded_text
    global document_store

    try:
        content = await file.read()
        extracted_text = ""
        uploaded_df = None # <-- NEW: Clear dataframe if uploading text

        if file.filename.endswith(".pdf"):
            pdf_reader = pypdf.PdfReader(io.BytesIO(content))
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text: extracted_text += text
        elif file.filename.endswith(".txt"):
            extracted_text = content.decode("utf-8")
        else:
            return {"error": "Only PDF and TXT supported."}

        # Cap length to prevent LLM memory overload
        extracted_text = extracted_text[:5000]
        uploaded_text = extracted_text

        # <-- NEW: Register PDF/TXT in Document Store so it can be modified!
        document_store["active"] = True
        document_store["filename"] = file.filename
        document_store["document_type"] = "PDF/TXT Document"
        document_store["versions"] = {1: uploaded_text}
        document_store["version_count"] = 1
        document_store["change_logs"] = {}
        document_store["revision"] = "A.1"
        document_store["version_revisions"] = {1: "A.1"}
        document_store["checkout_status"] = "Checked In"

        summary_prompt = f"""
        Summarize this engineering/manufacturing document:
        {extracted_text}
        Provide:
        - executive summary
        - key findings
        - risks
        - recommendations
        """

        result = llm.invoke(summary_prompt)

        return {
            "filename": file.filename,
            "summary": result.content
        }
    except Exception as e:
        return {"error": str(e)}

# =========================================================
# MAIN CHAT ROUTE
# =========================================================

@app.get("/test-ai")
async def test_ai(prompt: str):
    global uploaded_df
    global uploaded_text
    global document_store

    user_input = prompt.lower().strip()

    # =====================================================
    # NEW: DUAL DOCUMENT MODIFICATION ENGINE (SPREADSHEETS AND PDFS)
    # =====================================================
    if document_store.get("active") and detect_modification_intent(user_input):
        
        is_dataframe_active = uploaded_df is not None and document_store.get("document_type") != "PDF/TXT Document"
        is_text_active = uploaded_text != "" and document_store.get("document_type") == "PDF/TXT Document"

        # -------------------------------------------------
        # SCENARIO A: MODIFING SPREADSHEETS (Existing Logic)
        # -------------------------------------------------
        if is_dataframe_active:
            try:
                mock_windchill_checkout()
                old_rev = document_store["revision"]
                
                current_v = document_store["version_count"]
                new_v = current_v + 1
                new_df = document_store["versions"][current_v].copy()
                
                changes = extract_changes_via_llm(user_input, list(new_df.columns))
                new_df, change_log = modify_generic_dataset(new_df, changes)
                
                doc_type = document_store["document_type"]
                pfmea_analysis = None
                document_analysis = {}

                if doc_type == "PFMEA":
                    new_df = modify_pfmea(new_df)
                    lower_map = {col.lower(): col for col in new_df.columns}
                    sev_col = next((v for k, v in lower_map.items() if "severity" in k), None)
                    occ_col = next((v for k, v in lower_map.items() if "occurrence" in k), None)
                    det_col = next((v for k, v in lower_map.items() if "detection" in k), None)
                    
                    if sev_col and occ_col and det_col and "Calculated_RPN" in new_df.columns:
                        top_risk_rows = new_df.nlargest(5, "Calculated_RPN")
                        pfmea_analysis = {
                            "pfmea_detected": True,
                            "average_rpn": float(round(new_df["Calculated_RPN"].mean(), 2)),
                            "highest_rpn": float(new_df["Calculated_RPN"].max()),
                            "top_risk_records": top_risk_rows.to_dict(orient="records")
                        }
                elif doc_type == "Control Plan":
                    document_analysis["total_controls"] = len(new_df)
                elif doc_type == "PFD":
                    lower_map = {col.lower(): col for col in new_df.columns}
                    ct_col = next((v for k, v in lower_map.items() if "cycle time" in k), None)
                    if ct_col:
                        document_analysis["highest_cycle_time"] = float(pd.to_numeric(new_df[ct_col], errors="coerce").max())
                
                document_store["versions"][new_v] = new_df
                document_store["version_count"] = new_v
                document_store["change_logs"][new_v] = change_log
                uploaded_df = new_df  
                
                mock_windchill_checkin()
                new_rev = document_store["revision"]
                document_store["version_revisions"][new_v] = new_rev 
                
                summary_prompt = f"Summarize these document modifications: {change_log}. Old Revision: {old_rev}, New Revision: {new_rev}. Mention impacts and risks concisely."
                ai_summary = llm.invoke(summary_prompt).content
                
                numeric_cols = new_df.select_dtypes(include='number').columns
                numeric_summary = {}
                for col in numeric_cols:
                    numeric_summary[col] = {
                        "mean": float(round(new_df[col].mean(), 2)),
                        "max": float(round(new_df[col].max(), 2)),
                        "min": float(round(new_df[col].min(), 2))
                    }
                
                structured_response = {
                    "message": f"Successfully created Version {new_v} (Revision {new_rev})",
                    "rows": int(len(new_df)),
                    "columns": list(new_df.columns),
                    "analytics": numeric_summary,
                    "insights": ai_summary,
                    "document_analysis": document_analysis, 
                    "pfmea_analysis": pfmea_analysis,       
                    "document_version": f"v{new_v}",
                    "document_type": doc_type,
                    "change_log": change_log,
                    "modified_fields": list(set([log["field"] for log in change_log])),
                    "export_available": True,
                    "version_history": {f"v{v}": f"Revision {document_store['version_revisions'].get(v, 'A.X')}" for v in document_store["versions"].keys()},
                    "revision_summary": f"Checked out Rev {old_rev} -> Modified -> Checked in Rev {new_rev}",
                    "document_modified": True
                }
                
                return {"prompt": prompt, "response": structured_response}
            except Exception as e:
                return {"prompt": prompt, "response": f"Error modifying document: {str(e)}"}

        # -------------------------------------------------
        # SCENARIO B: MODIFYING PDFs/TXT (New Logic)
        # -------------------------------------------------
        elif is_text_active:
            try:
                mock_windchill_checkout()
                old_rev = document_store["revision"]
                
                current_v = document_store["version_count"]
                new_v = current_v + 1
                old_text = document_store["versions"][current_v]
                
                # Ask LLM to rewrite the document text based on user prompt
                rewrite_prompt = f"Here is the content of the document:\n\n{old_text}\n\nThe user requested the following change: '{user_input}'. Rewrite the document to incorporate these changes seamlessly. Return ONLY the new document text."
                new_text = llm.invoke(rewrite_prompt).content.strip()
                
                document_store["versions"][new_v] = new_text
                document_store["version_count"] = new_v
                
                # Create a simple generic log for text updates
                change_log = [{"field": "Document Body", "search": "Original Text", "old": "[PDF Re-write]", "new": "[PDF Re-write]"}]
                document_store["change_logs"][new_v] = change_log
                uploaded_text = new_text # Update active text
                
                mock_windchill_checkin()
                new_rev = document_store["revision"]
                document_store["version_revisions"][new_v] = new_rev
                
                ai_summary = f"I have analyzed your request and successfully rewritten the document. Changes have been saved in Revision {new_rev}. You can now download the revised PDF file."

                structured_response = {
                    "message": f"Successfully created Version {new_v} (Revision {new_rev})",
                    "rows": 0,
                    "columns": [],
                    "analytics": {},
                    "insights": ai_summary,
                    "document_analysis": {}, 
                    "pfmea_analysis": None,       
                    "document_version": f"v{new_v}",
                    "document_type": "PDF/TXT Document",
                    "change_log": change_log,
                    "modified_fields": ["Document Body"],
                    "export_available": True,
                    "version_history": {f"v{v}": f"Revision {document_store['version_revisions'].get(v, 'A.X')}" for v in document_store["versions"].keys()},
                    "revision_summary": f"Checked out Rev {old_rev} -> Modified Text Content -> Checked in Rev {new_rev}",
                    "document_modified": True
                }
                
                return {"prompt": prompt, "response": structured_response}
            except Exception as e:
                return {"prompt": prompt, "response": f"Error modifying text document: {str(e)}"}

    pfmea_match = re.search(r"(PFMEA-\d+)", prompt.upper())
    cp_match = re.search(r"(CP-\d+)", prompt.upper())
    pfd_match = re.search(r"(PFD-\d+)", prompt.upper())
    cr_match = re.search(r"(CR-\d+)", prompt.upper())
    part_match = re.search(r"(TVS-[A-Z]+-\d+)", prompt.upper())
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    small_talk = ["how are you"]

    if user_input in greetings: return {"prompt": prompt, "response": "Hello! I am TVS Buddy, your enterprise AI assistant."}
    if user_input in small_talk: return {"prompt": prompt, "response": "I am good, How can I help you!!"}

    if part_match: return {"prompt": prompt, "response": fetch_windchill_sbom(part_match.group(1))}
    
    if cr_match:
        cr_data = fetch_change_request(cr_match.group(1))
        if "error" in cr_data: return {"prompt": prompt, "response": cr_data["error"]}
        if "summary" in user_input or "executive" in user_input:
            summary_prompt = f"Generate an executive summary for this change request: {cr_data}"
            result = llm.invoke(summary_prompt)
            return {"prompt": prompt, "response": result.content}
        return {"prompt": prompt, "response": cr_data}

    if "pending" in user_input or "sla" in user_input or "bottleneck" in user_input or "change analytics" in user_input:
        analytics = get_cr_analytics()
        if "pending" in user_input:
            pending_crs = [{"cr_id": cr_id, "title": cr["title"], "status": cr["status"], "priority": cr["priority"]} for cr_id, cr in mock_change_requests.items() if cr["status"] != "Approved"]
            return {"prompt": prompt, "response": pending_crs}
        if "sla" in user_input:
            risk_crs = [{"cr_id": cr_id, "title": cr["title"], "sla_days_left": cr["sla_days_left"], "priority": cr["priority"]} for cr_id, cr in mock_change_requests.items() if cr["sla_days_left"] <= 1]
            return {"prompt": prompt, "response": risk_crs}
        if "bottleneck" in user_input:
            max_dept = max(analytics["department_load"], key=analytics["department_load"].get)
            return {"prompt": prompt, "response": f"Highest approval load is in {max_dept} department."}
        return {"prompt": prompt, "response": analytics}

    if pfmea_match: return {"prompt": prompt, "response": fetch_pfmea(pfmea_match.group(1))}
    if cp_match: return {"prompt": prompt, "response": fetch_control_plan(cp_match.group(1))}
    if pfd_match: return {"prompt": prompt, "response": fetch_pfd(pfd_match.group(1))}

    if uploaded_df is not None:
        try:
            numeric_cols = uploaded_df.select_dtypes(include='number').columns
            if "columns" in user_input: return {"prompt": prompt, "response": list(uploaded_df.columns)}

            if "highest" in user_input or "maximum" in user_input or "top" in user_input:
                if len(numeric_cols) > 0:
                    col = None
                    for c in numeric_cols:
                        core_name = re.sub(r'\(.*?\)', '', c).strip().lower()
                        if core_name in user_input:
                            col = c
                            break
                    if col is None: col = numeric_cols[0]
                    highest_row = uploaded_df.loc[uploaded_df[col].idxmax()]
                    return {"prompt": prompt, "response": highest_row.to_dict()}

            if "lowest" in user_input or "minimum" in user_input or "low stock" in user_input:
                if len(numeric_cols) > 0:
                    col = None
                    for c in numeric_cols:
                        core_name = re.sub(r'\(.*?\)', '', c).strip().lower()
                        if core_name in user_input:
                            col = c
                            break
                    if col is None: col = numeric_cols[0]
                    lowest_rows = uploaded_df.nsmallest(5, col)
                    return {"prompt": prompt, "response": lowest_rows.to_dict(orient="records")}

            if "average" in user_input or "mean" in user_input:
                averages = {}
                for col in numeric_cols:
                    averages[col] = float(round(uploaded_df[col].mean(), 2))
                return {"prompt": prompt, "response": averages}

            if "summary" in user_input or "analytics" in user_input or "insights" in user_input:
                summary = {}
                for col in numeric_cols[:5]:
                    summary[col] = {
                        "mean": float(round(uploaded_df[col].mean(), 2)),
                        "max": float(round(uploaded_df[col].max(), 2)),
                        "min": float(round(uploaded_df[col].min(), 2))
                    }
                return {"prompt": prompt, "response": summary}
        except Exception as e:
            return {"prompt": prompt, "response": str(e)}

    # General AI Fallback
    try:
        generic_prompt = f"You are Sahaayak, an enterprise AI assistant developed for TVS Motors. User Query: {prompt}"
        result = llm.invoke(generic_prompt)
        return {"prompt": prompt, "response": result.content}
    except Exception as e:
        return {"prompt": prompt, "response": str(e)}

# =========================================================
# EXPORT REVISED DOCUMENT (UPDATED FOR PDFs)
# =========================================================

@app.get("/export-document")
async def export_document():
    global uploaded_df
    global uploaded_text
    
    doc_type = document_store.get("document_type", "")
    
    # 1. Export Dataframe as CSV
    if doc_type != "PDF/TXT Document" and uploaded_df is not None:
        csv_data = uploaded_df.to_csv(index=False)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=revised_tvs_document.csv"}
        )
        
    # 2. NEW: Export Edited Text as PDF (or TXT Fallback)
    elif doc_type == "PDF/TXT Document" and uploaded_text:
        # If FPDF is installed, generate a real PDF
        if FPDF:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                
                # Split text and handle characters gracefully
                for line in uploaded_text.split('\n'):
                    safe_line = line.encode('latin-1', 'replace').decode('latin-1')
                    pdf.multi_cell(0, 10, txt=safe_line)
                
                pdf_bytes = pdf.output(dest='S')
                if isinstance(pdf_bytes, str):
                    pdf_bytes = pdf_bytes.encode('latin-1')
                    
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=revised_tvs_document.pdf"}
                )
            except Exception:
                pass # If PDF generation fails, fallback to standard text download

        # Fallback: Download as a pure text file
        return Response(
            content=uploaded_text.encode('utf-8'),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=revised_tvs_document.txt"}
        )
        
    return {"error": "No document available for export."}

# =========================================================
# STARTUP EVENT
# =========================================================

@app.on_event("startup")
async def startup_event():
    try:
        llm.invoke("Initialize TVS Buddy")
        print("TVS Buddy Enterprise Backend Started")
    except Exception as e:
        print(f"Startup warmup failed: {e}")