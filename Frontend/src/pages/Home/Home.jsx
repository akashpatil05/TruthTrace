import React from 'react';
import Hero from '../../components/Hero/Hero';
import PipelineSteps from '../../components/PipelineSteps/PipelineSteps';
import BentoGrid from '../../components/BentoGrid/BentoGrid';
import Footer from '../../components/Footer/Footer';
import './Home.css';

function Home() {
  return (
    <>
      <main className="home-main">
        <Hero />
        <PipelineSteps />
        <BentoGrid />
      </main>
      <Footer />
    </>
  );
}

export default Home;
