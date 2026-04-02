"""
Professional Web UI for DBarf with clean chat interface, upload modal, and schema viewer.
Features syntax highlighting, interactive tables, dark/light mode, and responsive design.
"""

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YappinDB - Chat with your database</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    
    <!-- External Libraries -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" id="hljs-theme">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap">
    
    <style>
        /* ===== CSS Variables ===== */
        :root {
            --primary: #1a73e8;
            --primary-hover: #1557b0;
            --primary-light: #e8f0fe;
            --success: #34a853;
            --error: #ea4335;
            --warning: #fbbc04;
            
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #f1f3f4;
            
            --text-primary: #202124;
            --text-secondary: #5f6368;
            --text-muted: #9aa0a6;
            
            --border: #e0e0e0;
            
            --message-user-bg: #1a73e8;
            --message-user-text: #ffffff;
            --message-assistant-bg: #f1f3f4;
            --message-assistant-text: #202124;
            
            --shadow: 0 2px 8px rgba(0,0,0,0.08);
            
            --radius: 10px;
            --radius-lg: 16px;
            
            --transition: 0.25s ease;
        }

        [data-theme="dark"] {
            --bg-primary: #202124;
            --bg-secondary: #292a2d;
            --bg-tertiary: #3c4043;
            
            --text-primary: #e8eaed;
            --text-secondary: #9aa0a6;
            --text-muted: #5f6368;
            
            --border: #3c4043;
            
            --message-assistant-bg: #3c4043;
            --message-assistant-text: #e8eaed;
        }

        /* ===== Reset & Base ===== */
        *, *::before, *::after {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        html, body {
            height: 100%;
            overflow: hidden;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-primary);
        }

        /* ===== App Container ===== */
        .app-container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }

        /* ===== Header ===== */
        .app-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--bg-primary);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .brand-icon {
            font-size: 28px;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .header-btn {
            padding: 8px 16px;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all var(--transition);
        }

        .header-btn:hover {
            background: var(--bg-tertiary);
        }

        .header-btn.primary {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        .header-btn.primary:hover {
            background: var(--primary-hover);
        }

        .header-btn.danger {
            background: var(--error);
            border-color: var(--error);
            color: white;
        }

        .header-btn.danger:hover {
            background: #d33426;
        }

        .theme-toggle {
            width: 40px;
            height: 40px;
            background: var(--bg-secondary);
            border: none;
            border-radius: 50%;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all var(--transition);
        }

        .theme-toggle:hover {
            background: var(--bg-tertiary);
            color: var(--primary);
        }

        /* ===== Main Content ===== */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* ===== Chat Messages ===== */
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
        }

        .welcome-section {
            text-align: center;
            padding: 80px 20px;
            max-width: 600px;
            margin: 0 auto;
        }

        .welcome-icon {
            font-size: 80px;
            margin-bottom: 24px;
            color: var(--primary);
        }

        .welcome-icon i {
            font-size: 80px;
        }

        .welcome-title {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-primary);
        }

        .welcome-subtitle {
            color: var(--text-secondary);
            line-height: 1.8;
            margin-bottom: 32px;
        }

        .suggestion-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
        }

        .suggestion-chip {
            padding: 10px 16px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 13px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all var(--transition);
        }

        .suggestion-chip:hover {
            background: var(--bg-tertiary);
            border-color: var(--primary);
            color: var(--primary);
        }

        .message {
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            flex-direction: row-reverse;
        }

        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            flex-shrink: 0;
            color: white;
        }

        .message.assistant .message-avatar {
            background: linear-gradient(135deg, var(--primary), #4285f4);
        }

        .message.user .message-avatar {
            background: linear-gradient(135deg, var(--success), #137333);
        }

        .message-content {
            flex: 1;
            max-width: calc(100% - 60px);
            min-width: 0;
        }

        .message-bubble {
            padding: 16px 20px;
            border-radius: var(--radius-lg);
            background: var(--message-assistant-bg);
            color: var(--message-assistant-text);
        }

        .message.user .message-bubble {
            background: var(--message-user-bg);
            color: var(--message-user-text);
            border-bottom-right-radius: 4px;
        }

        .message.assistant .message-bubble {
            border-bottom-left-radius: 4px;
        }

        .message-text {
            line-height: 1.7;
        }

        .message-text p {
            margin-bottom: 12px;
        }

        .message-text p:last-child {
            margin-bottom: 0;
        }

        /* SQL Code Block */
        .sql-block {
            margin: 16px 0;
            border-radius: var(--radius);
            overflow: hidden;
            background: #0d1117;
        }

        .sql-block-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 16px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }

        .sql-block-title {
            font-size: 12px;
            color: #8b949e;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .sql-copy-btn {
            padding: 4px 10px;
            background: transparent;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #8b949e;
            cursor: pointer;
            font-size: 11px;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: all var(--transition);
        }

        .sql-copy-btn:hover {
            background: #21262d;
            color: #c9d1d9;
        }

        .sql-block pre {
            margin: 0;
            padding: 16px;
            overflow-x: auto;
        }

        .sql-block code {
            font-family: 'SF Mono', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.6;
        }

        /* Data Table */
        .data-section {
            margin-top: 16px;
            border-radius: var(--radius);
            overflow: hidden;
            border: 1px solid var(--border);
        }

        .data-section-header {
            padding: 12px 16px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .data-table-wrapper {
            overflow-x: auto;
            max-height: 400px;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        .data-table th,
        .data-table td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        .data-table th {
            background: var(--bg-secondary);
            font-weight: 600;
            color: var(--text-secondary);
            position: sticky;
            top: 0;
            z-index: 10;
            white-space: nowrap;
        }

        .data-table tr:hover {
            background: var(--bg-tertiary);
        }

        /* Error Message */
        .error-message {
            background: #fce8e6;
            border: 1px solid #fda5a5;
            border-radius: var(--radius);
            padding: 16px;
            color: #a02020;
        }

        [data-theme="dark"] .error-message {
            background: #421818;
            border-color: #ea4335;
            color: #ffcccc;
        }

        .error-message strong {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        /* ===== Input Area ===== */
        .chat-input-container {
            padding: 20px 24px;
            border-top: 1px solid var(--border);
            background: var(--bg-primary);
        }

        .input-wrapper {
            display: flex;
            gap: 12px;
            align-items: flex-end;
            max-width: 900px;
            margin: 0 auto;
        }

        .input-field-container {
            flex: 1;
            position: relative;
        }

        .input-field {
            width: 100%;
            padding: 14px 20px;
            padding-right: 50px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            font-size: 14px;
            font-family: inherit;
            color: var(--text-primary);
            resize: none;
            max-height: 200px;
            min-height: 56px;
            transition: all var(--transition);
        }

        .input-field:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
        }

        .input-field::placeholder {
            color: var(--text-muted);
        }

        .send-btn {
            width: 48px;
            height: 48px;
            background: var(--primary);
            border: none;
            border-radius: 50%;
            color: white;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all var(--transition);
            flex-shrink: 0;
        }

        .send-btn:hover:not(:disabled) {
            background: var(--primary-hover);
            transform: scale(1.05);
        }

        .send-btn:disabled {
            background: var(--border);
            cursor: not-allowed;
            opacity: 0.6;
        }

        /* ===== Upload Modal ===== */
        .upload-modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.6);
            z-index: 2000;
            align-items: center;
            justify-content: center;
            padding: 20px;
            backdrop-filter: blur(4px);
        }

        .upload-modal-overlay.show {
            display: flex;
        }

        .upload-modal {
            background: var(--bg-primary);
            border-radius: var(--radius-lg);
            width: 100%;
            max-width: 500px;
            overflow: hidden;
            box-shadow: 0 16px 48px rgba(0,0,0,0.2);
            animation: modalSlideIn 0.3s ease;
        }

        @keyframes modalSlideIn {
            from { transform: translateY(-20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .upload-modal-header {
            padding: 24px;
            text-align: center;
            border-bottom: 1px solid var(--border);
        }

        .upload-modal-icon {
            font-size: 48px;
            color: var(--primary);
            margin-bottom: 16px;
        }

        .upload-modal-title {
            font-size: 22px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        .upload-modal-subtitle {
            font-size: 14px;
            color: var(--text-secondary);
        }

        .upload-modal-body {
            padding: 24px;
        }

        .upload-dropzone {
            border: 2px dashed var(--border);
            border-radius: var(--radius);
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all var(--transition);
            background: var(--bg-secondary);
        }

        .upload-dropzone:hover,
        .upload-dropzone.dragover {
            border-color: var(--primary);
            background: var(--primary-light);
        }

        .upload-dropzone-icon {
            font-size: 36px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }

        .upload-dropzone-text {
            font-size: 15px;
            color: var(--text-primary);
            margin-bottom: 4px;
        }

        .upload-dropzone-hint {
            font-size: 13px;
            color: var(--text-muted);
        }

        .file-types {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: center;
            gap: 12px;
        }

        .file-type-badge {
            padding: 4px 12px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            font-size: 12px;
            color: var(--text-secondary);
        }

        /* ===== Schema Modal ===== */
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .modal-overlay.show {
            display: flex;
        }

        .modal {
            background: var(--bg-primary);
            border-radius: var(--radius-lg);
            width: 100%;
            max-width: 1000px;
            max-height: 85vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }

        .modal-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-title {
            font-size: 18px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .modal-close {
            width: 32px;
            height: 32px;
            background: transparent;
            border: none;
            border-radius: 50%;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all var(--transition);
        }

        .modal-close:hover {
            background: var(--bg-tertiary);
        }

        .modal-body {
            padding: 24px;
            overflow-y: auto;
            flex: 1;
        }

        /* Schema Tables */
        .schema-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 24px;
        }

        .schema-table th,
        .schema-table td {
            padding: 12px 16px;
            text-align: left;
            border: 1px solid var(--border);
        }

        .schema-table th {
            background: var(--bg-secondary);
            font-weight: 600;
            color: var(--text-secondary);
        }

        .table-header-card {
            background: linear-gradient(135deg, var(--primary), #4285f4);
            color: white;
            padding: 16px 20px;
            border-radius: var(--radius);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 16px;
            font-weight: 600;
        }

        /* ===== Loading States ===== */
        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 8px 0;
        }

        .typing-dot {
            width: 8px;
            height: 8px;
            background: var(--text-muted);
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }

        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
            30% { transform: translateY(-8px); opacity: 1; }
        }

        /* ===== Toast Notifications ===== */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 2000;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .toast {
            min-width: 300px;
            padding: 14px 20px;
            background: var(--bg-primary);
            border-radius: var(--radius);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideIn 0.3s ease;
            border-left: 4px solid;
        }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .toast.success { border-color: var(--success); }
        .toast.error { border-color: var(--error); }
        .toast.warning { border-color: var(--warning); }
        .toast.info { border-color: var(--primary); }

        .toast-icon { font-size: 18px; }
        .toast.success .toast-icon { color: var(--success); }
        .toast.error .toast-icon { color: var(--error); }
        .toast.warning .toast-icon { color: var(--warning); }
        .toast.info .toast-icon { color: var(--primary); }

        .toast-message {
            flex: 1;
            font-size: 13px;
            color: var(--text-primary);
        }

        /* ===== Scrollbar ===== */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        /* ===== DataTables Overrides ===== */
        .dataTables_wrapper .dataTables_paginate .paginate_button.current,
        .dataTables_wrapper .dataTables_paginate .paginate_button.current:hover {
            background: var(--primary) !important;
            color: white !important;
            border: none;
        }

        .dataTables_wrapper .dataTables_filter input,
        .dataTables_wrapper .dataTables_length select {
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 6px 12px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Header -->
        <header class="app-header">
            <div class="brand">
                <svg width="40" height="40" viewBox="0 0 50 50" style="margin-right: 10px;">
                    <defs>
                        <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stop-color="#1a73e8"/>
                            <stop offset="100%" stop-color="#4285f4"/>
                        </linearGradient>
                    </defs>
                    <ellipse cx="25" cy="12" rx="18" ry="7" fill="url(#brandGrad)"/>
                    <path d="M7 12v26c0 4 8 7 18 7s18-3 18-7V12" fill="url(#brandGrad)"/>
                    <ellipse cx="25" cy="38" rx="18" ry="7" fill="url(#brandGrad)"/>
                    <path d="M7 25c0 4 8 7 18 7s18-3 18-7M7 32c0 4 8 7 18 7s18-3 18-7" fill="none" stroke="white" stroke-width="2" opacity="0.4"/>
                </svg>
                <span style="font-weight: 700; font-size: 22px;">Yappin<span style="color: var(--primary);">DB</span></span>
            </div>
            <div class="header-actions">
                <button class="header-btn" id="schemaBtn" onclick="showSchema()" style="display: none;">
                    <i class="fas fa-database"></i>
                    Schema
                </button>
                <button class="header-btn danger" onclick="resetSession()" id="resetBtn" style="display: none;">
                    <i class="fas fa-redo"></i>
                    Reset
                </button>
                <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">
                    <i class="fas fa-moon" id="themeIcon"></i>
                </button>
            </div>
        </header>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Chat Messages -->
            <div class="chat-messages" id="chatMessages">
                <div class="welcome-section" id="welcomeSection">
                    <div class="welcome-icon">
                        <i class="fas fa-comments"></i>
                    </div>
                    <h1 class="welcome-title">Welcome to YappinDB</h1>
                    <p class="welcome-subtitle">
                        Chat with your database. Ask questions in plain English, get instant SQL queries and answers.
                    </p>
                    <div class="suggestion-chips">
                        <div class="suggestion-chip" onclick="showUploadHint()">
                            <i class="fas fa-upload"></i> Upload Database
                        </div>
                        <div class="suggestion-chip" onclick="showUploadHint()">
                            <i class="fas fa-file-csv"></i> CSV / Excel
                        </div>
                        <div class="suggestion-chip" onclick="showUploadHint()">
                            <i class="fas fa-database"></i> SQLite
                        </div>
                    </div>
                </div>
            </div>

            <!-- Input Area -->
            <div class="chat-input-container">
                <div class="input-wrapper">
                    <div class="input-field-container">
                        <textarea 
                            class="input-field" 
                            id="questionInput" 
                            placeholder="Upload a database file first..."
                            rows="1"
                            onkeypress="handleKeyPress(event)"
                            oninput="autoResize(this)"
                            disabled
                        ></textarea>
                    </div>
                    <button class="send-btn" id="sendBtn" onclick="sendMessage()" disabled>
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        </main>
    </div>

    <!-- Upload Modal -->
    <div class="upload-modal-overlay" id="uploadModal">
        <div class="upload-modal">
            <div class="upload-modal-header">
                <div class="upload-modal-icon">
                    <i class="fas fa-cloud-upload-alt"></i>
                </div>
                <h2 class="upload-modal-title">Upload Database</h2>
                <p class="upload-modal-subtitle">Upload a database file to start querying your data</p>
            </div>
            <div class="upload-modal-body">
                <div class="upload-dropzone" id="uploadDropzone">
                    <div class="upload-dropzone-icon">
                        <i class="fas fa-file-import"></i>
                    </div>
                    <div class="upload-dropzone-text">Drag and drop your file here</div>
                    <div class="upload-dropzone-hint">or click to browse</div>
                </div>
                <input type="file" id="fileInput" accept=".db,.sqlite,.csv,.xlsx,.xls" style="display: none;">
                <div class="file-types">
                    <span class="file-type-badge">.db</span>
                    <span class="file-type-badge">.sqlite</span>
                    <span class="file-type-badge">.csv</span>
                    <span class="file-type-badge">.xlsx</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Schema Modal -->
    <div class="modal-overlay" id="schemaModal">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-title">
                    <i class="fas fa-database"></i>
                    Database Schema
                </div>
                <button class="modal-close" onclick="closeModal('schemaModal')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body" id="schemaModalBody">
                <div id="schemaLoading" style="text-align: center; padding: 40px;">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                    <p style="color: var(--text-secondary); margin-top: 16px;">Loading schema...</p>
                </div>
                <div id="schemaContent" style="display: none;"></div>
            </div>
        </div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container" id="toastContainer"></div>

    <!-- External Scripts -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    
    <script>
        // ===== App State =====
        const state = {
            sessionId: null,
            fileId: null,
            dbType: null,
            schema: null,
            theme: localStorage.getItem('yappindb_theme') || 'light'
        };

        // ===== Initialization =====
        document.addEventListener('DOMContentLoaded', () => {
            initTheme();
            initUpload();
            initInput();
            checkExistingSession();
        });

        // ===== Theme Management =====
        function initTheme() {
            document.documentElement.setAttribute('data-theme', state.theme);
            updateThemeUI();
        }

        function toggleTheme() {
            state.theme = state.theme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', state.theme);
            localStorage.setItem('yappindb_theme', state.theme);
            updateThemeUI();
            
            const hljsTheme = document.getElementById('hljs-theme');
            hljsTheme.href = state.theme === 'dark' 
                ? 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css'
                : 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
        }

        function updateThemeUI() {
            const icon = document.getElementById('themeIcon');
            icon.className = state.theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }

        // ===== Session Management =====
        function checkExistingSession() {
            const savedSessionId = localStorage.getItem('yappindb_session');
            if (savedSessionId) {
                fetch(`/session/${savedSessionId}`)
                    .then(res => res.ok ? res.json() : null)
                    .then(data => {
                        if (data && data.active) {
                            state.sessionId = savedSessionId;
                            state.fileId = data.file_id || Object.keys(data.files || {})[0];
                            state.dbType = data.db_type;
                            hideUploadModal();
                            enableChat();
                            fetchSchema();
                            addMessage('assistant', 'Welcome back! Your previous session is still active. Ask me questions about your data.');
                        } else {
                            localStorage.removeItem('yappindb_session');
                            showUploadModal();
                        }
                    })
                    .catch(() => showUploadModal());
            } else {
                showUploadModal();
            }
        }

        function showUploadModal() {
            document.getElementById('uploadModal').classList.add('show');
            document.getElementById('questionInput').disabled = true;
            document.getElementById('questionInput').placeholder = 'Upload a database file first...';
            document.getElementById('sendBtn').disabled = true;
            document.getElementById('schemaBtn').style.display = 'none';
            document.getElementById('resetBtn').style.display = 'none';
        }

        function hideUploadModal() {
            document.getElementById('uploadModal').classList.remove('show');
        }

        function showUploadHint() {
            showUploadModal();
        }

        function resetSession() {
            if (state.sessionId) {
                fetch(`/session/${state.sessionId}`, { method: 'DELETE' })
                    .catch(() => {});
            }
            
            state.sessionId = null;
            state.fileId = null;
            state.dbType = null;
            state.schema = null;
            localStorage.removeItem('yappindb_session');
            
            document.getElementById('chatMessages').innerHTML = `
                <div class="welcome-section" id="welcomeSection">
                    <div class="welcome-icon">
                        <i class="fas fa-comments"></i>
                    </div>
                    <h1 class="welcome-title">Welcome to YappinDB</h1>
                    <p class="welcome-subtitle">
                        Chat with your database. Ask questions in plain English, get instant SQL queries and answers.
                    </p>
                    <div class="suggestion-chips">
                        <div class="suggestion-chip" onclick="showUploadHint()">
                            <i class="fas fa-upload"></i> Upload Database
                        </div>
                        <div class="suggestion-chip" onclick="showUploadHint()">
                            <i class="fas fa-file-csv"></i> CSV / Excel
                        </div>
                        <div class="suggestion-chip" onclick="showUploadHint()">
                            <i class="fas fa-database"></i> SQLite
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('schemaBtn').style.display = 'none';
            document.getElementById('resetBtn').style.display = 'none';
            showUploadModal();
            
            showToast('success', 'Session reset successfully');
        }

        function enableChat() {
            console.log('Enabling chat, sessionId:', state.sessionId);
            document.getElementById('questionInput').disabled = false;
            document.getElementById('questionInput').placeholder = 'Ask a question about your data...';
            document.getElementById('sendBtn').disabled = true;  // Disabled until text entered
            document.getElementById('schemaBtn').style.display = 'flex';
            document.getElementById('resetBtn').style.display = 'flex';
        }

        // ===== Upload Handling =====
        function initUpload() {
            const dropzone = document.getElementById('uploadDropzone');
            const fileInput = document.getElementById('fileInput');

            dropzone.addEventListener('click', () => fileInput.click());
            
            dropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropzone.classList.add('dragover');
            });

            dropzone.addEventListener('dragleave', () => {
                dropzone.classList.remove('dragover');
            });

            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) uploadFile(e.target.files[0]);
            });
        }

        function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            if (state.sessionId) {
                formData.append('session_id', state.sessionId);
            }

            showToast('info', 'Uploading ' + file.name + '...');

            fetch('/upload', { method: 'POST', body: formData })
                .then(res => res.json())
                .then(data => {
                    console.log('Upload response:', data);
                    if (data.session_id) {
                        state.sessionId = data.session_id;
                        state.fileId = data.file_id;
                        state.dbType = data.db_type;
                        localStorage.setItem('yappindb_session', state.sessionId);
                        console.log('Session set:', state.sessionId, 'FileId:', state.fileId);

                        hideUploadModal();
                        enableChat();
                        fetchSchema();
                        
                        addMessage('assistant', 
                            `File "${data.filename}" uploaded successfully! Start chatting with your database. Ask me anything about your data!`);
                        showToast('success', 'File uploaded successfully');
                    }
                })
                .catch(err => {
                    console.error('Upload error:', err);
                    showToast('error', 'Upload failed: ' + err.message);
                });
        }

        // ===== Schema Handling =====
        function fetchSchema() {
            if (!state.sessionId) return;
            
            fetch(`/schema/${state.sessionId}`)
                .then(res => res.json())
                .then(data => {
                    state.schema = data;
                })
                .catch(err => console.error('Schema fetch error:', err));
        }

        function showSchema() {
            const modal = document.getElementById('schemaModal');
            const loading = document.getElementById('schemaLoading');
            const content = document.getElementById('schemaContent');

            modal.classList.add('show');
            loading.style.display = 'block';
            content.style.display = 'none';

            if (state.schema) {
                renderSchema(state.schema);
                loading.style.display = 'none';
                content.style.display = 'block';
            } else if (state.sessionId) {
                fetch(`/schema/${state.sessionId}`)
                    .then(res => res.json())
                    .then(data => {
                        state.schema = data;
                        renderSchema(data);
                        loading.style.display = 'none';
                        content.style.display = 'block';
                    })
                    .catch(err => {
                        loading.innerHTML = '<p style="color: var(--error);">Error: ' + err.message + '</p>';
                    });
            }
        }

        function renderSchema(schemaData) {
            const content = document.getElementById('schemaContent');
            
            let html = '<div style="background: var(--primary-light); padding: 16px; border-radius: var(--radius); margin-bottom: 24px;">';
            html += '<strong style="color: var(--primary);">📊 Summary:</strong> ';
            html += `${schemaData.table_count} table(s) found.`;
            html += '</div>';

            schemaData.tables.forEach(table => {
                html += '<div class="table-header-card">';
                html += '<i class="fas fa-table"></i> ' + table.table_name;
                html += '</div>';
                
                html += '<table class="schema-table">';
                html += '<thead><tr><th>Column</th><th>Data Type</th><th>Nullable</th><th>Key</th></tr></thead>';
                html += '<tbody>';

                table.columns.forEach(col => {
                    const isPk = col.primary_key ? 'PRIMARY KEY' : '';
                    const nullable = col.nullable !== false ? 'Yes' : 'No';
                    html += '<tr>';
                    html += '<td><strong>' + col.name + '</strong></td>';
                    html += '<td><code style="background: var(--bg-secondary); padding: 2px 6px; border-radius: 4px;">' + col.type + '</code></td>';
                    html += '<td>' + nullable + '</td>';
                    html += '<td style="color: ' + (isPk ? 'var(--success)' : 'var(--text-muted)') + ';">' + (isPk || '-') + '</td>';
                    html += '</tr>';
                });

                html += '</tbody></table>';

                if (table.foreign_keys && table.foreign_keys.length > 0) {
                    html += '<div style="margin: 16px 0 12px; font-weight: 600; color: var(--text-secondary);">';
                    html += '<i class="fas fa-link"></i> Foreign Keys</div>';
                    html += '<table class="schema-table"><thead><tr><th>Column</th><th>References Table</th><th>References Column</th></tr></thead><tbody>';
                    table.foreign_keys.forEach(fk => {
                        fk.columns.forEach((col, idx) => {
                            html += '<tr>';
                            html += '<td><strong>' + col + '</strong></td>';
                            html += '<td>' + (fk.referenced_table || 'N/A') + '</td>';
                            html += '<td>' + (fk.referenced_columns[idx] || 'N/A') + '</td>';
                            html += '</tr>';
                        });
                    });
                    html += '</tbody></table>';
                }

                html += '<hr style="border: none; border-top: 1px solid var(--border); margin: 24px 0;">';
            });

            content.innerHTML = html;
        }

        // ===== Chat Functionality =====
        function initInput() {
            const input = document.getElementById('questionInput');
            const sendBtn = document.getElementById('sendBtn');
            
            input.addEventListener('input', () => {
                const hasText = input.value.trim();
                sendBtn.disabled = !hasText;
                console.log('Input changed, hasText:', hasText, 'sendBtn.disabled:', sendBtn.disabled);
            });
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        function autoResize(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        }

        async function sendMessage() {
            const input = document.getElementById('questionInput');
            const question = input.value.trim();

            if (!question || !state.sessionId) {
                console.log('Cannot send: question=', question, 'sessionId=', state.sessionId);
                return;
            }

            input.value = '';
            input.style.height = 'auto';
            document.getElementById('sendBtn').disabled = true;

            addMessage('user', question);

            const loadingId = addLoadingIndicator();

            try {
                const requestBody = {
                    question: question,
                    session_id: state.sessionId,
                    file_id: state.fileId
                };

                console.log('Sending chat request:', requestBody);

                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });

                console.log('Response status:', response.status);

                if (!response.ok) {
                    throw new Error('Server returned ' + response.status);
                }

                const data = await response.json();
                console.log('Response data:', data);

                removeLoadingIndicator(loadingId);
                addAssistantMessage(data);

            } catch (err) {
                console.error('Chat error:', err);
                removeLoadingIndicator(loadingId);
                addMessage('assistant', 'Error: ' + err.message, true);
                showToast('error', 'Request failed: ' + err.message);
            }
        }

        function addMessage(role, content, isError = false) {
            const container = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + role;
            
            const avatarIcon = role === 'user' 
                ? '<i class="fas fa-user"></i>' 
                : '<i class="fas fa-robot"></i>';
            
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatarIcon}</div>
                <div class="message-content">
                    <div class="message-bubble">
                        <div class="message-text">${isError ? '<div class="error-message"><strong><i class="fas fa-exclamation-circle"></i> Error</strong>' + escapeHtml(content) + '</div>' : escapeHtml(content)}</div>
                    </div>
                </div>
            `;
            
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }

        function addAssistantMessage(data) {
            const container = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            
            let content = '<div class="message-text">';
            
            if (data.error) {
                content += '<div class="error-message">';
                content += '<strong><i class="fas fa-exclamation-circle"></i> Error</strong>';
                content += escapeHtml(data.error);
                content += '</div>';
            } else {
                content += '<p>' + escapeHtml(data.answer) + '</p>';
            }
            
            if (data.sql) {
                content += `
                    <div class="sql-block">
                        <div class="sql-block-header">
                            <span class="sql-block-title"><i class="fas fa-code"></i> Generated SQL</span>
                            <button class="sql-copy-btn" onclick="copyToClipboard(this, '${encodeURIComponent(data.sql)}')">
                                <i class="fas fa-copy"></i> Copy
                            </button>
                        </div>
                        <pre><code class="language-sql">${escapeHtml(data.sql)}</code></pre>
                    </div>
                `;
            }
            
            if (data.data && data.data.length > 0) {
                const tableId = 'table-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
                content += `
                    <div class="data-section">
                        <div class="data-section-header">
                            <i class="fas fa-table"></i> Results (${data.data.length} rows)
                        </div>
                        <div class="data-table-wrapper">
                            <table id="${tableId}" class="data-table"></table>
                        </div>
                    </div>
                `;
                
                setTimeout(() => {
                    initDataTable(tableId, data.data);
                }, 100);
            }
            
            content += '</div>';
            
            messageDiv.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <div class="message-bubble">${content}</div>
                </div>
            `;
            
            container.appendChild(messageDiv);
            
            setTimeout(() => {
                document.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
            }, 50);
            
            container.scrollTop = container.scrollHeight;
        }

        function addLoadingIndicator() {
            const container = document.getElementById('chatMessages');
            const id = 'loading-' + Date.now();
            
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message assistant';
            loadingDiv.id = id;
            loadingDiv.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <div class="message-bubble">
                        <div class="typing-indicator">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                    </div>
                </div>
            `;
            
            container.appendChild(loadingDiv);
            container.scrollTop = container.scrollHeight;
            
            return id;
        }

        function removeLoadingIndicator(id) {
            const element = document.getElementById(id);
            if (element) element.remove();
        }

        function initDataTable(tableId, data) {
            const table = document.getElementById(tableId);
            if (!data || data.length === 0) return;
            
            const columns = Object.keys(data[0]);
            let html = '<thead><tr>';
            columns.forEach(col => {
                html += '<th>' + escapeHtml(col) + '</th>';
            });
            html += '</tr></thead><tbody>';
            
            data.forEach(row => {
                html += '<tr>';
                columns.forEach(col => {
                    html += '<td>' + escapeHtml(String(row[col])) + '</td>';
                });
                html += '</tr>';
            });
            html += '</tbody>';
            
            table.innerHTML = html;
            
            $(table).DataTable({
                pageLength: 10,
                lengthMenu: [10, 25, 50, 100],
                order: [],
                language: {
                    search: "Filter:",
                    lengthMenu: "Show _MENU_ rows",
                    info: "Showing _START_ to _END_ of _TOTAL_ rows"
                }
            });
        }

        // ===== Utility Functions =====
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function copyToClipboard(btn, encodedText) {
            const text = decodeURIComponent(encodedText);
            navigator.clipboard.writeText(text).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                }, 2000);
                showToast('success', 'SQL copied to clipboard');
            }).catch(() => {
                showToast('error', 'Failed to copy');
            });
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('show');
        }

        function showToast(type, message) {
            const container = document.getElementById('toastContainer');
            const icons = {
                success: 'fa-check-circle',
                error: 'fa-exclamation-circle',
                warning: 'fa-exclamation-triangle',
                info: 'fa-info-circle'
            };
            
            const toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.innerHTML = `
                <i class="fas ${icons[type]} toast-icon"></i>
                <span class="toast-message">${escapeHtml(message)}</span>
            `;
            
            container.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay, .upload-modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                // Don't close upload modal on overlay click - force upload
                if (e.target === overlay && overlay.id !== 'uploadModal') {
                    overlay.classList.remove('show');
                }
            });
        });
    </script>
</body>
</html>
'''
