import React from 'react';
import './Methodology.css';
import Footer from '../../components/Footer/Footer';

const steps = [
  {
    icon: 'psychiatry',
    title: 'Claim Ingestion',
    desc: 'User query is parsed to identify core factual assertions and logical premises.',
    primary: true,
  },
  {
    icon: 'manage_search',
    title: 'Source Retrieval',
    desc: 'Semantic search queries our curated database of peer-reviewed journals and verified databases.',
    primary: false,
  },
  {
    icon: 'account_tree',
    title: 'LLM Reasoning',
    desc: 'Large Language Models cross-reference retrieved text against the original claim for logical consistency.',
    primary: false,
  },
  {
    icon: 'fact_check',
    title: 'Final Verdict',
    desc: 'A definitive rating is synthesized, strictly bound by the cited evidence presented.',
    primary: false,
  },
];

function Methodology() {
  return (
    <>
      <main className="methodology-page">
        {/* Hero */}
        <section className="meth-hero">
          <h1 className="meth-hero__title">Our Methodology</h1>
          <p className="meth-hero__subtitle">
            TruthTrace employs a rigorous, multi-stage Retrieval-Augmented Generation (RAG) pipeline designed for
            academic-grade verification. We prioritize provenance, transparency, and evidence over stylistic generation.
          </p>
        </section>

        {/* Pipeline */}
        <section>
          <h2 className="meth-pipeline__heading">The Verification Pipeline</h2>
          <div className="meth-pipeline__grid">
            {steps.map((step) => (
              <div key={step.title} className="meth-step">
                <div className={`meth-step__icon ${step.primary ? 'meth-step__icon--primary' : 'meth-step__icon--secondary'}`}>
                  <span className="material-symbols-outlined">{step.icon}</span>
                </div>
                <h3 className="meth-step__title">{step.title}</h3>
                <p className="meth-step__desc">{step.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

export default Methodology;
