const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

async function request(path, { method = "GET", token, body, headers } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    // no body
  }

  if (!response.ok) {
    const message = (data && (data.detail || JSON.stringify(data))) || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

export function login(email, password) {
  return request("/auth/login/", { method: "POST", body: { email, password } });
}

export function requestDraft(token, rawText) {
  return request("/announcements/draft/", { method: "POST", token, body: { raw_text: rawText } });
}

export function sendAnnouncement(token, { title, body, needsAck, classification }, idempotencyKey) {
  return request("/announcements/", {
    method: "POST",
    token,
    headers: { "Idempotency-Key": idempotencyKey },
    body: {
      title,
      body,
      needs_ack: needsAck,
      classification: classification || "",
    },
  });
}

export function getAnnouncement(token, id) {
  return request(`/announcements/${id}/`, { token });
}

export function listAnnouncements(token) {
  return request("/announcements/", { token });
}
