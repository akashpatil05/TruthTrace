import React from 'react';
import { Link } from 'react-router-dom';
import './Footer.css';

function Footer() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <p className="footer__copy">
          &copy; 2024 TruthTrace. Research-grade verification.
        </p>
        <nav className="footer__links">
          <Link to="/about" className="footer__link">About</Link>
          <Link to="/methodology" className="footer__link">Methodology</Link>
          <a href="https://github.com" target="_blank" rel="noreferrer" className="footer__link">GitHub</a>
          <a href="#" className="footer__link">Docs</a>
          <a href="#" className="footer__link">Disclaimer</a>
        </nav>
      </div>
    </footer>
  );
}

export default Footer;
