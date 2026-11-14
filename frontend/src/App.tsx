// Tiny hash router (no dependency, works on any static host):
//   #/              home (field list)
//   #/field/<id>    blink viewer for one field
//   #/about         science + credits
import { useEffect, useState } from 'react';
import { client } from './api/client';
import { AboutPage } from './pages/AboutPage';
import { FieldPage } from './pages/FieldPage';
import { HomePage } from './pages/HomePage';

function useHashRoute(): string[] {
  const parse = () => window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const [parts, setParts] = useState(parse);
  useEffect(() => {
    const onChange = () => {
      setParts(parse());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return parts;
}

export function App() {
  const [page, arg] = useHashRoute();
  return (
    <>
      <header className="topbar">
        <a href="#/" className="brand">
          Errante <span className="muted">· SPHEREx sky explorer</span>
        </a>
        <nav>
          <a href="#/">Fields</a>
          <a href="#/about">About</a>
          <span className="muted small">
            {client.config.mode === 'api' ? 'live API' : 'static'} data
          </span>
        </nav>
      </header>
      {page === 'field' && arg ? <FieldPage fieldId={arg} /> : page === 'about' ? <AboutPage /> : <HomePage />}
      <footer className="muted small">
        NASA Space Apps Challenge 2026 · Planet X and SPHEREx · SPHEREx data: NASA/JPL-Caltech/IPAC IRSA
      </footer>
    </>
  );
}
