/**
 * TruthTrace API Client Service
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001/api';

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
    // Fallback attempt via relative proxy /api/verify
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
      // ignore fallback error and throw original
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
