import { NavLink } from 'react-router-dom';
import '../assets/styles/sideBarNav.css';

const SidebarNav = () => {
  return (
    <aside className="sidebar">
      <nav className="sidebar-links">
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/new-workout">New Workout</NavLink>
        <NavLink to="/historyPage">Workout Logs</NavLink>
        <NavLink to="/calendarPage">Calendar</NavLink>
        <NavLink to="/profilePage">Profile</NavLink>
      </nav>
    </aside>
  );
};

export default SidebarNav;
