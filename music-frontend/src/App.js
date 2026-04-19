import React, { useState, useEffect } from "react";
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

  // Apply theme to body
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
      const response = await fetch("http://127.0.0.1:5000/recognize", {
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

  // Shazam-style: records 15s, sends to backend, auto-shows result
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      setResult(null);
      setError(null);
      setLoading(false);
      setRecording(true);

      const tryRecognize = () => {
        const recorder = new MediaRecorder(stream, { mimeType });
        let chunks = [];

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = () => {
          const blob = new Blob(chunks, { type: mimeType });
          setAudioBlob(blob);

          // Send to backend immediately
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          setLoading(true);

          fetch("http://127.0.0.1:5000/recognize", { method: "POST", body: formData })
            .then((res) => res.json())
            .then((data) => {
              if (data.result === "No match found" || data.error) {
                // No match yet — try again with next 15s chunk
                setLoading(false);
                // Only retry if stream is still active
                if (stream.active) {
                  tryRecognize();
                } else {
                  setRecording(false);
                  setResult(data);
                }
              } else {
                // Got a match! Stop everything and show result
                stream.getTracks().forEach((t) => t.stop());
                setRecording(false);
                setLoading(false);
                setResult(data);
              }
            })
            .catch((err) => {
              stream.getTracks().forEach((t) => t.stop());
              setRecording(false);
              setLoading(false);
              setError(err.message);
            });
        };

        // Record for 15 seconds then auto-send
        recorder.start();
        setMediaRecorder(recorder);
        setTimeout(() => {
          if (recorder.state === "recording") recorder.stop();
        }, 10000);
      };

      tryRecognize();

    } catch (err) {
      alert("Microphone access denied: " + err.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    setRecording(false);
    setLoading(false);
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
          <h1 className="app-title">
            Music<span>Finder</span>
          </h1>
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
            <button
              className={`btn-record ${recording ? "recording-active" : ""}`}
              onClick={startRecording}
              disabled={recording || loading}
            >
              🎤 Start
            </button>
            <button
              className="btn-record"
              onClick={stopRecording}
              disabled={!recording}
            >
              ⏹ Stop
            </button>
          </div>

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
              <span className="rec-label">● Recording — auto identifies every 15s</span>
            </div>
          )}

          {loading && !recording && (
            <div className="status-ready" style={{color: "var(--accent)"}}>
              🔍 Analyzing audio...
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="error-box">
            ⚠️ {error}
          </div>
        )}

        {/* Loading */}
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
                {/* Banner */}
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

                {/* Details */}
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

                {/* Streaming links */}
                {(result.spotify_url || result.youtube_url || result.apple_url) && (
                  <div className="stream-section">
                    <div className="stream-label">Listen on</div>
                    <div className="stream-links">
                      {result.spotify_url && (
                        <a href={result.spotify_url} target="_blank" rel="noreferrer"
                          className="stream-btn spotify">
                          🎧 Spotify
                        </a>
                      )}
                      {result.youtube_url && (
                        <a href={result.youtube_url} target="_blank" rel="noreferrer"
                          className="stream-btn youtube">
                          ▶ YouTube
                        </a>
                      )}
                      {result.apple_url && (
                        <a href={result.apple_url} target="_blank" rel="noreferrer"
                          className="stream-btn apple">
                          🍎 Apple Music
                        </a>
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