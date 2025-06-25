import { useLocation } from "react-router-dom";
import { useState } from "react";
import TitleBanner from "../components/titleBanner";
import SideBarNav from "../components/sideBarNav";
import "../assets/styles/workoutDetails.css";

const WorkoutDetails = () => {
  const { state } = useLocation();
  const originalWorkout = state?.workout;
  const [editMode, setEditMode] = useState(false);
  const [workout, setWorkout] = useState(originalWorkout);
  const [newSets, setNewSets] = useState([]);

  const handleVideoUpload = (e, index) => {
    const file = e.target.files[0];
    if (!file) return;
    const updated = [...newSets];
    updated[index] = { video: file };
    setNewSets(updated);
  };

  const handleAddSet = () => {
    setNewSets([...newSets, { video: null }]);
  };

  const handleCancel = () => {
    setWorkout(originalWorkout);
    setEditMode(false);
  };

  return (
    <div className="app-layout">
      <TitleBanner />
      <div className="main-area">
        <SideBarNav className="sidebar" />
        <div className="content-area workout-details-page">
          <div className="header-row">
            <h2>Workout Details</h2>
            {!editMode && (
              <button className="edit-btn" onClick={() => setEditMode(true)}>
                Edit
              </button>
            )}
          </div>

          <div className="summary-banner">
            <strong>Total Score:</strong> {workout?.score?.toFixed(1)}% |{" "}
            <strong>Date:</strong>{" "}
            {editMode ? (
              <input
                type="date"
                value={workout.date}
                onChange={(e) =>
                  setWorkout({ ...workout, date: e.target.value })
                }
              />
            ) : (
              workout.date
            )}{" "}
            | <strong>Sets:</strong> {workout.num_sets}
          </div>

          {workout.results.map((set, index) => (
            <div key={index} className="set-container">
              <h4>Set {index + 1}</h4>
              <div className="video-feedback-row">
                {set.processed_url ? (
                  <video controls>
                    <source src={set.processed_url} type="video/mp4" />
                  </video>
                ) : (
                  <p className="no-video">
                    No processed video available (quick analysis)
                  </p>
                )}
                <div className="feedback-section">
                  <p>
                    <strong>Good Reps / Total Reps:</strong>{" "}
                    {set.analysis.good_reps} / {set.analysis.total_reps}
                  </p>
                  <p>
                    <strong>Avg Peak Angle:</strong>{" "}
                    {set.analysis.average_peak_angle}
                  </p>
                  <p>
                    <strong>Avg Descent Angle:</strong>{" "}
                    {set.analysis.average_descent_angle}
                  </p>
                  <p>
                    <strong>Feedback:</strong> {set.analysis.overall_feedback}
                  </p>
                  <p>
                    <strong>Score for set:</strong>{" "}
                    {(set.analysis.score * 100).toFixed(1)}%
                  </p>

                  {typeof set.gemini_feedback === "object" && (
                    <>
                      <p>
                        <strong>Strengths:</strong>{" "}
                        {set.gemini_feedback.strengths?.join(" ")}
                      </p>
                      <p>
                        <strong>Improvements:</strong>{" "}
                        {set.gemini_feedback.areas_for_improvement?.join(" ")}
                      </p>
                      <p>
                        <strong>Tips:</strong>{" "}
                        {set.gemini_feedback.actionable_tips?.join(" ")}
                      </p>
                      <p>
                        <strong>Overall:</strong>{" "}
                        {set.gemini_feedback.overall_assessment}
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}

          {editMode &&
            newSets.map((set, index) => (
              <div key={`new-${index}`} className="set-container new-set-card">
                <button
                  className="remove-set-btn"
                  onClick={() => {
                    const updatedSets = [...newSets];
                    updatedSets.splice(index, 1);
                    setNewSets(updatedSets);
                  }}
                >
                  ×
                </button>
                <h4>New Set {workout.results.length + index + 1}</h4>
                <div className="video-feedback-row">
                  {set.video ? (
                    <video controls>
                      <source
                        src={URL.createObjectURL(set.video)}
                        type="video/mp4"
                      />
                    </video>
                  ) : (
                    <>
                      <label
                        htmlFor={`new-file-upload-${index}`}
                        className="custom-file-upload"
                      >
                        Upload Video
                      </label>
                      <input
                        id={`new-file-upload-${index}`}
                        type="file"
                        accept="video/*"
                        style={{ display: "none" }}
                        onChange={(e) => handleVideoUpload(e, index)}
                      />
                    </>
                  )}
                </div>
              </div>
            ))}

          {editMode && (
            <div style={{ marginTop: "20px" }}>
              <button className="add-set-btn" onClick={handleAddSet}>
                + Add Set
              </button>
            </div>
          )}

          {editMode && (
            <div className="edit-controls">
              <button className="cancel-btn" onClick={handleCancel}>
                Cancel
              </button>
              <button
                className="save-btn"
                onClick={() => {
                  /* Save changes handler */
                }}
              >
                Save Changes
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WorkoutDetails;
