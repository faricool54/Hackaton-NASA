import { useEffect, useRef, useState } from 'react';

export function useScienceRequest<T>(identity: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    active.current?.abort(); setData(null); setError(''); setBusy(false);
    return () => active.current?.abort();
  }, [identity]);
  async function run(load: (signal: AbortSignal) => Promise<T>) {
    active.current?.abort();
    const abort = new AbortController(); active.current = abort;
    setBusy(true); setError(''); setData(null);
    const timer = setTimeout(() => {
      abort.abort(); setBusy(false); setError('Stopped waiting after 160 seconds. The service may finish; retry to check its cache.');
    }, 160_000);
    try {
      const result = await load(abort.signal);
      if (!abort.signal.aborted) setData(result);
    } catch (e) { if (!abort.signal.aborted) setError((e as Error).message); }
    finally { clearTimeout(timer); if (!abort.signal.aborted) setBusy(false); }
  }
  function stop() {
    active.current?.abort(); setBusy(false);
    setError('Stopped waiting. Server work may continue; retry to retrieve its result.');
  }
  return { data, error, busy, run, stop };
}
