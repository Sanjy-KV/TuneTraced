import React, { useState, useEffect, useRef } from "react";
import "./App.css";

function App() {
  const [theme, setTheme] = useState("dark");
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const [error, setError] = useState(null);

  // Refs to track mic stream and cancelled state
  const streamRef    = useRef(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    document.body.className = theme;
  }, [theme]);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setResult(null);
    setError(null);
  };

  const sendToBackend = async (formData) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch("https://tunetraced-2.onrender.com/recognize", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || `Server error: ${response.status}`);
      }
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    await sendToBackend(formData);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current    = stream;
      cancelledRef.current = false;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      setResult(null);
      setError(null);
      setLoading(false);
      setRecording(true);

      const tryRecognize = () => {
        // Stop retrying if user cancelled
        if (cancelledRef.current) return;
        // Stop retrying if mic is no longer active
        if (!streamRef.current || !streamRef.current.active) return;

        const recorder = new MediaRecorder(stream, { mimeType });
        let chunks = [];

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = () => {
          const blob = new Blob(chunks, { type: mimeType });
          setAudioBlob(blob);

          // If user cancelled before analysis started, don't send
          if (cancelledRef.current) {
            setLoading(false);
            return;
          }

          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          setLoading(true);

          fetch("https://tunetraced-2.onrender.com/recognize", { method: "POST", body: formData })
            .then((res) => res.json())
            .then((data) => {
              // Ignore result if user cancelled
              if (cancelledRef.current) {
                setLoading(false);
                return;
              }

              if (data.result === "No match found" || data.error) {
                setLoading(false);
                // Retry only if mic still active and not cancelled
                if (!cancelledRef.current && streamRef.current && streamRef.current.active) {
                  tryRecognize();
                } else {
                  setRecording(false);
                  if (data.error) setError(data.error);
                }
              } else {
                // Match found — stop mic and show result
                if (streamRef.current) {
                  streamRef.current.getTracks().forEach((t) => t.stop());
                  streamRef.current = null;
                }
                setRecording(false);
                setLoading(false);
                setResult(data);
              }
            })
            .catch((err) => {
              if (streamRef.current) {
                streamRef.current.getTracks().forEach((t) => t.stop());
                streamRef.current = null;
              }
              setRecording(false);
              setLoading(false);
              if (!cancelledRef.current) setError(err.message);
            });
        };

        recorder.start();
        setMediaRecorder(recorder);

        // Auto-send after 10 seconds
        setTimeout(() => {
          if (recorder.state === "recording") recorder.stop();
        }, 10000);
      };

      tryRecognize();

    } catch (err) {
      alert("Microphone access denied: " + err.message);
    }
  };

  // ── STOP = stop mic only, analysis of sent audio continues ──
  const stopRecording = () => {
    // Stop the mic stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    // Stop the recorder — triggers onstop → sends current chunk
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    setRecording(false);
    // NOTE: loading stays true if analysis is still running
  };

  // ── CANCEL = stop everything including analysis ──
  const cancelAll = () => {
    cancelledRef.current = true;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    setRecording(false);
    setLoading(false);
    setResult(null);
    setError(null);
  };

  const confidencePct = result?.score
    ? Math.round(result.score * 100)
    : null;

  return (
    <>
      {/* Animated background orbs */}
      <div className="bg-orbs">
        <div className="orb orb1"></div>
        <div className="orb orb2"></div>
        <div className="orb orb3"></div>
      </div>

      {/* Theme toggle */}
      <div className="theme-toggle">
        <button
          className={`theme-btn ${theme === "dark" ? "active" : ""}`}
          onClick={() => setTheme("dark")}
        >
          🌙 Dark
        </button>
        <button
          className={`theme-btn ${theme === "light" ? "active" : ""}`}
          onClick={() => setTheme("light")}
        >
          ☀️ Light
        </button>
      </div>

      <div className="container">

        {/* Header */}
        <div className="app-header">
          <div className="logo-ring">🎵</div>
          <h1 className="app-title">Music<span>Finder</span></h1>
          <p className="app-subtitle">Identify any song in seconds</p>
        </div>

        {/* Upload Panel */}
        <div className="panel">
          <div className="panel-label">Upload Audio</div>
          <div className="file-drop">
            <input type="file" accept="audio/*" onChange={handleFileChange} />
            <span className="file-drop-icon">🎧</span>
            {file
              ? <p className="selected-name">📄 {file.name}</p>
              : <p>Click to choose an audio file</p>
            }
          </div>
          <button
            className="btn-primary"
            onClick={handleUpload}
            disabled={loading || !file}
          >
            {loading ? "Identifying..." : "✦ Recognize Song"}
          </button>
        </div>

        <div className="divider" />

        {/* Record Panel */}
        <div className="panel">
          <div className="panel-label">Record Audio</div>
          <div className="record-controls">

            {/* Start button */}
            <button
              className={`btn-record ${recording ? "recording-active" : ""}`}
              onClick={startRecording}
              disabled={recording || loading}
            >
              🎤 Start
            </button>

            {/* Stop mic — analysis continues */}
            <button
              className="btn-record"
              onClick={stopRecording}
              disabled={!recording}
              title="Stop microphone (analysis continues)"
            >
              ⏹ Stop Mic
            </button>

            {/* Cancel all — stops everything */}
            <button
              className="btn-record"
              onClick={cancelAll}
              disabled={!recording && !loading}
              title="Cancel everything"
              style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
            >
              ✕ Cancel
            </button>

          </div>

          {/* Recording animation */}
          {recording && (
            <div className="recording-indicator">
              <div className="mic-anim">
                <div className="mic-core">🎙️</div>
              </div>
              <div className="sound-waves">
                {[...Array(9)].map((_, i) => (
                  <div key={i} className="wave-bar"></div>
                ))}
              </div>
              <span className="rec-label">● Listening — identifies every 10s</span>
            </div>
          )}

          {/* Analysing after mic stopped */}
          {loading && !recording && (
            <div className="status-ready" style={{ color: "var(--accent)" }}>
              🔍 Analyzing audio... (click Cancel to stop)
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="error-box">⚠️ {error}</div>
        )}

        {/* Loading spinner */}
        {loading && (
          <div className="loading-panel">
            <div className="spinner-wrap">
              <div className="spinner"></div>
              <div className="spinner-inner"></div>
            </div>
            <p>Analyzing audio fingerprint...</p>
          </div>
        )}

        {/* Result */}
        {result && !loading && (
          <div className="card">
            {result.result ? (
              <div className="no-match">
                <span className="no-match-icon">🔇</span>
                <h2>No Match Found</h2>
                <p>Try a longer clip or clearer audio</p>
              </div>
            ) : (
              <>
                <div className="result-banner">
                  {result.image ? (
                    <img
                      src={result.image}
                      alt="album art"
                      className="album-img"
                      onError={(e) => { e.target.style.display = "none"; }}
                    />
                  ) : (
                    <div className="album-placeholder">🎵</div>
                  )}
                  <div className="result-meta">
                    <h2>{result.song}</h2>
                    <div className="result-artist">🎤 {result.artist}</div>
                    {result.album && (
                      <div className="result-album">💿 {result.album}</div>
                    )}
                  </div>
                  {confidencePct && (
                    <div className="confidence-badge">{confidencePct}% match</div>
                  )}
                </div>

                <div className="details-section">
                  <div className="details-grid">
                    {result.release_date && (
                      <div className="detail-item">
                        <span className="detail-label">Released</span>
                        <span className="detail-value">📅 {result.release_date}</span>
                      </div>
                    )}
                    {result.label && (
                      <div className="detail-item">
                        <span className="detail-label">Label</span>
                        <span className="detail-value">🏷 {result.label}</span>
                      </div>
                    )}
                    {result.duration && (
                      <div className="detail-item">
                        <span className="detail-label">Duration</span>
                        <span className="detail-value">⏱ {result.duration}</span>
                      </div>
                    )}
                    {result.timecode && (
                      <div className="detail-item">
                        <span className="detail-label">Matched at</span>
                        <span className="detail-value">🎯 {result.timecode}</span>
                      </div>
                    )}
                    {result.isrc && (
                      <div className="detail-item detail-full">
                        <span className="detail-label">ISRC</span>
                        <span className="detail-value" style={{ fontSize: "0.78rem", letterSpacing: "1px" }}>
                          {result.isrc}
                        </span>
                      </div>
                    )}
                    {result.genres && result.genres.length > 0 && (
                      <div className="detail-item detail-full">
                        <span className="detail-label">Genres</span>
                        <div className="genre-tags">
                          {result.genres.map((g, i) => (
                            <span key={i} className="genre-tag">{g}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {(result.spotify_url || result.youtube_url || result.apple_url) && (
                  <div className="stream-section">
                    <div className="stream-label">Listen on</div>
                    <div className="stream-links">
                      {result.spotify_url && (
                        <a href={result.spotify_url} target="_blank" rel="noreferrer"
                          className="stream-btn spotify">🎧 Spotify</a>
                      )}
                      {result.youtube_url && (
                        <a href={result.youtube_url} target="_blank" rel="noreferrer"
                          className="stream-btn youtube">▶ YouTube</a>
                      )}
                      {result.apple_url && (
                        <a href={result.apple_url} target="_blank" rel="noreferrer"
                          className="stream-btn apple">🍎 Apple Music</a>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}

export default App;