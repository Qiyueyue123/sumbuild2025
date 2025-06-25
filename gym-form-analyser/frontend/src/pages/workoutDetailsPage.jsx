import TitleBanner from '../components/titleBanner';
import SideBarNav from '../components/sideBarNav';

const WorkoutDetails = () => {
  return (
    <div className="app-layout">
      <TitleBanner />
      <div className="main-area">
        <SideBarNav />
      </div>
    </div>
  );
};

export default WorkoutDetails;