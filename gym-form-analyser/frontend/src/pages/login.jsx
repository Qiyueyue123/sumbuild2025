import '../assets/styles/login.css';
import { Link } from 'react-router-dom';

const Login = () => {
  return (
    <div className="login-page">
      <div className="login-card">
        <h2>Login</h2>

        <form>
          <input type="text" placeholder="User ID" required />
          <input type="password" placeholder="Password" required />
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
