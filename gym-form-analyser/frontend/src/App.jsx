import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Login from "./pages/login";
import CreateAccount from "./pages/createAccountPage";
import Homepage from "./pages/homepage";
import NewWorkout from "./pages/newWorkoutPage";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/create-account" element={<CreateAccount />} />
        <Route path="/dashboard" element={<Homepage />} />
        <Route path="/new-workout" element={<NewWorkout />} />
        <Route path="/penis" element={<h1>Penis</h1>} />
      </Routes>
    </Router>
  );
}

export default App;
