import '../assets/styles/createAccountPage.css';
import { Link } from 'react-router-dom';


const CreateAccount = () => {
  return (
    <div className="create-account-page">
      <div className="create-account-card">
        <h2>Create Account</h2>

        <form>
          <input type="text" placeholder="User ID" required />
          <input type="email" placeholder="Email" required />
          <input type="password" placeholder="Password" required />
          <input type="password" placeholder="Confirm Password" required />
          <button type="submit">Create Account</button>
        </form>

        <div className="alt-option">
          Already have an account? <Link to="/">Log in</Link>
        </div>
      </div>
    </div>
  );
};

export default CreateAccount;
