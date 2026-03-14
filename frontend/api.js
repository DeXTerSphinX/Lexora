/**
 * Lexora API Client
 * Shared fetch wrapper for all frontend pages with authentication support.
 */

const API_BASE = "http://localhost:8000";
const TOKEN_STORAGE_KEY = "lexora_access_token";
const REFRESH_TOKEN_KEY = "lexora_refresh_token";


// ===========================
// Token Management
// ===========================

function saveTokens(accessToken, refreshToken) {
    /**Save access and refresh tokens to localStorage*/
    localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

function getAccessToken() {
    /**Get stored access token from localStorage*/
    return localStorage.getItem(TOKEN_STORAGE_KEY);
}

function getRefreshToken() {
    /**Get stored refresh token from localStorage*/
    return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function clearTokens() {
    /**Clear all stored tokens from localStorage*/
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function isAuthenticated() {
    /**Check if user is authenticated (has valid access token)*/
    return !!getAccessToken();
}


// ===========================
// Authentication Endpoints
// ===========================

async function registerUser(email, fullName, password, role = 'student') {
    /**Register a new user account

    Args:
        email: User email
        fullName: User full name
        password: User password (min 8 chars)
        role: 'student' or 'admin'

    Returns:
        User data with tokens

    Throws:
        Error if registration fails
    */
    const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            email,
            full_name: fullName,
            password,
            role
        })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Registration failed");
    }

    const data = await res.json();
    saveTokens(data.access_token, data.refresh_token);
    return data;
}

async function loginUser(email, password, role = 'student') {
    /**Login user with email and password

    Args:
        email: User email
        password: User password
        role: 'student' or 'admin' (for UI purposes)

    Returns:
        User data with tokens

    Throws:
        Error if login fails (401 for invalid credentials)
    */
    const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, role })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Login failed");
    }

    const data = await res.json();
    saveTokens(data.access_token, data.refresh_token);
    return data;
}

async function refreshAccessToken() {
    /**Request a new access token using the refresh token

    Returns:
        True if refresh succeeded, False otherwise

    Side effect:
        Updates stored tokens if successful
    */
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (!res.ok) return false;

        const data = await res.json();
        saveTokens(data.access_token, data.refresh_token);
        return true;
    } catch (e) {
        console.error("Token refresh error:", e);
        return false;
    }
}

async function logout() {
    /**Logout current user by revoking all refresh tokens

    Side effect:
        Clears tokens and redirects to login page
    */
    try {
        const token = getAccessToken();
        if (token) {
            await fetch(`${API_BASE}/auth/logout`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                }
            });
        }
    } catch (e) {
        console.error("Logout error:", e);
    }

    clearTokens();
    window.location.href = '/Login.html';
}

async function getCurrentUser() {
    /**Get current authenticated user's info

    Returns:
        User data object

    Throws:
        Error if not authenticated or user not found
    */
    const token = getAccessToken();
    if (!token) {
        throw new Error("Not authenticated");
    }

    const res = await fetch(`${API_BASE}/auth/me`, {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${token}`
        }
    });

    if (!res.ok) {
        if (res.status === 401) {
            clearTokens();
            throw new Error("Session expired");
        }
        const err = await res.json();
        throw new Error(err.detail || "Failed to get user info");
    }

    return res.json();
}


// ===========================
// HTTP Wrapper with Auth & Retry
// ===========================

async function apiFetch(url, options = {}) {
    /**Fetch wrapper that automatically handles auth tokens and refresh

    Args:
        url: API endpoint URL
        options: fetch options (method, body, etc.)

    Returns:
        Response object

    Behavior:
        - Adds access token to Authorization header if available
        - On 401 response, attempts to refresh token and retry once
        - If refresh fails, clears tokens and throws error
    */
    const token = getAccessToken();
    const headers = {
        ...options.headers || {},
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    let response = await fetch(url, { ...options, headers });

    // Handle 401 - try to refresh token
    if (response.status === 401) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            const newToken = getAccessToken();
            headers['Authorization'] = `Bearer ${newToken}`;
            response = await fetch(url, { ...options, headers });
        } else {
            // Refresh failed - clear tokens and redirect to login
            clearTokens();
            window.location.href = '/Login.html';
            throw new Error("Session expired - please login again");
        }
    }

    return response;
}


// ===========================
// Processing Endpoints
// ===========================

async function processPDF(file) {
    /**Upload and process a PDF file

    Args:
        file: File object (PDF)

    Returns:
        Processed PDF result with transformed text and metadata

    Throws:
        Error if processing fails or user not authenticated
    */
    const formData = new FormData();
    formData.append("file", file);

    const res = await apiFetch(`${API_BASE}/v1/process-pdf`, {
        method: "POST",
        body: formData
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to process PDF");
    }

    return res.json();
}


/**
 * Process a PDF with real-time progress updates via SSE.
 * @param {File}     file        The PDF file to upload.
 * @param {Function} onProgress  Called with (step, label) for each pipeline stage.
 * @returns {Promise<Object>}    The final result JSON (same shape as processPDF).
 */
async function processPDFWithProgress(file, onProgress) {

    const formData = new FormData();
    formData.append("file", file);

    const token = getAccessToken();
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Try initial request
    let res = await fetch(`${API_BASE}/v1/process-pdf-stream`, {
        method: "POST",
        body: formData,
        headers
    });

    // If 401, try to refresh and retry
    if (res.status === 401) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            const newToken = getAccessToken();
            const newHeaders = { 'Authorization': `Bearer ${newToken}` };
            res = await fetch(`${API_BASE}/v1/process-pdf-stream`, {
                method: "POST",
                body: formData,
                headers: newHeaders
            });
        } else {
            clearTokens();
            window.location.href = '/Login.html';
            throw new Error("Session expired - please login again");
        }
    }

    if (!res.ok) {
        let detail = "Failed to process PDF";
        try {
            const err = await res.json();
            detail = err.detail || detail;
        } catch (_) {}
        throw new Error(detail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines
        const parts = buffer.split("\n\n");
        buffer = parts.pop(); // last part may be incomplete

        for (const part of parts) {
            if (!part.trim()) continue;

            const lines = part.split("\n");
            let eventType = "";
            let data = "";

            for (const line of lines) {
                if (line.startsWith("event: ")) eventType = line.slice(7);
                else if (line.startsWith("data: "))  data = line.slice(6);
            }

            if (eventType === "progress" && onProgress) {
                const payload = JSON.parse(data);
                onProgress(payload.step, payload.label);
            } else if (eventType === "result") {
                finalResult = JSON.parse(data);
            } else if (eventType === "error") {
                const payload = JSON.parse(data);
                throw new Error(payload.detail || "Pipeline error");
            }
        }
    }

    if (!finalResult) throw new Error("Stream ended without a result");
    return finalResult;
}


async function analyzeText(text) {
    /**Analyze text for cognitive complexity

    Args:
        text: Text to analyze

    Returns:
        Complexity analysis result

    Throws:
        Error if analysis fails or user not authenticated
    */
    const res = await apiFetch(`${API_BASE}/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to analyze text");
    }

    return res.json();
}


async function transformText(text) {
    /**Transform text to reduce cognitive load

    Args:
        text: Text to transform

    Returns:
        Transformed text with metadata

    Throws:
        Error if transformation fails or user not authenticated
    */
    const res = await apiFetch(`${API_BASE}/v1/transform`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to transform text");
    }

    return res.json();
}

async function transformBatch(questions) {
    /**Transform multiple texts at once

    Args:
        questions: Array of text strings to transform

    Returns:
        Array of transformation results

    Throws:
        Error if batch transformation fails or user not authenticated
    */
    const res = await apiFetch(`${API_BASE}/v1/transform-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to transform batch");
    }

    return res.json();
}
