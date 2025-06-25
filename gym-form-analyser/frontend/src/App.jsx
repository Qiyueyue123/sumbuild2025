import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Login from "./pages/login";
import CreateAccount from "./pages/createAccountPage";
import Homepage from "./pages/homepage";
import NewWorkout from "./pages/newWorkoutPage";
import WorkoutLogs from "./pages/workoutLogs";
import WorkoutDetails from "./pages/workoutDetailsPage";
import PrivateRoute from "./components/privateRoute";
import ProfilePage from "./pages/profilePage";


function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/create-account" element={<CreateAccount />} />
        <Route path="/penis" element={<h1>Penis</h1>} />

        <Route element={<PrivateRoute />}>
          <Route path="/dashboard" element={<Homepage />} />
          <Route path="/new-workout" element={<NewWorkout />} />
          <Route path="/workout-logs" element={<WorkoutLogs />} />
          <Route path="/workout-details" element={<WorkoutDetails />} />
          <Route path="/profilePage" element={<ProfilePage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
