import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { DatasetDetail } from "../api/schema";
import { DatasetPage } from "../pages/DatasetPage";
import { dataset } from "./catalogFixtures";

it("shows attribution, permissions, provenance and verification while linking only safe HTTPS", async () => {
  const detail: DatasetDetail = {
    ...dataset, tags: [], official_url: null, created_at: null, published_at: null,
    metadata_updated_at: null, data_updated_at: null, updated_at: null, access_conditions: null,
    redistribution_conditions: "Condiciones sintéticas", extraction_permission: "undetermined",
    redistribution_permission: "denied", first_seen_at: dataset.last_seen_at,
    licenses: [
      { name: "Licencia segura", url: "https://example.org/terms", note: null },
      { name: "Licencia insegura", url: "javascript:alert(1)", note: null },
    ],
    locators: [{ kind: "api", status: "invalid", url: "http://example.org/data", source_field: "data" }],
    source: {
      official_url: "https://example.org", verified_at: "2026-01-02", terms_checked_on: null,
      license_name: null, license_url: null, terms_url: null, access_conditions: "Acceso público",
      redistribution_conditions: null,
    },
    provenance: { total: 21, items: [{ run_id: dataset.id, query_term: "Presupuesto",
      observed_at: dataset.last_seen_at, source_url: "https://example.org/observation" }] },
  };
  const fetcher = vi.fn(async (path: string) => Response.json(new URL(path, "http://localhost").pathname.endsWith("/provenance") ? {
    ...detail.provenance, page: 1, page_size: 20,
  } : detail));
  vi.stubGlobal("fetch", fetcher);
  render(<DatasetPage datasetId={dataset.id} />);
  expect(await screen.findByRole("heading", { name: dataset.title })).toBeDefined();
  for (const value of ["Revisión pendiente", "2026-01-02", "Cita sintética", "Atribución sintética",
    "Acceso público", "Condiciones sintéticas", "denied", "21 observaciones"]) {
    expect(screen.getByText(value)).toBeDefined();
  }
  expect(screen.getAllByText("Desconocido").length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "Licencia segura" }).getAttribute("href"))
    .toBe("https://example.org/terms");
  expect(screen.queryByRole("link", { name: "Licencia insegura" })).toBeNull();
  expect(screen.queryByRole("link", { name: "http://example.org/data" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Ver historial completo" }));
  expect(fetcher.mock.calls.some(([path]) => path.includes("/provenance"))).toBe(true);
  expect(await screen.findByRole("link", { name: "Ver ejecución" })).toBeDefined();
});

it("distinguishes a missing dataset from an unavailable service", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 404 })));
  const missing = render(<DatasetPage datasetId={dataset.id} />);
  expect(await screen.findByText("Recurso no encontrado.")).toBeDefined();
  missing.unmount();

  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
  render(<DatasetPage datasetId={dataset.id} />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
