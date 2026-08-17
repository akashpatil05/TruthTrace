import React from 'react';
import './History.css';
import Footer from '../../components/Footer/Footer';

const contradictingEvidence = [
  {
    source: 'congress.gov',
    type: 'Primary Source',
    quote: '"...this Act shall apply solely to entities engaging in the bulk transfer, sale, or sharing of precise geolocation information derived from consumer devices."',
    date: 'Oct 12, 2023',
  },
  {
    source: 'eff.org',
    type: 'Analysis',
    quote: '"Despite initial rumors, our legal review confirms the final draft removes any ambiguous language that could have been weaponized against private communication platforms."',
    date: 'Oct 14, 2023',
  },
];

const supportingEvidence = [
  {
    source: 'tech-rumors-daily.net',
    type: 'Blog/Opinion',
    quote: '"If this passes, say goodbye to your private chats. The government is essentially banning encryption by requiring backdoor access."',
    date: 'Oct 10, 2023',
    italic: true,
  },
];

function EvidenceCard({ item, color }) {
  return (
    <div className={`history-evidence history-evidence--${color}`}>
      <div className="history-evidence__header">
        <div className="history-evidence__source">
          <span>{item.source}</span>
        </div>
        <span className="history-evidence__type">{item.type}</span>
      </div>
      <p className="history-evidence__quote" style={item.italic ? { fontStyle: 'italic' } : {}}>
        {item.quote}
      </p>
      <div className="history-evidence__footer">
        <span className="history-evidence__date">{item.date}</span>
        <a href="#" className="history-evidence__link">
          View Source <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>open_in_new</span>
        </a>
      </div>
    </div>
  );
}

function History() {
  return (
    <>
      <main className="history-page">
        {/* Claim header */}
        <div className="history-claim">
          <div style={{ flex: 1 }}>
            <span className="history-claim__label">Verified Claim</span>
            <blockquote className="history-claim__quote">
              "The recent legislative bill includes a provision that entirely outlaws the use of end-to-end encryption for personal communications."
            </blockquote>
          </div>
          <button className="history-claim__edit-btn">
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>edit</span>
            Edit / Re-verify
          </button>
        </div>

        {/* Verdict card */}
        <div className="history-verdict">
          <div style={{ flex: 1 }}>
            <div className="history-verdict__badge history-verdict__badge--false">
              <span className="material-symbols-outlined" style={{ fontSize: '18px', color: 'var(--color-verdict-false)' }}>cancel</span>
              <span className="history-verdict__badge-label">FALSE</span>
            </div>
            <h2 className="history-verdict__title">Claim is factually incorrect.</h2>
            <p className="history-verdict__summary">
              The legislative bill in question regulates commercial data brokers and does not contain any provisions referencing or prohibiting end-to-end encryption for individual citizens.
            </p>
          </div>
          {/* Confidence Dial */}
          <div className="history-verdict__dial">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="8" />
              <circle
                cx="50" cy="50" r="45" fill="none"
                stroke="var(--color-verdict-false)"
                strokeWidth="8"
                strokeDasharray="283"
                strokeDashoffset="42.45"
                strokeLinecap="round"
              />
            </svg>
            <div className="history-verdict__dial-value">
              <span className="history-verdict__pct history-verdict__pct--false">85%</span>
              <span className="history-verdict__pct-label">Confidence</span>
            </div>
          </div>
        </div>

        {/* Reasoning accordion */}
        <details className="history-accordion">
          <summary>
            Why this verdict?
            <span className="material-symbols-outlined">expand_more</span>
          </summary>
          <div className="history-accordion__body">
            <ul>
              <li><strong>Direct Text Analysis:</strong> Cross-referencing the exact text of Bill HR.2394 reveals no mention of "encryption," "end-to-end," or related cryptographic terms.</li>
              <li><strong>Scope Misattribution:</strong> The bill strictly focuses on third-party data aggregators selling bulk location data.</li>
              <li><strong>Consensus:</strong> Multiple independent legal analyses and digital rights organizations have verified the bill's limited scope.</li>
            </ul>
          </div>
        </details>

        {/* Conflict banner */}
        <div className="history-conflict">
          <span className="material-symbols-outlined" style={{ color: 'var(--color-verdict-misleading)' }}>info</span>
          <span>Sources show conflicting interpretations. Review evidence columns below for complete context.</span>
        </div>

        {/* Evidence columns */}
        <div className="history-col">
          <h3 className="history-col__heading">
            <span className="material-symbols-outlined" style={{ color: 'var(--color-verdict-false)' }}>gavel</span>
            Contradicting Evidence
            <span className="history-col__count">3 Sources</span>
          </h3>
          {contradictingEvidence.map((e) => (
            <EvidenceCard key={e.source} item={e} color="false" />
          ))}
        </div>

        <div className="history-col" style={{ marginTop: 0 }}>
          <h3 className="history-col__heading">
            <span className="material-symbols-outlined" style={{ color: 'var(--color-verdict-true)' }}>check_circle</span>
            Supporting Evidence
            <span className="history-col__count">1 Source</span>
          </h3>
          {supportingEvidence.map((e) => (
            <EvidenceCard key={e.source} item={e} color="true" />
          ))}
        </div>
      </main>

      {/* Metadata bar */}
      <div className="history-meta">
        <div className="history-meta__inner">
          <div>Verified on: 2023-10-27T14:32:01Z | Pipeline Version: v2.4.1 (Strict Mode)</div>
          <div>Processed 4 documents across 3 domains in 1.2s.</div>
          <div style={{ maxWidth: '384px', textAlign: 'right', opacity: 0.7, color: 'var(--color-outline)' }}>
            Disclaimer: This report is generated algorithmically by correlating available public data. It does not constitute legal or professional advice.
          </div>
        </div>
      </div>

      <Footer />

      {/* Floating action bar */}
      <div className="history-fab">
        <button className="history-fab__btn" title="Share Report">
          <span className="material-symbols-outlined">share</span>
        </button>
        <div className="history-fab__divider" />
        <button className="history-fab__btn" title="Export PDF">
          <span className="material-symbols-outlined">picture_as_pdf</span>
        </button>
        <div className="history-fab__divider" />
        <button className="history-fab__btn history-fab__btn--flag" title="Flag inaccurate">
          <span className="material-symbols-outlined">flag</span>
        </button>
      </div>
    </>
  );
}

export default History;
