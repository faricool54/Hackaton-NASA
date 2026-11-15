import { useEffect, useState } from 'react';
import { client, createClient } from '../api/client';
import type { FieldSummary, Manifest } from '../api/types';
import { SkyExplorer } from '../components/SkyExplorer';
import '../styles/explorer.css';

export function HomePage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState('');
  const [realFields, setRealFields] = useState<FieldSummary[]>([]);

  useEffect(() => {
    let current = true;
    client.getManifest().then((result) => { if (current) setManifest(result); })
      .catch((e: Error) => { if (current) setError(e.message); });
    return () => { current = false; };
  }, []);

  const realBase = `${import.meta.env.BASE_URL}data/real/`;
  useEffect(() => {
    if (client.config.mode !== 'static' || client.config.staticBase === realBase) return;
    let current = true;
    createClient({ ...client.config, staticBase: realBase }).getManifest()
      .then((real) => { if (current) setRealFields(real.fields); })
      .catch(() => { /* A static deployment can contain only the demo. */ });
    return () => { current = false; };
  }, [realBase]);

  const realLink = `${import.meta.env.BASE_URL}?mode=static&dataset=real#/`;
  const sequences = [
    ...(manifest?.fields ?? []).map((field) => ({ field, href: `#/field/${field.id}` })),
    ...realFields.map((field) => ({ field, href: `${realLink}field/${field.id}` })),
  ];

  return <main className="xp-app">
    <SkyExplorer sequences={sequences} systems={manifest?.systems ?? []}
      synthetic={manifest?.synthetic ?? (client.config.mode === 'static' && client.config.staticBase.endsWith('/demo/'))}
      manifestError={error} />
  </main>;
}
