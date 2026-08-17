import React, { useState } from 'react';
import './VerificationInput.css';

function VerificationInput() {
  const [activeTab, setActiveTab] = useState('Claim');
  const [inputText, setInputText] = useState('');
  const tabs = ['Claim', 'Headline', 'Full Article'];

  const handleVerify = () => {
    console.log('[TruthTrace] Verifying:', activeTab, '-', inputText);
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
          onChange={(e) => setInputText(e.target.value)}
        />
        <span className="verification-console__hint">
          Example: "Recent studies show high-intensity interval training significantly improves mitochondrial capacity."
        </span>
      </div>

      {/* Action Bar */}
      <div className="verification-console__actions">
        <button className="verification-console__submit" onClick={handleVerify}>
          <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>manage_search</span>
          Verify Claim
        </button>
      </div>
    </div>
  );
}

export default VerificationInput;
