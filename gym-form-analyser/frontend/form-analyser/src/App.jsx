import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, useNavigate } from "react-router-dom";
import './App.css';

function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const handleLogin = (e) => {
    e.preventDefault();
    if (username && password) {
      navigate("/main");
    } else {
      alert("Please enter credentials");
    }
  };

  return (
    <div className="login-wrapper">
      <form onSubmit={handleLogin} className="login-form">
        <h2 className="form-title">Welcome Back 👋</h2>
        <p className="form-subtitle">Please log in to analyze your workout form</p>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="form-input"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="form-input"
        />
        <button type="submit" className="form-button">Log In</button>
      </form>
    </div>
  );
}

function MainPage() {
  const [videoSrc, setVideoSrc] = useState(null);
  const [videoFile, setVideoFile] = useState(null);
  const [exerciseType, setExerciseType] = useState("squat");
  const [status, setStatus] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);

  const handleFileInput = (e) => {
    const file = e.target.files[0];
    if (file) {
      setVideoSrc(URL.createObjectURL(file));
      setVideoFile(file);
      setResult(null);
      setStatus("");
    }
  };

  const handleAnalyze = async () => {
    if (!videoFile) return;
    setStatus("Uploading...");

    const formData = new FormData();
    formData.append("video", videoFile);
    formData.append("exercise_type", exerciseType);

    try {
      const uploadRes = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      const uploadData = await uploadRes.json();
      if (!uploadRes.ok) throw new Error(uploadData.error);

      setStatus("Analyzing...");
      setAnalyzing(true);

      const analyzeRes = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_url: uploadData.video_url,
          exercise_type: uploadData.exercise_type,
        }),
      });

      const analyzeData = await analyzeRes.json();
      if (!analyzeRes.ok || !analyzeData.success)
        throw new Error(analyzeData.error);

      setResult(analyzeData);
      setStatus("Analysis complete.");
    } catch (err) {
      setStatus("❌ " + err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="main-wrapper">
      <div className="main-container">
        <header className="header">
          <h1 className="main-title">🏋️ Workout Form Analyzer</h1>
          <p className="main-subtitle">Upload your workout video and get instant AI-powered feedback</p>
        </header>

        <div className="upload-group">
          <div className="dropdown-group">
            <label className="dropdown-label">Exercise Type:</label>
            <select
              value={exerciseType}
              onChange={(e) => setExerciseType(e.target.value)}
              className="dropdown-select"
            >
              <option value="squat">Squat</option>
              <option value="bench">Bench Press</option>
              <option value="pullup">Pull-up</option>
            </select>
          </div>

          <label htmlFor="videoInput" className="upload-button">
            📹 Choose Video to Upload
            <input
              type="file"
              id="videoInput"
              accept="video/*"
              onChange={handleFileInput}
              className="hidden-input"
            />
          </label>

          <button
            onClick={handleAnalyze}
            disabled={!videoFile || analyzing}
            className="analyze-button"
          >
            {analyzing ? "" : "Upload & Analyze"}
          </button>
          <p className="status-text">{status}</p>
          {analyzing && <div className="spinner"></div>}
        </div>

        {videoSrc && (
          <video src={videoSrc} controls className="video-preview limited-size" />
        )}

        {result && (
          <div className="results-section">
            <h2 className="results-title">📊 Analysis Results</h2>
            <div className="results-grid">
              <p><strong>Exercise:</strong> {result.analysis.exercise || exerciseType}</p>
              <p><strong>Frames Analyzed:</strong> {result.analysis.total_frames_analyzed || "N/A"}</p>
              {result.analysis.average_peak_angle && (
                <p><strong>Average Peak Angle:</strong> {result.analysis.average_peak_angle}°</p>
              )}
              {result.analysis.average_descent_angle && (
                <p><strong>Average Descent Angle:</strong> {result.analysis.average_descent_angle}°</p>
              )}
              {result.analysis.total_reps && (
                <p><strong>Total Reps:</strong> {result.analysis.total_reps}</p>
              )}
              {result.analysis.good_reps && (
                <p><strong>Good Reps:</strong> {result.analysis.good_reps}</p>
              )}
              {result.analysis.bad_reps && (
                <p><strong>Bad Reps:</strong> {result.analysis.bad_reps}</p>
              )}
              <p><strong>Overall Feedback:</strong> {result.analysis.overall_feedback}</p>
            </div>

            {result.gemini_feedback && (
              <div className="feedback-box">
                <h3 className="feedback-title">✨ Gemini Feedback</h3>
                <pre className="feedback-content">
                  {result.gemini_feedback}
                </pre>
              </div>
            )}

            {result.processed_url && (
              <div className="processed-video">
                <h3>🎥 Processed Video</h3>
                <video src={result.processed_url} controls className="video-preview limited-size" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/main" element={<MainPage />} />
      </Routes>
    </Router>
  );
}

export default App;
