const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const MAX_CALLS = 3;
const STORAGE_KEY = 'shng_usage_count';

function isUnlimited() {
  const params = new URLSearchParams(window.location.search);
  return params.get('unlimited') === 'true';
}

export function getRemainingCalls() {
  if (isUnlimited()) return Infinity;
  const used = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
  return MAX_CALLS - used;
}

function incrementUsage() {
  if (isUnlimited()) return;
  const used = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
  localStorage.setItem(STORAGE_KEY, String(used + 1));
}

export async function generateName(seed, mode) {
  if (getRemainingCalls() <= 0) {
    throw new Error('Demo limit reached (3 of 3 generations used). This is a portfolio demo with limited usage.');
  }

  const response = await fetch(`${API_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed, mode }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Generation failed' }));
    throw new Error(err.error || 'Generation failed');
  }

  const data = await response.json();
  incrementUsage();
  return data;
}
