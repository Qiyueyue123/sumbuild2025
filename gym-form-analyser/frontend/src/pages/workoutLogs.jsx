import { useState, useEffect } from "react";
import TitleBanner from "../components/titleBanner";
import SideBarNav from "../components/sideBarNav";
import { useNavigate } from "react-router-dom";
import "../assets/styles/workoutLogs.css";

const getColorFromScore = (score) => {
  if (score >= 80) return "green";
  if (score >= 50) return "orange";
  return "red";
};

const WorkoutLogs = () => {
  const [allWorkouts, setAllWorkouts] = useState([]);
  const [sortKey, setSortKey] = useState("date");
  const [sortOrder, setSortOrder] = useState("desc");
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await fetch("/all_workouts", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          throw new Error("Response Status: " + response.status);
        }
        const data = await response.json();

        const flattened = Object.entries(data)
          .map(([date, entries]) => {
            return entries.map((entry) => ({ date, ...entry }));
          })
          .flat();

        setAllWorkouts(flattened);
      } catch (error) {
        console.log(error.message);
      }
    };

    fetchData();
  }, []);

  const handleDeleteWorkout = async (workoutToDelete) => {
    if (!window.confirm("Are you sure you want to delete this workout?"))
      return;

    try {
      const token = localStorage.getItem("token");
      const response = await fetch("/delete_workout", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          workout_id: workoutToDelete.id,
          workout_date: workoutToDelete.date
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to delete workout");
      }

      // Remove from local state
      setAllWorkouts((prev) =>
        prev.filter((w) => !(w.id === workoutToDelete.id))
      );
    } catch (err) {
      console.error(err.message);
      alert("Failed to delete workout");
    }
  };
  const sortedWorkouts = [...allWorkouts].sort((a, b) => {
    if (sortKey === "date") {
      return sortOrder === "asc"
        ? new Date(a.date) - new Date(b.date)
        : new Date(b.date) - new Date(a.date);
    } else if (sortKey === "exercise") {
      return sortOrder === "asc"
        ? a.results[0].analysis.exercise.localeCompare(
            b.results[0].analysis.exercise
          )
        : b.results[0].analysis.exercise.localeCompare(
            a.results[0].analysis.exercise
          );
    }
    return 0;
  });

  const handleSortChange = (key) => {
    if (key === sortKey) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("asc");
    }
  };

  const handleViewDetails = (workout) => {
    navigate("/workout-details", { state: { workout } });
  };

  return (
    <div className="app-layout">
      <TitleBanner />
      <div className="main-area">
        <SideBarNav />
        <div className="logs-container">
          <h2>Workout Logs</h2>
          <div className="sort-controls">
            <button onClick={() => handleSortChange("date")}>
              Sort by Date
            </button>
            <button onClick={() => handleSortChange("exercise")}>
              Sort by Exercise
            </button>
          </div>
          <table className="workout-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Exercise</th>
                <th>Sets</th>
                <th>Score</th>
                <th>View</th>
                <th>Delete</th>
              </tr>
            </thead>
            <tbody>
              {sortedWorkouts.map((workout, i) => (
                <tr key={i}>
                  <td>{workout.date}</td>
                  <td>{workout.results[0].analysis.exercise}</td>
                  <td>{workout.num_sets}</td>
                  <td>
                    <div
                      className="score-circle"
                      style={{
                        backgroundColor: getColorFromScore(workout.score),
                      }}
                    >
                      {Math.round(workout.score)}
                    </div>
                  </td>
                  <td>
                    <button
                      className="view-btn"
                      onClick={() => handleViewDetails(workout)}
                    >
                      View Details
                    </button>
                  </td>
                  <td>
                    <button
                      className="delete-btn"
                      onClick={() => handleDeleteWorkout(workout)}
                      title="Delete Workout"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default WorkoutLogs;
