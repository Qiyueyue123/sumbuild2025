import { useEffect, useState } from 'react';
import TitleBanner from '../components/titleBanner';
import SideBarNav from '../components/sideBarNav';
import '../assets/styles/newWorkout.css'; // Reuse layout styling

const ProfilePage = () => {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [showPopup, setShowPopup] = useState(false);

  const token = localStorage.getItem('token');

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await fetch('/get-profile', {
          method: 'GET',
          headers: {
            Authorization: 'Bearer ' + token,
          },
        });
        const data = await res.json();
        if (res.ok) {
          setEmail(data.email);
          setUsername(data.user_id);
        } else {
          setMessage(data.error || 'Failed to load profile');
        }
      } catch (err) {
        console.error('Profile fetch error:', err);
        setMessage('Error fetching profile');
      }
    };
    fetchProfile();
  }, [token]);

  const isValidEmail = (email) => {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();

    if (!isValidEmail(email)) {
      setMessage('Invalid email format');
      return;
    }

    try {
      const res = await fetch('/update-profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token,
        },
        body: JSON.stringify({
          email,
          user_id: username,
          password,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage('Profile updated successfully');
        setShowPopup(true);
        setTimeout(() => setShowPopup(false), 3000);
      } else {
        setMessage(data.error || 'Update failed');
      }
    } catch (err) {
      console.error('Update error:', err);
      setMessage('Server error during update');
    }
  };

  return (
    <div className="app-layout">
      <TitleBanner />
      <div className="main-area">
        <SideBarNav />
        <div className="content-area">
          <div className="upload-page">
            <h2>Profile Settings</h2>
            {message && <div style={{ marginBottom: '20px', color: message.includes('successfully') ? 'green' : 'red' }}>{message}</div>}
            {showPopup && (
              <div style={{
                position: 'fixed',
                top: '20px',
                right: '20px',
                backgroundColor: '#4caf50',
                color: 'white',
                padding: '10px 20px',
                borderRadius: '5px',
                boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
                zIndex: 1000,
              }}>
                ✅ Profile updated!
              </div>
            )}
            <form onSubmit={handleUpdate}>
              <div className="form-section">
                <label>Email:</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="form-section">
                <label>Username:</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="form-section">
                <label>New Password (leave blank to keep current):</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <button className="analyze-button" type="submit">Update Profile</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;