import { useEffect, useState } from "react";

import { CatalogPage } from "./pages/CatalogPage";
import { DatasetPage } from "./pages/DatasetPage";
import { RunPage, RunsPage } from "./pages/RunsPage";

type ServiceState = "checking" | "available" | "unavailable";

const MESSAGES: Record<ServiceState, string> = {
  checking: "Comprobando el servicio…",
  available: "Servicio disponible.",
  unavailable: "Servicio no disponible.",
};

async function readHealth(signal: AbortSignal): Promise<ServiceState> {
  try {
    const response = await fetch("/health", { signal });
    const body: unknown = response.ok ? await response.json() : null;
    const ok = typeof body === "object" && body !== null && "status" in body && body.status === "ok";
    return ok ? "available" : "unavailable";
  } catch {
    return "unavailable";
  }
}

function ServiceHealth() {
  const [state, setState] = useState<ServiceState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    void readHealth(controller.signal).then((result) => {
      if (!controller.signal.aborted) {
        setState(result);
      }
    });
    return () => controller.abort();
  }, []);

  return <p role="status" data-state={state}>{MESSAGES[state]}</p>;
}

function Page({ path }: { path: string }) {
  if (path === "/" || path === "/datasets") return <CatalogPage />;
  if (path === "/runs") return <RunsPage />;
  const detail = /^\/(datasets|runs)\/([0-9a-f-]{36})$/i.exec(path);
  if (detail?.[1] === "datasets" && detail[2]) return <DatasetPage datasetId={detail[2]} />;
  if (detail?.[1] === "runs" && detail[2]) return <RunPage runId={detail[2]} />;
  return <h1>Página no encontrada</h1>;
}

export function App({ path = window.location.pathname }: { path?: string }) {
  return <>
    <header>
      <div className="shell masthead">
        <a className="brand" href="/">Financial Data Hub</a>
        <nav aria-label="Principal">
          <a href="/datasets" aria-current={path === "/" || path.startsWith("/datasets") ? "page" : undefined}>Catálogo</a>
          <a href="/runs" aria-current={path.startsWith("/runs") ? "page" : undefined}>Ejecuciones</a>
        </nav>
      </div>
    </header>
    <main className="shell"><Page path={path} /></main>
    <footer className="shell"><ServiceHealth /></footer>
  </>;
}
