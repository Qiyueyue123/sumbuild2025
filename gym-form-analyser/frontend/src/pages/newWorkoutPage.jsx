import { useState } from "react";
import TitleBanner from "../components/titleBanner";
import SideBarNav from "../components/sideBarNav";
import "../assets/styles/newWorkout.css";

const NewWorkout = () => {
  const [exerciseType, setExerciseType] = useState("pushups");
  const [analysisType, setAnalysisType] = useState("FULL");
  const [numSets, setNumSets] = useState(1);
  const [videos, setVideos] = useState(Array(1).fill(null));
  const [workoutDate, setWorkoutDate] = useState(() => {
    const today = new Date().toISOString().split("T")[0];
    return today;
  });
  const token = localStorage.getItem("token");
  const [analysisResults, setAnalysisResults] = useState([]);
  const [totalScore, setTotalScore] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleExerciseChange = (e) => {
    setExerciseType(e.target.value);
  };

  const handleSetChange = (e) => {
    const value = e.target.value;

    if (value === "") {
      //let user clear input
      setNumSets(""); // temporarily allow empty string
      return;
    }

    const newNum = parseInt(value);

    if (isNaN(newNum) || newNum < 1) return; // for invalid num and zero

    setNumSets(newNum);
    setVideos((prev) => {
      const newVideos = [...prev];
      newVideos.length = newNum;
      return newVideos.fill(null, prev.length, newNum);
    });
  };

  const handleVideoUpload = (e, index) => {
    const file = e.target.files[0];
    if (file) {
      const updatedVideos = [...videos];
      updatedVideos[index] = file;
      setVideos(updatedVideos);
    }
  };

  const handleRemoveVideo = (index) => {
    const updatedVideos = [...videos];
    updatedVideos[index] = null;
    setVideos(updatedVideos);
  };
  const handleAnalyze = async () => {
    setIsLoading(true);
    setAnalysisResults([]);
    setTotalScore(null);
    try {
      const formData = new FormData();
      formData.append("workout_date", workoutDate);
      formData.append("exercise_type", exerciseType);
      formData.append("num_sets", numSets);
      formData.append("analysisType", analysisType);

      videos.forEach((video) => {
        if (video) {
          formData.append("video", video);
        }
      });

      const response = await fetch("/upload_and_analyze", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const data = await response.json();

      if (data.success && Array.isArray(data.results)) {
        const mapped = data.results.map((r) => ({
          analysis: r?.analysis || {},
          geminiFeedback: r?.gemini_feedback || "No feedback",
          processedUrl: r?.processed_url || "",
        }));

        setAnalysisResults(mapped);
        setTotalScore(data.score);
        alert("Analysis complete!");
      } else {
        alert("Error: " + (data.error || "Unexpected server response"));
      }
    } catch (error) {
      console.error("Analysis failed:", error);
      alert("An error occurred while analyzing.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-layout">
      <TitleBanner />
      <div className="main-area">
        <SideBarNav />
        <div className="content-area">
          <div className="upload-page">
            <h2>Upload New Workout</h2>

            <div className="form-section">
              <label>Workout Type:</label>
              <select value={exerciseType} onChange={handleExerciseChange}>
                <option value="pushups">Push-ups</option>
                <option value="squats">Squats</option>
                <option value="pullups">Pull-ups</option>
              </select>
            </div>

            <div className="form-section">
              <label>Workout Date:</label>
              <input
                type="date"
                value={workoutDate}
                onChange={(e) => setWorkoutDate(e.target.value)}
              />
            </div>
            <div className="form-section">
              <label>Number of Sets:</label>
              <input
                type="number"
                min="1"
                value={numSets}
                onChange={handleSetChange}
              />
            </div>

            <div className="form-section">
              <label>Analysis Mode:</label>
              <div
                style={{
                  display: "flex",
                  borderRadius: "6px",
                  overflow: "hidden",
                  width: "fit-content",
                  border: "1px solid #aaa",
                }}
              >
                <button
                  type="button"
                  onClick={() => setAnalysisType("QUICK")}
                  style={{
                    padding: "10px 20px",
                    backgroundColor:
                      analysisType === "QUICK" ? "#4CAF50" : "#8B0000",
                    color: "white",
                    border: "none",
                    fontWeight: "bold",
                    cursor: "pointer",
                  }}
                >
                  Quick
                </button>
                <button
                  type="button"
                  onClick={() => setAnalysisType("FULL")}
                  style={{
                    padding: "10px 20px",
                    backgroundColor:
                      analysisType === "FULL" ? "#4CAF50" : "#8B0000",
                    color: "white",
                    border: "none",
                    fontWeight: "bold",
                    cursor: "pointer",
                  }}
                >
                  Full
                </button>
              </div>
            </div>
            {totalScore !== null && (
              <div className="total-score-banner">
                <strong>Total Score for current workout:</strong> {totalScore}%
              </div>
            )}

            <div className="upload-section">
              {videos.map((video, index) => (
                <div key={index} className="set-upload">
                  <h4>Set {index + 1}</h4>
                  {video ? (
                    <div className="video-feedback-row">
                      <div className="video-container">
                        <video
                          key={
                            analysisResults[index]?.processedUrl
                              ? `processed-${index}`
                              : `original-${index}`
                          }
                          controls
                        >
                          <source
                            src={
                              analysisResults[index]?.processedUrl
                                ? analysisResults[index].processedUrl
                                : URL.createObjectURL(video)
                            }
                            type="video/mp4"
                          />
                        </video>

                        <div className="button-row">
                          <button onClick={() => handleRemoveVideo(index)}>
                            Remove Video
                          </button>
                        </div>
                      </div>

                      {analysisResults[index] && (
                        <div className="feedback-section">
                          <p>
                            <strong> Good Reps / Total Reps:</strong>{" "}
                            {analysisResults[index].analysis?.good_reps} /{" "}
                            {analysisResults[index].analysis?.total_reps}
                          </p>
                          <p>
                            <strong> Avg Peak Angle:</strong>{" "}
                            {
                              analysisResults[index].analysis
                                ?.average_peak_angle
                            }
                          </p>
                          <p>
                            <strong> Avg Descent Angle:</strong>{" "}
                            {
                              analysisResults[index].analysis
                                ?.average_descent_angle
                            }
                          </p>
                          <p>
                            <strong> Feedback:</strong>{" "}
                            {analysisResults[index].analysis?.overall_feedback}
                          </p>
                          <p>
                            <strong> Score for set:</strong>{" "}
                            {analysisResults[index].analysis?.score * 100} %
                          </p>
                          {analysisType === "FULL" && typeof analysisResults[index].geminiFeedback ===
                          "object" ? (
                            <>
                              <p>
                                <strong> Strengths:</strong>{" "}
                                {analysisResults[
                                  index
                                ].geminiFeedback?.strengths?.join(", ")}
                              </p>
                              <p>
                                <strong> Improvements:</strong>{" "}
                                {analysisResults[
                                  index
                                ].geminiFeedback?.areas_for_improvement?.join(
                                  ", "
                                )}
                              </p>
                              <p>
                                <strong> Tips:</strong>{" "}
                                {analysisResults[
                                  index
                                ].geminiFeedback?.actionable_tips?.join(", ")}
                              </p>
                              <p>
                                <strong> Overall:</strong>{" "}
                                {
                                  analysisResults[index].geminiFeedback
                                    ?.overall_assessment
                                }
                              </p>
                            </>
                          ) : ( 
                            <p>
                              <strong>No Gemini feedback as quick analysis was selected.</strong>{" "}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <>
                      <label
                        htmlFor={`file-upload-${index}`}
                        className="custom-file-upload"
                      >
                        Upload Video
                      </label>
                      <input
                        id={`file-upload-${index}`}
                        type="file"
                        accept="video/*"
                        onChange={(e) => handleVideoUpload(e, index)}
                        style={{ display: "none" }}
                      />
                    </>
                  )}
                </div>
              ))}
            </div>
            <div className="analyze-section">
              <button
                className="analyze-button"
                disabled={videos.some((v) => v === null) || isLoading}
                onClick={handleAnalyze}
              >
                {isLoading ? "Analyzing..." : "Analyze Videos"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewWorkout;
