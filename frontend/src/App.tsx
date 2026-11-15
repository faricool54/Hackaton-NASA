// Tiny hash router (no dependency, works on any static host):
//   #/              home (field list)
//   #/field/<id>    blink viewer for one field
//   #/about         science + credits
//   #/systems                3D systems list (WS7)
//   #/system/<id>[/<body>]   3D view of a system; a body id "enters" that body
import { useEffect, useState } from 'react';
import { client } from './api/client';
import { ErrorBoundary } from './components/ErrorBoundary';
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
  const currentPage = page === 'about' || page === 'systems' || (arg && (page === 'field' || page === 'system'))
    ? page : 'home';

  useEffect(() => {
    document.documentElement.dataset.page = currentPage;
  }, [currentPage]);

  return (
    <>
      <header className="app-topbar">
        <a href="#/" className="app-brand">
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width={24} height={24} />
          <span>Errante</span>
          <span className="app-brand-context">SPHEREx sky explorer</span>
        </a>
        <nav className="app-nav" aria-label="Main navigation">
          <a href="#/" aria-current={currentPage === 'home' ? 'page' : currentPage === 'field' ? 'location' : undefined}>Explore</a>
          <a href="#/systems" aria-current={currentPage === 'systems' ? 'page' : currentPage === 'system' ? 'location' : undefined}>3D models</a>
          <a href="#/about" aria-current={currentPage === 'about' ? 'page' : undefined}>About</a>
        </nav>
        <span className="u-badge app-mode">{client.config.mode === 'api' ? 'Live API' : 'Static data'}</span>
      </header>
      <ErrorBoundary what="This page" key={`${page ?? ''}/${arg ?? ''}`}>
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
      </ErrorBoundary>
      {currentPage !== 'home' && <footer className="app-footer">
        NASA Space Apps Challenge 2026 · Planet X and SPHEREx · SPHEREx data: NASA/JPL-Caltech/IPAC IRSA
      </footer>}
    </>
  );
}
