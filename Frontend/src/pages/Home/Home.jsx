import { useLocation } from 'react-router-dom';
import Hero from '../../components/Hero/Hero';
import PipelineSteps from '../../components/PipelineSteps/PipelineSteps';
import BentoGrid from '../../components/BentoGrid/BentoGrid';
import Footer from '../../components/Footer/Footer';
import './Home.css';

function Home() {
  const location = useLocation();
  const initialText = location.state?.initialText || '';

  return (
    <>
      <main className="home-main">
        <Hero initialText={initialText} />
        <PipelineSteps />
        <BentoGrid />
      </main>
      <Footer />
    </>
  );
}

export default Home;
