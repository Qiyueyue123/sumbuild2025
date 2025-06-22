import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, useNavigate } from "react-router-dom";
import './App.css';

function RegisterPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!username || !password || !confirmPassword) {
      setError("All fields are required.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      const res = await fetch("http://localhost:5000/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccess("Registration successful! Redirecting to login...");
        setTimeout(() => navigate("/"), 2000);
      } else {
        setError(data.error || "Registration failed.");
      }
    } catch (err) {
      setError("Error connecting to server.");
    }
  };

  return (
    <div className="login-wrapper">
      <form onSubmit={handleRegister} className="login-form">
        <h2 className="form-title">Create an Account 📝</h2>
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
        <input
          type="password"
          placeholder="Confirm Password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="form-input"
        />
        {error && <p style={{ color: "red" }}>{error}</p>}
        {success && <p style={{ color: "green" }}>{success}</p>}
        <button type="submit" className="form-button">Register</button>
        <p style={{ marginTop: "1rem" }}>
          Already have an account?{" "}
          <span
            style={{ color: "#007bff", cursor: "pointer" }}
            onClick={() => navigate("/")}
          >
            Login here
          </span>
        </p>
      </form>
    </div>
  );
}

function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");

    if (!username || !password) {
      setError("Please enter both username and password.");
      return;
    }

    try {
      const res = await fetch("http://localhost:5000/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });

      const data = await res.json();
      if (res.ok) {
        navigate("/main");
      } else {
        setError(data.error || "Login failed.");
      }
    } catch (err) {
      setError("Error connecting to server.");
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
        {error && <p style={{ color: "red", marginBottom: "10px" }}>{error}</p>}
        <button type="submit" className="form-button">Log In</button>
        <p style={{ marginTop: "1rem" }}>
          Don't have an account?{" "}
          <span
            style={{ color: "#007bff", cursor: "pointer" }}
            onClick={() => navigate("/register")}
          >
            Register here
          </span>
        </p>
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
    setStatus("Analyzing...");
    setAnalyzing(true);

    const formData = new FormData();
    formData.append("video", videoFile);
    formData.append("exercise_type", exerciseType);

    try {
      const response = await fetch("/upload_and_analyze", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      console.log("Backend response:", data);

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Analysis failed.");
      }

      setResult(data);
      setStatus("✅ Analysis complete!");
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
            <div className="feedback-box">
              <div className="results-grid">
                <p><strong>Exercise:</strong> {result?.analysis?.exercise || exerciseType}</p>
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
            </div>

            {result.gemini_feedback && (
              <div className="feedback-box">
                <h3 className="feedback-title">✨ Gemini Feedback</h3>
                <div className="feedback-content">
                  <p><strong>📝 Title:</strong> {result.gemini_feedback.title}</p>
                  <p><strong>💪 Strengths:</strong> {result.gemini_feedback.strengths}</p>
                  <p><strong>⚠️ Areas for Improvement:</strong> {result.gemini_feedback.areas_for_improvement}</p>
                  <p><strong>✅ Actionable Tips:</strong> {result.gemini_feedback.actionable_tips}</p>
                  <p><strong>🧠 Overall Assessment:</strong> {result.gemini_feedback.overall_assessment}</p>
                </div>
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
        <Route path="/register" element={<RegisterPage />} />
      </Routes>
    </Router>
  );
}

export default App;
