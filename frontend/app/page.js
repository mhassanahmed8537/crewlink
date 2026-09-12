"use client";

import { useEffect, useRef, useState } from "react";
import { getAnnouncement, login, requestDraft, sendAnnouncement } from "../lib/api";

const CLASSIFICATIONS = ["Journeyman Wireman", "Apprentice 3rd Year", "Apprentice 1st Year", "Foreman"];

function newIdempotencyKey() {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `key-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function LoginForm({ onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await login(email, password);
      onLoggedIn(data.token, data.member);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: 320 }}>
      <h1>Member Callout</h1>
      <p>Leadership login</p>
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ display: "block", width: "100%", marginBottom: 12 }}
        />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ display: "block", width: "100%", marginBottom: 12 }}
        />
      </label>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}

function ComposeScreen({ token, member, onLogout }) {
  const [rawText, setRawText] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [needsAck, setNeedsAck] = useState(true);
  const [classification, setClassification] = useState("");

  const [draftLoading, setDraftLoading] = useState(false);
  const [draftNote, setDraftNote] = useState("");

  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");

  const [activeAnnouncement, setActiveAnnouncement] = useState(null);

  const idempotencyKeyRef = useRef(newIdempotencyKey());
  const pollRef = useRef(null);

  function resetComposeForm() {
    setRawText("");
    setTitle("");
    setBody("");
    setNeedsAck(true);
    setClassification("");
    setDraftNote("");
    idempotencyKeyRef.current = newIdempotencyKey();
  }

  async function handleGenerateDraft() {
    if (!rawText.trim()) return;
    setDraftLoading(true);
    setDraftNote("");
    try {
      const draft = await requestDraft(token, rawText);
      if (draft.available) {
        setTitle(draft.title);
        setBody(draft.body);
        setDraftNote(`AI draft ready, ${draft.push_preview.length} character push preview. Review before sending.`);
      } else {
        setDraftNote("AI draft is unavailable right now. Write the title and body manually below.");
      }
    } catch (err) {
      setDraftNote(`AI draft failed: ${err.message}. Write the title and body manually below.`);
    } finally {
      setDraftLoading(false);
    }
  }

  async function handleSend(event) {
    event.preventDefault();
    setSending(true);
    setSendError("");
    try {
      const announcement = await sendAnnouncement(
        token,
        { title, body, needsAck, classification },
        idempotencyKeyRef.current
      );
      setActiveAnnouncement(announcement);
      resetComposeForm();
    } catch (err) {
      setSendError(err.message);
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    if (!activeAnnouncement) return undefined;

    async function poll() {
      try {
        const fresh = await getAnnouncement(token, activeAnnouncement.id);
        setActiveAnnouncement(fresh);
      } catch {
        // a missed poll is not worth surfacing to leadership, the next one will catch up
      }
    }

    pollRef.current = setInterval(poll, 3000);
    return () => clearInterval(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeAnnouncement?.id, token]);

  return (
    <div style={{ maxWidth: 640 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1>Member Callout</h1>
        <button onClick={onLogout}>Sign out</button>
      </div>
      <p>
        Sending as <strong>{member.full_name}</strong>, {member.local_name}
      </p>

      <section style={{ marginBottom: 24, padding: 12, border: "1px solid #ccc" }}>
        <h2 style={{ fontSize: "1rem" }}>Paste the messy note (optional)</h2>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          rows={3}
          style={{ width: "100%" }}
          placeholder="emergency mtg thurs 6pm hall re: contractor pulling crews off the westside job, EVERYONE needs to be there this is the third time"
        />
        <button type="button" onClick={handleGenerateDraft} disabled={draftLoading || !rawText.trim()}>
          {draftLoading ? "Generating..." : "Generate draft with AI"}
        </button>
        {draftNote && <p>{draftNote}</p>}
      </section>

      <form onSubmit={handleSend}>
        <label>
          Title
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            style={{ display: "block", width: "100%", marginBottom: 12 }}
          />
        </label>
        <label>
          Body
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required
            rows={4}
            style={{ display: "block", width: "100%", marginBottom: 12 }}
          />
        </label>
        <label style={{ display: "block", marginBottom: 12 }}>
          Classification (optional, narrows the audience)
          <select
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
            style={{ display: "block", width: "100%" }}
          >
            <option value="">All classifications</option>
            {CLASSIFICATIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "block", marginBottom: 12 }}>
          <input type="checkbox" checked={needsAck} onChange={(e) => setNeedsAck(e.target.checked)} />
          Requires acknowledgement
        </label>
        {sendError && <p style={{ color: "crimson" }}>{sendError}</p>}
        <button type="submit" disabled={sending}>
          {sending ? "Sending..." : "Send"}
        </button>
      </form>

      {activeAnnouncement && (
        <section style={{ marginTop: 32, padding: 12, border: "1px solid #ccc" }}>
          <h2 style={{ fontSize: "1rem" }}>{activeAnnouncement.title}</h2>
          <p>Sent {activeAnnouncement.sent_at ? new Date(activeAnnouncement.sent_at).toLocaleString() : "..."}</p>
          <table cellPadding={6} style={{ borderCollapse: "collapse" }}>
            <tbody>
              <tr>
                <td>Total recipients</td>
                <td>{activeAnnouncement.counts.total}</td>
              </tr>
              <tr>
                <td>Sent</td>
                <td>{activeAnnouncement.counts.sent}</td>
              </tr>
              <tr>
                <td>Read</td>
                <td>{activeAnnouncement.counts.read}</td>
              </tr>
              <tr>
                <td>Acknowledged</td>
                <td>{activeAnnouncement.counts.acknowledged}</td>
              </tr>
              <tr>
                <td>Failed</td>
                <td>{activeAnnouncement.counts.failed}</td>
              </tr>
            </tbody>
          </table>
          <p style={{ fontSize: "0.85rem", color: "#555" }}>Refreshes every 3 seconds.</p>
        </section>
      )}
    </div>
  );
}

export default function Page() {
  const [session, setSession] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("callout-session");
    if (stored) {
      setSession(JSON.parse(stored));
    }
    setReady(true);
  }, []);

  function handleLoggedIn(token, member) {
    const next = { token, member };
    window.localStorage.setItem("callout-session", JSON.stringify(next));
    setSession(next);
  }

  function handleLogout() {
    window.localStorage.removeItem("callout-session");
    setSession(null);
  }

  if (!ready) return null;

  if (!session) {
    return <LoginForm onLoggedIn={handleLoggedIn} />;
  }

  return <ComposeScreen token={session.token} member={session.member} onLogout={handleLogout} />;
}
