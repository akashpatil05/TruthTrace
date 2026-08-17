import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import './Navbar.css';

function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header>
      <nav className="navbar">
        <div className="navbar__inner">
          {/* Brand Logo */}
          {/* <NavLink to="/" className="navbar__brand">
            <img
              alt="TruthTrace Logo"
              className="navbar__logo"
              // src="public/white-removebg-preview.png"
            // src="https://lh3.googleusercontent.com/aida-public/AB6AXuAF1I0_8PN3gVuORVDje4MaQ0CvJq4m0y1HguygbJP5hguEbAUNSW_KZ3oJ20hcqyZt4T2ocjmr_pyK-gFrlh794Lmiwa3YEPEYgJmQDUglftwakG96w50KwB7h6J7p4e2qoxbaOKDhaoP8TqogQXJTBI-qUApCYkze1XduQ3P2HKl1fP-My-KA7MPMgSd2oCfAjLSFd6mSJvwsUmAYEbG-HGx6_DI0-Ug7eC2jFDBBzCPkwBQpCvFU"
            />
            <span className="navbar__brand-name">TruthTrace</span>
          </NavLink> */}
          <span className="navbar__brand-name">TruthTrace</span>
          {/* Desktop Navigation Links */}
          <ul className="navbar__links">
            <li>
              <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Home</NavLink>
            </li>
            <li>
              <NavLink to="/history" className={({ isActive }) => isActive ? 'active' : ''}>History</NavLink>
            </li>
            <li>
              <NavLink to="/methodology" className={({ isActive }) => isActive ? 'active' : ''}>Methodology</NavLink>
            </li>
            <li>
              <NavLink to="/about" className={({ isActive }) => isActive ? 'active' : ''}>About</NavLink>
            </li>
          </ul>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Theme Toggle */}
            <button className="navbar__toggle-btn" aria-label="Toggle theme">
              <span className="material-symbols-outlined">light_mode</span>
            </button>
            {/* Mobile Hamburger */}
            <button
              className="navbar__hamburger"
              aria-label="Open menu"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <span className="material-symbols-outlined">
                {mobileOpen ? 'close' : 'menu'}
              </span>
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile Menu */}
      <div className={`navbar__mobile-menu ${mobileOpen ? 'open' : ''}`}>
        <NavLink to="/" end onClick={() => setMobileOpen(false)}>Home</NavLink>
        <NavLink to="/history" onClick={() => setMobileOpen(false)}>History</NavLink>
        <NavLink to="/methodology" onClick={() => setMobileOpen(false)}>Methodology</NavLink>
        <NavLink to="/about" onClick={() => setMobileOpen(false)}>About</NavLink>
      </div>
    </header>
  );
}

export default Navbar;
