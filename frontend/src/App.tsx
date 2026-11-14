// Tiny hash router (no dependency, works on any static host):
//   #/              home (field list)
//   #/field/<id>    blink viewer for one field
//   #/about         science + credits
//   #/systems                3D systems list (WS7)
//   #/system/<id>[/<body>]   3D view of a system; a body id "enters" that body
import { useEffect, useState } from 'react';
import { client } from './api/client';
import { AboutPage } from './pages/AboutPage';
import { FieldPage } from './pages/FieldPage';
import { HomePage } from './pages/HomePage';
import { SystemPage } from './pages/SystemPage';
import { SystemsPage } from './pages/SystemsPage';

function useHashRoute(): string[] {
  const parse = () => window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const [parts, setParts] = useState(parse);
  useEffect(() => {
    let prev = parse();
    const onChange = () => {
      const next = parse();
      // Don't jump to the top when only the sub-item changes (e.g. selecting a body in 3D).
      if (next[0] !== prev[0] || next[1] !== prev[1]) window.scrollTo(0, 0);
      prev = next;
      setParts(next);
    };
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return parts;
}

export function App() {
  const [page, arg, sub] = useHashRoute();
  return (
    <>
      <header className="topbar">
        <a href="#/" className="brand">
          Errante <span className="muted">· SPHEREx sky explorer</span>
        </a>
        <nav>
          <a href="#/">Fields</a>
          <a href="#/systems">3D Systems</a>
          <a href="#/about">About</a>
          <span className="muted small">
            {client.config.mode === 'api' ? 'live API' : 'static'} data
          </span>
        </nav>
      </header>
      {page === 'field' && arg ? (
        <FieldPage fieldId={arg} />
      ) : page === 'system' && arg ? (
        <SystemPage systemId={arg} bodyId={sub ?? null} />
      ) : page === 'systems' ? (
        <SystemsPage />
      ) : page === 'about' ? (
        <AboutPage />
      ) : (
        <HomePage />
      )}
      <footer className="muted small">
        NASA Space Apps Challenge 2026 · Planet X and SPHEREx · SPHEREx data: NASA/JPL-Caltech/IPAC IRSA
      </footer>
    </>
  );
}
