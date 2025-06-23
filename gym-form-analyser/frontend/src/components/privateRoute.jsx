import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';

const PrivateRoute = () => {
  const [isValid, setIsValid] = useState(null); // null = loading, true = verified, false = invalid

  useEffect(() => {
    const verifyToken = async () => {
      const token = localStorage.getItem('token');
      if (!token) {
        setIsValid(false);
        return;
      }

      try {
        const res = await fetch('/verify-token', {
          method: 'GET',
          headers: {
            Authorization: 'Bearer ' + token,
          },
        });

        if (res.status === 200) {
          setIsValid(true);
        } else {
          localStorage.removeItem('token');
          setIsValid(false);
        }
      } catch (err) {
        console.error('Token verification failed:', err);
        localStorage.removeItem('token');
        setIsValid(false);
      }
    };

    verifyToken();
  }, []);

  if (isValid === null) return <div>Loading...</div>; // or a spinner if you like
  if (!isValid) return <Navigate to="/" replace />;   // redirect to login

  return <Outlet />; // render child route if valid
};

export default PrivateRoute;
