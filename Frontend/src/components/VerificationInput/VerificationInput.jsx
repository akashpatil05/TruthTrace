import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { verifyClaim } from '../../services/api';
import './VerificationInput.css';

const sampleClaims = [
  "Scientists have discovered that drinking coffee completely prevents cancer.",
  "COVID-19 mRNA vaccines alter human DNA and contain tracking microchips.",
  "Human activities and greenhouse gas emissions have unequivocally caused global warming.",
];

function VerificationInput({ initialText = '' }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Claim');
  const [inputText, setInputText] = useState(initialText);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [loadingStep, setLoadingStep] = useState('');

  const tabs = ['Claim', 'Headline', 'Full Article'];

  const handleVerify = async () => {
    const claimToVerify = inputText.trim();
    if (!claimToVerify) {
      setErrorMsg('Please enter a claim or statement to verify.');
      return;
    }

    setIsLoading(true);
    setErrorMsg('');
    setLoadingStep('Embedding claim and searching FAISS vector index...');

    try {
      // Simulate quick pipeline feedback step
      const stepTimer = setTimeout(() => {
        setLoadingStep('Evaluating evidence stance & authority scores...');
      }, 700);

      const result = await verifyClaim(claimToVerify);
      clearTimeout(stepTimer);

      // Store in localStorage for persistence across reloads
      const record = {
        id: Date.now().toString(),
        claim: claimToVerify,
        tab: activeTab,
        date: new Date().toISOString(),
        result,
      };

      try {
        localStorage.setItem('truthTrace_latest', JSON.stringify(record));
        const past = JSON.parse(localStorage.getItem('truthTrace_history') || '[]');
        past.unshift(record);
        localStorage.setItem('truthTrace_history', JSON.stringify(past.slice(0, 20)));
      } catch (e) {
        console.warn('LocalStorage save failed:', e);
      }

      // Navigate to /history with the real verification data
      navigate('/history', { state: record });
    } catch (err) {
      console.error('Verification error:', err);
      setErrorMsg(
        err.message || 'Unable to connect to TruthTrace backend. Ensure uvicorn is running on port 8001.'
      );
    } finally {
      setIsLoading(false);
      setLoadingStep('');
    }
  };

  return (
    <div className="verification-console">
      {/* Segmented Tab Control */}
      <div className="verification-console__tabs">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={`verification-console__tab${activeTab === tab ? ' active' : ''}`}
            onClick={() => setActiveTab(tab)}
            disabled={isLoading}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Textarea */}
      <div className="verification-console__input-wrap">
        <label className="sr-only" htmlFor="verification-input">
          Enter {activeTab.toLowerCase()} to verify
        </label>
        <textarea
          id="verification-input"
          className="verification-console__textarea"
          placeholder="Enter a claim, statement, or article to verify against high-authority sources..."
          rows={4}
          value={inputText}
          onChange={(e) => {
            setInputText(e.target.value);
            if (errorMsg) setErrorMsg('');
          }}
          disabled={isLoading}
        />

        {/* Quick sample pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
          <span style={{ fontSize: '11px', color: 'var(--color-on-surface-variant)', fontFamily: 'var(--font-mono)' }}>
            TRY PRE-SEEDED EXAMPLES:
          </span>
          {sampleClaims.map((claim, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setInputText(claim)}
              disabled={isLoading}
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid var(--color-glass-border)',
                borderRadius: '4px',
                color: 'var(--color-primary)',
                fontSize: '11px',
                padding: '3px 8px',
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: 'var(--font-body)',
              }}
            >
              {claim.slice(0, 48)}...
            </button>
          ))}
        </div>

        {errorMsg && (
          <div style={{ color: 'var(--color-verdict-false)', fontSize: '13px', marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>error</span>
            {errorMsg}
          </div>
        )}

        {isLoading && (
          <div style={{ color: 'var(--color-primary)', fontSize: '13px', marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="material-symbols-outlined" style={{ animation: 'spin 1.5s linear infinite', fontSize: '18px' }}>
              sync
            </span>
            <span>{loadingStep || 'Processing claim against evidence corpus...'}</span>
          </div>
        )}
      </div>

      {/* Action Bar */}
      <div className="verification-console__actions">
        <button
          className="verification-console__submit"
          onClick={handleVerify}
          disabled={isLoading || !inputText.trim()}
          style={{ opacity: isLoading || !inputText.trim() ? 0.7 : 1, cursor: isLoading ? 'wait' : 'pointer' }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>
            {isLoading ? 'hourglass_top' : 'manage_search'}
          </span>
          {isLoading ? 'Verifying Claim...' : 'Verify Claim'}
        </button>
      </div>
    </div>
  );
}

export default VerificationInput;
