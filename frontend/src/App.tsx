import { useEffect, useState } from "react";

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

export function App() {
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

  return (
    <main>
      <h1>Financial Data Hub</h1>
      <p role="status" data-state={state}>
        {MESSAGES[state]}
      </p>
      <p>El catálogo de datasets todavía no está implementado.</p>
    </main>
  );
}
