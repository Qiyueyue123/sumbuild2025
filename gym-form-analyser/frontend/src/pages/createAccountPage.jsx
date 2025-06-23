import '../assets/styles/createAccountPage.css';
import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';

const CreateAccount = () => {
  const [userId, setUserId] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
  e.preventDefault();
  console.log("Form submitted");

  if (password !== confirmPassword) {
    alert("Passwords do not match");
    return;
  }

  try {
    console.log("Sending fetch request...");
    const res = await fetch('/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        email,
        password,
      }),
    });

    const data = await res.json();
    console.log("Received response:", data);

    if (res.ok) {
      alert("Account created successfully!");
      navigate('/');
    } else {
      alert(data.error || "Account creation failed.");
    }
  } catch (err) {
    console.error("Fetch error:", err);
    alert("Server error.");
  }
};


  return (
    <div className="create-account-page">
      <div className="create-account-card">
        <h2>Create Account</h2>

        <form onSubmit={handleSubmit}>
          <input type="text" placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} required />
          <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <input type="password" placeholder="Confirm Password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
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
