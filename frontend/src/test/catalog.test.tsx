import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { dataset } from "./catalogFixtures";
import { CatalogPage } from "../pages/CatalogPage";


describe("CatalogPage", () => {
  it("distinctly displays loading, empty and failed responses", async () => {
    const pending = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal("fetch", pending);
    const { unmount } = render(<CatalogPage />);
    expect(screen.getByRole("status").textContent).toBe("Cargando…");
    unmount();

    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ items: [], total: 0 })));
    const empty = render(<CatalogPage />);
    expect(await screen.findByText("Sin resultados.")).toBeDefined();
    empty.unmount();

    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
    render(<CatalogPage />);
    expect(await screen.findByRole("alert")).toBeDefined();
  });

  it("renders returned records as text and submits the original filter values", async () => {
    const fetcher = vi.fn(async (path: string) => Response.json({
      items: path.startsWith("/api/v1/datasets") ? [dataset] : [],
      total: 1, page: 1, page_size: 20,
    }));
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<CatalogPage />);
    expect((await screen.findByRole("link", { name: dataset.title })).getAttribute("href"))
      .toBe(`/datasets/${dataset.id}`);
    expect(screen.getByText(dataset.description ?? "")).toBeDefined();
    expect(container.querySelector("img")).toBeNull();
    fireEvent.change(screen.getByLabelText("Búsqueda"), { target: { value: "Ejecución %" } });
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "Hacienda" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    expect(fetcher.mock.calls.some(([path]) => {
      const url = new URL(path, "http://localhost");
      return url.searchParams.get("q") === "Ejecución %" && url.searchParams.get("category") === "Hacienda";
    })).toBe(true);
    await screen.findByRole("link", { name: dataset.title });
  });
});
