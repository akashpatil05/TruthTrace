import React from 'react';
import './PipelineSteps.css';

const steps = [
  {
    icon: 'input',
    title: '1. Query Expansion',
    description: 'The input claim is analyzed and expanded into multiple specific search queries to ensure broad coverage.',
    primary: true,
  },
  {
    icon: 'database',
    title: '2. Source Retrieval',
    description: 'High-authority documents are retrieved via semantic search from curated databases and the open web.',
    primary: false,
  },
  {
    icon: 'psychology',
    title: '3. Cross-Reference',
    description: 'LLMs evaluate the retrieved evidence against the original claim, scoring relevancy and identifying contradictions.',
    primary: false,
  },
  {
    icon: 'fact_check',
    title: '4. Final Verdict',
    description: 'A transparent, source-cited verdict is generated, exposing the underlying reasoning and confidence levels.',
    primary: false,
  },
];

function PipelineSteps() {
  return (
    <section className="pipeline">
      <h2 className="pipeline__title">Verification Pipeline</h2>
      <div className="pipeline__grid">
        {steps.map((step) => (
          <div key={step.title} className="pipeline__step">
            <div className={`pipeline__step-icon${step.primary ? '' : ' pipeline__step-icon--muted'}`}>
              <span className="material-symbols-outlined">{step.icon}</span>
            </div>
            <h3 className="pipeline__step-title">{step.title}</h3>
            <p className="pipeline__step-desc">{step.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default PipelineSteps;
