import React, { useState, useRef } from "react";
import "./App.css";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import tvsLogo from "./assets/CHATBOT_LOGO.png";

import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  Legend
} from "recharts";

function App() {

  // =====================================================
  // STATES & REFS
  // =====================================================
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [darkMode, setDarkMode] = useState(true);
  
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  // =====================================================
  // API URL
  // =====================================================
  const API_URL = "http://127.0.0.1:8000";

  const chartColors = [
    "#EA4D2C", "#253B80", "#4F6EDB", "#FF6B4A",
    "#1D4ED8", "#DC2626", "#3B82F6", "#FB7185"
  ];

  // =====================================================
  // STRUCTURED RESPONSE (Fixed Top-Level Primitive Arrays & [object Object] bug)
  // =====================================================
  const renderStructuredResponse = (data) => {
    // 1. Handle Array Lists (e.g., Change Requests or Column Lists)
    if (Array.isArray(data)) {
      // Check if it's a simple list of strings (like Column Names)
      if (data.length > 0 && typeof data[0] !== 'object') {
        return (
          <ul style={{ margin: 0, paddingLeft: '20px', lineHeight: '1.8' }}>
            {data.map((item, idx) => (
              <li key={idx}>{String(item)}</li>
            ))}
          </ul>
        );
      }

      // If it's an array of objects (like Pending Change Requests), use cards
      return (
        <div className="cr-list">
          {data.map((item, index) => (
            <div key={index} className="cr-list-card">
              {Object.entries(item).map(([key, value]) => (
                <div key={key}>
                  <strong>{key}:</strong> {String(value)}
                </div>
              ))}
            </div>
          ))}
        </div>
      );
    }

    // 2. Handle Objects (e.g., Windchill PLM Data)
    if (data && typeof data === "object") {
      if (data.error) {
        return <div style={{ color: '#EF4444', fontWeight: 'bold' }}>❌ {data.error}</div>;
      }

      return (
        <div className="plm-data-card">
          <div className="plm-data-header">System Record Retrieved</div>
          
          <div className="plm-data-grid">
            {Object.entries(data).map(([key, value]) => {
              if (Array.isArray(value)) return null; 
              
              // NEW: Handle nested objects to prevent [object Object] rendering
              if (value && typeof value === 'object') {
                return (
                  <div className="plm-data-item" key={key}>
                    <div className="plm-data-label">{key.replace(/_/g, ' ')}</div>
                    <div className="plm-data-value" style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '4px' }}>
                      {Object.entries(value).map(([subKey, subVal]) => (
                        <div key={subKey} style={{ fontSize: '13px' }}>
                          <span style={{ color: 'var(--text-muted)', textTransform: 'capitalize', marginRight: '4px' }}>{subKey}:</span> 
                          {String(subVal)}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }

              return (
                <div className="plm-data-item" key={key}>
                  <div className="plm-data-label">{key.replace(/_/g, ' ')}</div>
                  <div className="plm-data-value">{String(value)}</div>
                </div>
              );
            })}
          </div>

          {/* Render Nested Arrays (like BOM Components or String Lists) */}
          {Object.entries(data).map(([key, value]) => {
            if (Array.isArray(value) && value.length > 0) {
              
              // Check if the array contains raw strings/numbers instead of objects
              const isPrimitiveArray = typeof value[0] !== 'object';

              return (
                <div key={key} className="plm-nested-section">
                  <div className="plm-nested-title">{key.replace(/_/g, ' ')}</div>
                  
                  {isPrimitiveArray ? (
                    // Render simple lists (like PFD Process Flow)
                    <ul style={{ 
                      color: 'var(--text-main)', 
                      paddingLeft: '20px', 
                      fontSize: '14px', 
                      lineHeight: '1.8' 
                    }}>
                      {value.map((item, idx) => (
                        <li key={idx}>{String(item)}</li>
                      ))}
                    </ul>
                  ) : (
                    // Render tables for objects (like Windchill BOMs)
                    <div className="plm-table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            {Object.keys(value[0]).map(k => <th key={k}>{k.replace(/_/g, ' ')}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {value.map((item, idx) => (
                            <tr key={idx}>
                              {Object.values(item).map((val, vIdx) => <td key={vIdx}>{String(val)}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            }
            return null;
          })}
        </div>
      );
    }

    // 3. Handle Standard Text
    return <ReactMarkdown>{String(data)}</ReactMarkdown>;
  };

  // =====================================================
  // SEND MESSAGE
  // =====================================================
  const sendMessage = async () => {
    if (!prompt.trim() && !selectedFile) return;

    // 1. CAPTURE DATA GLOBALLY FIRST
    const fileToSend = selectedFile;
    const textToSend = prompt.trim();

    // 2. CLEAR UI INSTANTLY
    setSelectedFile(null);
    setPrompt("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    // 3. BUILD CHAT MESSAGE
    const userText = fileToSend 
      ? textToSend ? `[Attached: ${fileToSend.name}]\n${textToSend}` : `[Attached: ${fileToSend.name}]` 
      : textToSend;

    setMessages((prev) => [...prev, { sender: "user", text: userText }]);
    setLoading(true);

    try {
      // 4. PROCESS FILE UPLOAD
      if (fileToSend) {
        const formData = new FormData();
        formData.append("file", fileToSend);

        const isDataFile = fileToSend.name.endsWith(".csv") || fileToSend.name.endsWith(".xlsx") || fileToSend.name.endsWith(".xls");

        if (isDataFile) {
          const response = await axios.post(`${API_URL}/upload`, formData, {
            headers: { "Content-Type": "multipart/form-data" }
          });

          if (response.data.error) {
             setMessages((prev) => [...prev, { sender: "ai", text: `Error processing file: ${response.data.error}` }]);
          } else {
             setAnalyticsData(response.data);
             setMessages((prev) => [...prev, { sender: "ai", text: `Successfully processed **${response.data.document_type}** document. Dashboard updated.` }]);
          }
        } 
        else {
          const response = await axios.post(`${API_URL}/upload-and-summarize`, formData, {
            headers: { "Content-Type": "multipart/form-data" }
          });
          setMessages((prev) => [...prev, { sender: "ai", text: response.data.summary || "No summary generated." }]);
        }
      } 
      
      // 5. PROCESS NORMAL TEXT & INTENT INTERCEPTION
      else {
        const response = await axios.get(`${API_URL}/test-ai`, {
          params: { prompt: textToSend }
        });
        
        const aiResponse = response.data.response;

        if (aiResponse && typeof aiResponse === "object" && aiResponse.document_modified) {
           setAnalyticsData(aiResponse);
           const versionLabel = aiResponse.active_version || aiResponse.document_version;
           setMessages((prev) => [...prev, { sender: "ai", text: `Document modified successfully! Version updated to **${versionLabel}**.\n\n${aiResponse.revision_summary}` }]);
        } else {
           setMessages((prev) => [...prev, { sender: "ai", text: aiResponse }]);
        }
      }
    } catch (error) {
      console.error(error);
      setMessages((prev) => [...prev, { sender: "ai", text: "Error communicating with backend." }]);
    } finally {
      setLoading(false);
    }
  };

  // =====================================================
  // FILE SELECTION
  // =====================================================
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !loading) {
      sendMessage();
    }
  };

  // =====================================================
  // CHARTS
  // =====================================================
  const renderCharts = () => {
    if (!analyticsData || !analyticsData.analytics) return null;

    const chartData = Object.entries(analyticsData.analytics).map(([key, value]) => ({
      label: key,
      mean: value.mean,
      max: value.max,
      min: value.min
    }));

    if (chartData.length === 0) return null; 

    return (
      <div className="charts-container">
        {/* BAR CHART */}
        <div className="dashboard-card">
          <div className="dashboard-card-title">Analytics Overview</div>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="mean" fill="#EA4D2C" />
              <Bar dataKey="max" fill="#253B80" />
              <Bar dataKey="min" fill="#4F6EDB" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* PIE CHART */}
        <div className="dashboard-card">
          <div className="dashboard-card-title">Mean Distribution</div>
          <ResponsiveContainer width="100%" height={350}>
            <PieChart>
              <Pie data={chartData} dataKey="mean" nameKey="label" outerRadius={110} label>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={chartColors[i % chartColors.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* LINE CHART */}
        <div className="dashboard-card">
          <div className="dashboard-card-title">Trend Analysis</div>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="mean" stroke="#EA4D2C" strokeWidth={3} />
              <Line type="monotone" dataKey="max" stroke="#253B80" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  // =====================================================
  // UI
  // =====================================================
  return (
    <div className={`app-container ${darkMode ? "dark-theme" : "light-theme"}`}>
      
      {/* TOP BAR */}
      <div className="top-bar">
        <div className="logo-section">
          <img src={tvsLogo} alt="Chatbot Logo" className="tvs-logo" />
          <div>
            <div className="main-title">Sahaayak</div>
            <div className="sub-title">AI Analytics & PLM Intelligence</div>
          </div>
        </div>
        <button className="theme-toggle" onClick={() => setDarkMode(!darkMode)}>
          {darkMode ? "☀️ Light" : "🌙 Dark"}
        </button>
      </div>

      {/* MAIN CONTENT */}
      <div className="main-content">
        
        {/* CHAT SECTION */}
        <div className="chat-section">
          <div className="messages-container">
            {messages.length === 0 && (
              <div className="welcome-container">
                <div className="welcome-card">
                  <img src={tvsLogo} alt="Chatbot Logo" className="hero-logo" />
                  <h2>Sahaayak</h2>
                  <p>Enterprise Manufacturing Intelligence Platform</p>
                </div>
              </div>
            )}

            {messages.map((msg, index) => (
              <div key={index} className={`message-wrapper ${msg.sender === "user" ? "user-wrapper" : "ai-wrapper"}`}>
                <div className={`message-bubble ${msg.sender === "user" ? "user-message" : "ai-message"}`}>
                  {renderStructuredResponse(msg.text)}
                </div>
              </div>
            ))}

            {loading && (
              <div className="loading-text">Sahaayak is thinking...</div>
            )}
          </div>

          {/* INPUT WRAPPER */}
          <div style={{ display: 'flex', flexDirection: 'column', padding: '0 24px' }}>
            
            {/* PENDING FILE INDICATOR */}
            {selectedFile && (
              <div style={{ 
                padding: '10px 16px', 
                background: darkMode ? '#111C44' : '#F8FAFC', 
                border: '1px solid #4F6EDB', 
                borderRadius: '12px', 
                marginBottom: '10px', 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                width: 'fit-content',
                gap: '15px'
              }}>
                <span style={{ fontSize: '14px', color: darkMode ? '#CBD5E1' : '#334155', fontWeight: '600' }}>
                  📎 {selectedFile.name}
                </span>
                <button
                  disabled={loading}
                  onClick={() => { 
                    setSelectedFile(null); 
                    if (fileInputRef.current) fileInputRef.current.value = ''; 
                  }}
                  style={{ background: 'transparent', border: 'none', color: '#EA4D2C', cursor: 'pointer', fontSize: '16px', fontWeight: 'bold' }}
                >
                  ✕
                </button>
              </div>
            )}

            {/* MAIN INPUT ROW */}
            <div className="input-section" style={{ padding: '20px 0' }}>
              <label className="upload-button" style={{ opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}>
                📎
                <input 
                  type="file" 
                  hidden 
                  ref={fileInputRef}
                  onChange={handleFileSelect} 
                  disabled={loading}
                />
              </label>
              
              <input
                type="text"
                placeholder={selectedFile ? "Add a message with your file..." : "Ask Sahaayak anything..."}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyPress}
                className="chat-input"
                disabled={loading}
              />
              
              <button 
                onClick={sendMessage} 
                className="send-button"
                disabled={loading}
                style={{ opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
              >
                {loading ? "Sending..." : "Send"}
              </button>
            </div>
            
          </div>
        </div>

        {/* DASHBOARD SECTION */}
        <div className="dashboard-section">
          <div className="dashboard-title">Analytics Dashboard</div>
          
          {analyticsData && (
            <>
              {/* DOCUMENT TYPE & VERSION BADGE */}
              {analyticsData.document_type && (
                <div style={{ marginBottom: "10px", display: "flex", gap: "10px", alignItems: "center" }}>
                  <span className={`priority-badge ${analyticsData.document_type === 'Generic Dataset' ? 'medium' : 'critical'}`}>
                    Detected: {analyticsData.document_type}
                  </span>
                  
                  {(analyticsData.active_version || analyticsData.document_version) && (
                    <span className="priority-badge low" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10B981" }}>
                      {analyticsData.active_version || analyticsData.document_version}
                    </span>
                  )}
                </div>
              )}

              {/* REVISION & EXPORT SUCCESS CARD */}
              {analyticsData.document_modified && (
                 <div className="analytics-card" style={{ border: "1px solid rgba(16, 185, 129, 0.4)" }}>
                   <div className="dashboard-card-title" style={{ color: "#10B981" }}>Revision Successful</div>
                   <div className="insights-text">
                     <strong>Active Version:</strong> {analyticsData.active_version || analyticsData.document_version} <br/>
                     <strong>Summary:</strong> {analyticsData.revision_summary}
                   </div>
                   
                   {/* EXPORT BUTTON */}
                   {analyticsData.export_available && (
                     <button 
                       onClick={() => window.open(`${API_URL}/export-document`, '_blank')}
                       style={{
                         marginTop: '18px',
                         padding: '12px 24px',
                         background: 'linear-gradient(145deg, #10B981, #059669)',
                         color: 'white',
                         border: 'none',
                         borderRadius: '12px',
                         fontWeight: '700',
                         cursor: 'pointer',
                         width: '100%',
                         transition: 'all 0.3s ease'
                       }}
                       onMouseOver={(e) => e.target.style.transform = 'translateY(-2px)'}
                       onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
                     >
                       📥 Download Revised Document
                     </button>
                   )}
                 </div>
              )}

              {/* VERSION HISTORY UI */}
              {analyticsData.version_history && Object.keys(analyticsData.version_history).length > 0 && (
                <div className="analytics-card">
                  <div className="dashboard-card-title">Version History</div>
                  <ul style={{ 
                    paddingLeft: '20px', 
                    fontSize: '14px', 
                    color: darkMode ? '#CBD5E1' : '#334155' 
                  }}>
                    {Object.entries(analyticsData.version_history).map(([v, status]) => (
                      <li key={v} style={{ marginBottom: '6px' }}>
                        <strong style={{ color: v === (analyticsData.active_version || analyticsData.document_version) ? '#10B981' : 'inherit' }}>
                          {v}:
                        </strong> {status} 
                        {v === (analyticsData.active_version || analyticsData.document_version) && " (Active)"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* CHANGE LOG UI */}
              {analyticsData.change_log && analyticsData.change_log.length > 0 && (
                 <div className="analytics-card">
                   <div className="dashboard-card-title">Modification Log</div>
                   <div style={{ overflowX: 'auto' }}>
                     <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '14px', minWidth: '400px' }}>
                       <thead>
                         <tr style={{ borderBottom: darkMode ? '1px solid rgba(148, 163, 184, 0.2)' : '1px solid #CBD5E1' }}>
                           <th style={{ padding: '12px 8px' }}>Field</th>
                           <th style={{ padding: '12px 8px' }}>Target</th>
                           <th style={{ padding: '12px 8px' }}>Old</th>
                           <th style={{ padding: '12px 8px' }}>New</th>
                         </tr>
                       </thead>
                       <tbody>
                         {analyticsData.change_log.map((log, idx) => (
                           <tr key={idx} style={{ borderBottom: darkMode ? '1px solid rgba(148, 163, 184, 0.1)' : '1px solid rgba(203, 213, 225, 0.5)' }}>
                             <td style={{ padding: '12px 8px', color: darkMode ? '#E2E8F0' : '#334155' }}>{log.field}</td>
                             <td style={{ padding: '12px 8px', color: darkMode ? '#94A3B8' : '#64748B' }}>{log.search}</td>
                             <td style={{ padding: '12px 8px', color: '#EF4444', textDecoration: 'line-through' }}>{log.old}</td>
                             <td style={{ padding: '12px 8px', color: '#10B981', fontWeight: 'bold' }}>{log.new}</td>
                           </tr>
                         ))}
                       </tbody>
                     </table>
                   </div>
                 </div>
              )}

              {/* AI INSIGHTS CARD */}
              {analyticsData.insights && (
                 <div className="analytics-card">
                   <div className="dashboard-card-title">AI Insights & Recommendations</div>
                   <div className="insights-text">
                     <ReactMarkdown>{analyticsData.insights}</ReactMarkdown>
                   </div>
                 </div>
              )}

              {/* PFMEA SPECIFIC ANALYSIS */}
              {analyticsData.pfmea_analysis && (
                 <div className="analytics-card">
                   <div className="dashboard-card-title">PFMEA Risk Analysis</div>
                   <div className="kpi-grid">
                     <div className="kpi-card">
                       <div className="kpi-title">Average RPN</div>
                       <div className="kpi-value">{analyticsData.pfmea_analysis.average_rpn}</div>
                     </div>
                     <div className="kpi-card">
                       <div className="kpi-title">Highest RPN</div>
                       <div className="kpi-value" style={{ color: "#EF4444" }}>{analyticsData.pfmea_analysis.highest_rpn}</div>
                     </div>
                   </div>
                 </div>
              )}

              {/* CONTROL PLAN / PFD ANALYSIS */}
              {analyticsData.document_analysis && Object.keys(analyticsData.document_analysis).length > 0 && (
                 <div className="analytics-card">
                   <div className="dashboard-card-title">Document Metrics</div>
                   <div className="kpi-grid">
                     {Object.entries(analyticsData.document_analysis).map(([key, val]) => (
                       <div className="kpi-card" key={key}>
                         <div className="kpi-title">{key.replace(/_/g, ' ').toUpperCase()}</div>
                         <div className="kpi-value">{val}</div>
                       </div>
                     ))}
                   </div>
                 </div>
              )}

              {/* DATASET INFO (NEW: Hidden for PDFs and Text Documents) */}
              {analyticsData.document_type !== 'PDF/TXT Document' && (
                <div className="analytics-card">
                  <div className="dashboard-card-title">Dataset Information</div>
                  <div><strong>Rows:</strong> {analyticsData.rows}</div>
                  <br />
                  <div><strong>Columns:</strong></div>
                  <ul>
                    {analyticsData.columns?.map((col, index) => (
                      <li key={index}>{col}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* CHARTS */}
              {renderCharts()}
            </>
          )}

          {!analyticsData && (
            <div className="empty-dashboard">
              Upload CSV or Excel files to generate dashboards, KPIs, charts, and AI insights.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;