import React from 'react';
import './Hero.css';
import VerificationInput from '../VerificationInput/VerificationInput';

function Hero({ initialText = '' }) {
  return (
    <section className="hero">
      <h1 className="hero__title">
        Evidence-grounded fact verification, powered by RAG + LLMs.
      </h1>
      <p className="hero__subtitle">
        A research-grade intelligence terminal designed to parse claims, retrieve verifiable sources, and deliver transparent reasoning over stylistic flair.
      </p>
      <VerificationInput initialText={initialText} />
    </section>
  );
}

export default Hero;
