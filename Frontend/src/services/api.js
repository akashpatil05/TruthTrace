/**
 * TruthTrace API Client Service
 */

// In production, default to the live Render backend URL.
// In development, allow localhost fallback if no env variable is set.
const getBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl.trim()) {
    const clean = envUrl.trim().replace(/\/+$/, '');
    return clean.endsWith('/api') ? clean : `${clean}/api`;
  }
  
  // If running locally in development mode (vite dev)
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8001/api';
  }

  // Default production fallback: live deployed Render backend
  return 'https://truthtrace-api-rdd5.onrender.com/api';
};

const BASE_URL = getBaseUrl();

export async function verifyClaim(text) {
  try {
    const response = await fetch(`${BASE_URL}/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Server error: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    // If running on custom domain or proxy setup, try relative path as last resort
    if (BASE_URL.startsWith('http')) {
      try {
        const fallbackResponse = await fetch('/api/verify', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text }),
        });
        if (fallbackResponse.ok) {
          return await fallbackResponse.json();
        }
      } catch (_) {
        // ignore fallback error and throw original error
      }
    }
    throw error;
  }
}

export async function fetchDocuments() {
  const response = await fetch(`${BASE_URL}/documents`);
  if (!response.ok) {
    throw new Error('Failed to fetch indexed documents');
  }
  return await response.json();
}

export async function checkBackendHealth() {
  try {
    const response = await fetch(`${BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}
