import React from 'react';
import './BentoGrid.css';

function BentoGrid() {
  return (
    <section className="bento">
      <div className="bento__header">
        <div className="bento__header-text">
          <h2 className="bento__title">Transparent by Design</h2>
          <p className="bento__subtitle">
            Moving beyond black-box AI. TruthTrace prioritizes provenance, presenting verifiable evidence alongside every conclusion.
          </p>
        </div>
      </div>

      <div className="bento__grid">
        {/* Card 1: Traceable Evidence — wide */}
        <div className="bento__card bento__card--wide">
          <div>
            <h3 className="bento__card-title">Traceable Evidence Cards</h3>
            <p className="bento__card-desc">
              Every fact is anchored to a specific source excerpt. Relevancy scores and confidence toggles allow for deep manual review of the AI's reasoning.
            </p>
          </div>
          {/* Decorative mock UI */}
          <div className="bento__evidence-mock">
            <div className="bento__evidence-header">
              <span className="bento__evidence-source">nature.com</span>
              <span className="bento__evidence-relevancy">Relevancy: 94%</span>
            </div>
            <p className="bento__evidence-quote">
              "...observed a statistically significant increase in mitochondrial density following a 6-week HIIT protocol..."
            </p>
            <div className="bento__progress-bar-bg">
              <div
                className="bento__progress-bar-fill"
                style={{ width: '94%', background: 'var(--color-verdict-true)' }}
              />
            </div>
          </div>
        </div>

        {/* Card 2: Confidence Metrics */}
        <div className="bento__card">
          <div>
            <h3 className="bento__card-title">Confidence Metrics</h3>
            <p className="bento__card-desc">
              Visual status indicators and quantitative scoring prevent false certainty.
            </p>
          </div>
          <div className="bento__metrics">
            <div>
              <div className="bento__metric-row">
                <span>Supporting</span>
                <span className="bento__metric-value--true">82%</span>
              </div>
              <div className="bento__progress-bar-bg">
                <div
                  className="bento__progress-bar-fill"
                  style={{ width: '82%', background: 'var(--color-verdict-true)', borderRadius: '9999px' }}
                />
              </div>
            </div>
            <div>
              <div className="bento__metric-row">
                <span>Contradicting</span>
                <span className="bento__metric-value--false">12%</span>
              </div>
              <div className="bento__progress-bar-bg">
                <div
                  className="bento__progress-bar-fill"
                  style={{ width: '12%', background: 'var(--color-verdict-false)', borderRadius: '9999px' }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Domain Authority */}
        <div className="bento__card">
          <div>
            <h3 className="bento__card-title">Domain Authority</h3>
            <p className="bento__card-desc">
              Retrieval focuses on peer-reviewed journals, recognized news outlets, and official databases.
            </p>
          </div>
          <div className="bento__domain-tags">
            {['gov', 'edu', 'arxiv', 'pubmed'].map((tag) => (
              <span key={tag} className="bento__domain-tag">{tag}</span>
            ))}
          </div>
        </div>

        {/* Card 4: Nuanced Verdicts — wide */}
        <div className="bento__card bento__card--wide">
          <div>
            <h3 className="bento__card-title">Nuanced Verdicts</h3>
            <p className="bento__card-desc">
              Not everything is True or False. The system categorizes claims into precise states: Verified, Partially True, Misleading, or Unverifiable.
            </p>
          </div>
          <div className="bento__verdict-badges">
            <span className="bento__badge bento__badge--true">
              <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>check_circle</span>
              Verified
            </span>
            <span className="bento__badge bento__badge--neutral">
              <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>info</span>
              Context Needed
            </span>
            <span className="bento__badge bento__badge--warn">
              <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>warning</span>
              Misleading
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

export default BentoGrid;
