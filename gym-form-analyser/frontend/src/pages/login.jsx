import "../assets/styles/login.css";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";

const Login = () => {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    console.log("handleSubmit reached");

    try {
      console.log("Sending fetch request...");
      const res = await fetch("/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: userId,
          password,
        }),
      });

      const data = await res.json();
      console.log("Received response:", data);

      if (res.ok) {
        localStorage.setItem('token', data.token);
        console.log(data.token)
        navigate("/dashboard");
      } else {
        alert(data.error || "login failed.");
      }
    } catch (err) {
      console.error("Fetch error:", err);
      alert("Server error.");
    }
  };
  return (
    <div className="login-page">
      <div className="login-card">
        <h2>Login</h2>

        <form onSubmit={handleSubmit}>
          <input type="text" placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button type="submit">Log In</button>
        </form>

        <div className="alt-option">
          Don’t have an account? <Link to="/create-account">Register</Link>
        </div>
      </div>
    </div>
  );
};

export default Login;
