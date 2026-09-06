import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './History.css';
import Footer from '../../components/Footer/Footer';

function EvidenceCard({ item, color }) {
  return (
    <div className={`history-evidence history-evidence--${color}`}>
      <div className="history-evidence__header">
        <div className="history-evidence__source">
          <span style={{ fontWeight: 600 }}>{item.source}</span>
        </div>
        <span className="history-evidence__type">{item.type || 'Primary Source'}</span>
      </div>
      <p className="history-evidence__quote" style={{ fontStyle: 'italic', marginBottom: '12px' }}>
        "{item.text || item.quote}"
      </p>
      <div className="history-evidence__footer">
        <span className="history-evidence__date">{item.publication_date || item.date || 'Recent'}</span>
        {item.url && item.url !== '#' ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="history-evidence__link"
          >
            View Source <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>open_in_new</span>
          </a>
        ) : (
          <span className="history-evidence__link" style={{ opacity: 0.6 }}>
            Indexed Source
          </span>
        )}
      </div>
    </div>
  );
}

function History() {
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    // 1. Check React Router state
    if (location.state && location.state.result) {
      setData(location.state);
      return;
    }

    // 2. Check localStorage for latest verification
    try {
      const saved = localStorage.getItem('truthTrace_latest');
      if (saved) {
        setData(JSON.parse(saved));
        return;
      }
    } catch (e) {
      console.warn('Failed to load verification from storage', e);
    }

    // 3. Fallback default showcase demo
    setData({
      claim: "Scientists have discovered that drinking coffee completely prevents cancer.",
      tab: "Claim",
      date: new Date().toISOString(),
      result: {
        verdict: "FALSE",
        confidence: 0.88,
        summary: "The claim is refuted by international cancer research authorities. Scientific consensus from WHO and IARC confirms coffee does not prevent cancer or cure oncological diseases.",
        reasoning: [
          "Direct contradictory findings identified from World Health Organization - IARC with high semantic relevance.",
          "Documented excerpt: 'A working group of 23 international scientists convened by IARC evaluated drinking coffee... scientists emphasize that drinking coffee does not prevent cancer.'",
          "No authoritative supporting evidence was found in the indexed corpus to substantiate the assertion."
        ],
        supporting_evidence: [],
        contradicting_evidence: [
          {
            source: "World Health Organization - IARC",
            type: "Peer Reviewed Journal",
            text: "The experts found that drinking coffee was not classifiable as to its carcinogenicity to humans. While some observational studies have suggested inverse associations for certain types of cancer, scientists emphasize that drinking coffee does not prevent cancer, cure tumors, or provide complete immunity against oncological diseases.",
            publication_date: "2023-06-15",
            url: "https://www.iarc.who.int/news-events/iarc-evaluates-drinking-coffee-mate-and-very-hot-beverages/",
          }
        ],
        total_evidence_analyzed: 1,
        processing_time_ms: 12.4
      }
    });
  }, [location.state]);

  if (!data || !data.result) {
    return (
      <main className="history-page">
        <div className="history-claim">
          <p>Loading verification data...</p>
        </div>
      </main>
    );
  }

  const { claim, result } = data;
  const verdict = result.verdict || 'INSUFFICIENT_EVIDENCE';
  const confidence = result.confidence !== undefined ? result.confidence : 0.5;
  const confidencePct = Math.round(confidence * 100);

  // Verdict visual configurations
  const verdictConfigs = {
    TRUE: {
      badgeClass: 'history-verdict__badge--true',
      pctClass: 'history-verdict__pct--true',
      color: 'var(--color-verdict-true)',
      icon: 'check_circle',
      title: 'Claim is factually supported.',
    },
    FALSE: {
      badgeClass: 'history-verdict__badge--false',
      pctClass: 'history-verdict__pct--false',
      color: 'var(--color-verdict-false)',
      icon: 'cancel',
      title: 'Claim is factually incorrect.',
    },
    MISLEADING: {
      badgeClass: 'history-verdict__badge--misleading',
      pctClass: 'history-verdict__pct--misleading',
      color: 'var(--color-verdict-misleading)',
      icon: 'warning',
      title: 'Claim is misleading or disputed.',
    },
    INSUFFICIENT_EVIDENCE: {
      badgeClass: 'history-verdict__badge--insufficient',
      pctClass: 'history-verdict__pct--insufficient',
      color: 'var(--color-text-muted)',
      icon: 'help',
      title: 'Insufficient authoritative evidence.',
    },
  };

  const currentCfg = verdictConfigs[verdict] || verdictConfigs.INSUFFICIENT_EVIDENCE;
  const strokeDashoffset = 283 - (283 * confidence);

  const supporting = result.supporting_evidence || [];
  const contradicting = result.contradicting_evidence || [];
  const hasConflict = (supporting.length > 0 && contradicting.length > 0) || verdict === 'MISLEADING';

  const handleEditReverify = () => {
    navigate('/', { state: { initialText: claim } });
  };

  return (
    <>
      <main className="history-page">
        {/* Claim header */}
        <div className="history-claim">
          <div style={{ flex: 1 }}>
            <span className="history-claim__label">Verified {data.tab || 'Claim'}</span>
            <blockquote className="history-claim__quote">
              "{claim}"
            </blockquote>
          </div>
          <button className="history-claim__edit-btn" onClick={handleEditReverify}>
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>edit</span>
            Edit / Re-verify
          </button>
        </div>

        {/* Verdict card */}
        <div className="history-verdict">
          <div style={{ flex: 1 }}>
            <div className={`history-verdict__badge ${currentCfg.badgeClass}`}>
              <span className="material-symbols-outlined" style={{ fontSize: '18px', color: currentCfg.color }}>
                {currentCfg.icon}
              </span>
              <span className="history-verdict__badge-label">{verdict.replace('_', ' ')}</span>
            </div>
            <h2 className="history-verdict__title">{currentCfg.title}</h2>
            <p className="history-verdict__summary">
              {result.summary}
            </p>
          </div>

          {/* Confidence Dial */}
          <div className="history-verdict__dial">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="8" />
              <circle
                cx="50" cy="50" r="45" fill="none"
                stroke={currentCfg.color}
                strokeWidth="8"
                strokeDasharray="283"
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
              />
            </svg>
            <div className="history-verdict__dial-value">
              <span className={`history-verdict__pct ${currentCfg.pctClass}`}>{confidencePct}%</span>
              <span className="history-verdict__pct-label">Confidence</span>
            </div>
          </div>
        </div>

        {/* Reasoning accordion */}
        {result.reasoning && result.reasoning.length > 0 && (
          <details className="history-accordion" open>
            <summary>
              Why this verdict?
              <span className="material-symbols-outlined">expand_more</span>
            </summary>
            <div className="history-accordion__body">
              <ul>
                {result.reasoning.map((step, idx) => (
                  <li key={idx}>
                    {step}
                  </li>
                ))}
              </ul>
            </div>
          </details>
        )}

        {/* Conflict banner */}
        {hasConflict && (
          <div className="history-conflict">
            <span className="material-symbols-outlined" style={{ color: 'var(--color-verdict-misleading)' }}>info</span>
            <span>Sources show conflicting interpretations or omissions. Review the supporting and contradicting evidence columns below for complete context.</span>
          </div>
        )}

        {/* Evidence columns */}
        <div className="history-col">
          <h3 className="history-col__heading">
            <span className="material-symbols-outlined" style={{ color: 'var(--color-verdict-false)' }}>gavel</span>
            Contradicting Evidence
            <span className="history-col__count">{contradicting.length} Source{contradicting.length !== 1 ? 's' : ''}</span>
          </h3>
          {contradicting.length > 0 ? (
            contradicting.map((e, idx) => (
              <EvidenceCard key={idx} item={e} color="false" />
            ))
          ) : (
            <div style={{ color: 'var(--color-outline)', fontSize: '14px', fontStyle: 'italic', padding: '16px', border: '1px dashed var(--color-glass-border)', borderRadius: '8px' }}>
              No contradicting evidence found in indexed corpus.
            </div>
          )}
        </div>

        <div className="history-col">
          <h3 className="history-col__heading">
            <span className="material-symbols-outlined" style={{ color: 'var(--color-verdict-true)' }}>check_circle</span>
            Supporting Evidence
            <span className="history-col__count">{supporting.length} Source{supporting.length !== 1 ? 's' : ''}</span>
          </h3>
          {supporting.length > 0 ? (
            supporting.map((e, idx) => (
              <EvidenceCard key={idx} item={e} color="true" />
            ))
          ) : (
            <div style={{ color: 'var(--color-outline)', fontSize: '14px', fontStyle: 'italic', padding: '16px', border: '1px dashed var(--color-glass-border)', borderRadius: '8px' }}>
              No supporting evidence found in indexed corpus.
            </div>
          )}
        </div>
      </main>

      {/* Metadata bar */}
      <div className="history-meta">
        <div className="history-meta__inner">
          <div>Verified at: {new Date(data.date || Date.now()).toLocaleString()} | Engine: FAISS Dense Retrieval + Grounded Reasoning</div>
          <div>Analyzed {result.total_evidence_analyzed || (supporting.length + contradicting.length)} evidence items in {result.processing_time_ms || 18}ms.</div>
          <div style={{ maxWidth: '384px', textAlign: 'right', opacity: 0.7, color: 'var(--color-outline)' }}>
            Strict Grounding Policy: Verdicts are derived strictly from retrieved authoritative sources without ungrounded extrapolation.
          </div>
        </div>
      </div>

      <Footer />
    </>
  );
}

export default History;
