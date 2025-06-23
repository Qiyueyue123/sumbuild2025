import { useState } from "react";
import TitleBanner from "../components/titleBanner";
import SideBarNav from "../components/sideBarNav";
import "../assets/styles/newWorkout.css";

const NewWorkout = () => {
  const [exerciseType, setExerciseType] = useState("pushups");
  const [numSets, setNumSets] = useState(1);
  const [videos, setVideos] = useState(Array(1).fill(null));
  const [workoutDate, setWorkoutDate] = useState(() => {
    const today = new Date().toISOString().split("T")[0];
    return today;
  });
  const token = localStorage.getItem("token");

  const handleExerciseChange = (e) => {
    setExerciseType(e.target.value);
  };

  const handleSetChange = (e) => {
    const newNum = parseInt(e.target.value);
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
    try {
      const formData = new FormData();
      formData.append("workout_date", workoutDate);
      formData.append("exercise_type", exerciseType);
      formData.append("num_sets", numSets);

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
      if (data.success) {
        alert("Analysis complete!");
        console.log("Result:", data);
      } else {
        alert("Error: " + data.error);
      }
    } catch (error) {
      console.error("Analysis failed:", error);
      alert("An error occurred while analyzing.");
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

            <div className="upload-section">
              {videos.map((video, index) => (
                <div key={index} className="set-upload">
                  <h4>Set {index + 1}</h4>
                  {video ? (
                    <div>
                      <video width="300" controls>
                        <source
                          src={URL.createObjectURL(video)}
                          type="video/mp4"
                        />
                        Your browser does not support the video tag.
                      </video>
                      <div className="button-row">
                        <button onClick={() => handleRemoveVideo(index)}>
                          Remove Video
                        </button>
                      </div>
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
                disabled={videos.some((v) => v === null)}
                onClick={handleAnalyze}
              >
                Analyze Videos
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewWorkout;
