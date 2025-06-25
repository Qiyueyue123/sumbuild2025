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
  const [deletedSetIds, setDeletedSetIds] = useState([]);
  const [analysisType, setAnalysisType] = useState(
    originalWorkout.results[0].processed_url ? "QUICK" : "FULL"
  );
  const [exerciseType, setExerciseType] = useState(
    workout.results[0]?.analysis?.exercise || ""
  );

  const handleVideoUpload = (e, index) => {
    const file = e.target.files[0];
    if (!file) return;
    const updated = [...newSets];
    updated[index] = { video: file };
    setNewSets(updated);
  };

  const handleAddSet = () => {
    setNewSets([...newSets, { video: null }]);
    setWorkout({ ...workout, num_sets: workout.num_sets + 1 });
  };

  const handleCancel = () => {
    setWorkout(originalWorkout);
    setNewSets([]);
    setEditMode(false);
  };

  const handleDeleteExistingSet = (index) => {
    const deletedSet = workout.results[index];
    if (
      window.confirm(
        `Are you sure you want to delete Set ${
          index + 1
        }? This action cannot be undone.`
      )
    ) {
      const updatedResults = [...workout.results];
      updatedResults.splice(index, 1);
      setWorkout({
        ...workout,
        results: updatedResults,
        num_sets: workout.num_sets - 1,
      });
      if (deletedSet.id) {
        setDeletedSetIds((prev) => [...prev, deletedSet.id]);
      }
    }
  };

  const handleRemoveNewSetVideo = (index) => {
    const updated = [...newSets];
    updated[index] = { video: null };
    setNewSets(updated);
  };

  const hasChanges = () => {
    const workoutChanged =
      JSON.stringify(workout) !== JSON.stringify(originalWorkout);
    const newSetsExist = newSets.some((set) => set.video !== null);
    return workoutChanged || newSetsExist;
  };

  const handleSaveChanges = async () => {
    const formData = new FormData();
    formData.append("workout_date", workout.date);
    formData.append("exercise_type", exerciseType);
    formData.append("num_sets", workout.num_sets);
    formData.append("analysisType", analysisType);
    formData.append("id", workout.id);
    formData.append("deleted_set_ids", JSON.stringify(deletedSetIds));
    newSets.forEach((set) => {
      if (set.video) {
        formData.append("video", set.video);
      }
    });

    const token = localStorage.getItem("token");
    console.log(formData);
    const response = await fetch("/update_workout", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
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
            | <strong>Type:</strong>{" "}
            {editMode ? (
              <select
                value={exerciseType}
                onChange={(e) => {
                  const newType = e.target.value;

                  // Update all results' analysis.exercise
                  const updatedResults = workout.results.map((set) => {
                    if (set.analysis) {
                      return {
                        ...set,
                        analysis: {
                          ...set.analysis,
                          exercise: newType,
                        },
                      };
                    }
                    return set;
                  });

                  // Update both state variables
                  setExerciseType(newType);
                  setWorkout({ ...workout, results: updatedResults });
                }}
                style={{ marginLeft: "8px" }}
              >
                <option value="pushups">Push-ups</option>
                <option value="squats">Squats</option>
                <option value="pullups">Pull-ups</option>
              </select>
            ) : (
              workout.results[0]?.analysis?.exercise.charAt(0).toUpperCase() +
              workout.results[0]?.analysis?.exercise.slice(1)
            )}{" "}
            | <strong>Sets:</strong> {workout.num_sets}
          </div>

          {workout.results.map((set, index) => (
            <div
              key={index}
              className="set-container"
              style={{ position: "relative" }}
            >
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

              {editMode && (
                <button
                  className="remove-set-btn bottom-right"
                  onClick={() => handleDeleteExistingSet(index)}
                >
                  Delete Set
                </button>
              )}
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
                    <>
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <video controls>
                          <source
                            src={URL.createObjectURL(set.video)}
                            type="video/mp4"
                          />
                        </video>
                        <button
                          className="remove-video-btn"
                          onClick={() => handleRemoveNewSetVideo(index)}
                          style={{ marginTop: "10px", alignSelf: "start" }}
                        >
                          Remove Video
                        </button>
                      </div>
                    </>
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

          {editMode &&
            deletedSetIds.length === originalWorkout.results.length &&
            workout.num_sets > 0 && (
              <div className="analysis-mode-wrapper">
                <p className="analysis-mode-label">Analysis Mode:</p>
                <div className="analysis-mode-buttons">
                  <button
                    type="button"
                    className={`analysis-btn left-btn ${
                      analysisType === "QUICK" ? "active" : ""
                    }`}
                    onClick={() => setAnalysisType("QUICK")}
                  >
                    Quick
                  </button>
                  <button
                    type="button"
                    className={`analysis-btn right-btn ${
                      analysisType === "FULL" ? "active" : ""
                    }`}
                    onClick={() => setAnalysisType("FULL")}
                  >
                    Full
                  </button>
                </div>
              </div>
            )}

          {editMode && (
            <div className="edit-controls">
              <button className="cancel-btn" onClick={handleCancel}>
                Cancel
              </button>
              <button
                className="save-btn"
                onClick={handleSaveChanges}
                disabled={!hasChanges() || Number(workout.num_sets) === 0}
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
