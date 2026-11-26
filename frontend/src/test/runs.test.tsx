import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { Run, RunStatus } from "../api/schema";
import { RunsPage } from "../pages/RunsPage";

it("distinguishes four run statuses, truncation, and zero from unknown measurements", async () => {
  const statuses: RunStatus[] = ["running", "succeeded", "partial", "failed"];
  const items: Run[] = statuses.map((status, index) => ({
    id: status, source_id: `synthetic-${status}`, status, truncated: index === 1,
    started_at: "2026-01-01T00:00:00Z", finished_at: null, pages_processed: 1, received: 2,
    created: 1, updated: 0, unchanged: 1, rejected: 0, failures: 0,
    requests: index === 0 ? null : 5, duration_ms: null, persistence_ms: index === 3 ? 0 : null,
  }));
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ items, total: 4, page: 1, page_size: 20 })));
  const { container } = render(<RunsPage />);
  expect(await screen.findByText("En curso")).toBeDefined();
  for (const text of ["Exitosa", "Parcial", "Fallida", "Truncada"]) expect(screen.getByText(text)).toBeDefined();
  expect(container.querySelectorAll('[data-status="succeeded"]')).toHaveLength(1);
  const persistence = [...container.querySelectorAll("dt")].filter(dt => dt.textContent === "Persistencia (ms)");
  expect(persistence.map(dt => dt.nextElementSibling?.textContent)).toEqual([
    "Desconocido", "Desconocido", "Desconocido", "0",
  ]);
});

it("differentiates loading, no runs and unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
  const loading = render(<RunsPage />);
  expect(screen.getByText("Cargando…")).toBeDefined();
  loading.unmount();

  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ items: [], total: 0 })));
  const empty = render(<RunsPage />);
  expect(await screen.findByText("Sin resultados.")).toBeDefined();
  empty.unmount();

  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
  render(<RunsPage />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
