import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";

// Synthetic responses: the tests never reach a server.
function answer(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((path: string) => Promise.resolve(new Response(
    JSON.stringify(path === "/health" ? body : { items: [], total: 0 }), { status },
  ))));
}

describe("App", () => {
  it("shows that it is checking while the service has not answered", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    render(<App />);
    expect(screen.getByText("Comprobando el servicio…").textContent).toBe("Comprobando el servicio…");
  });

  it("shows that the service is available", async () => {
    answer(200, { status: "ok" });
    render(<App />);
    expect(await screen.findByText("Servicio disponible.")).toBeDefined();
  });

  it.each([
    [503, { error: { code: "unavailable" } }],
    [200, { status: "other" }],
  ])("shows a failure for status %i and body %j", async (status, body) => {
    answer(status, body);
    render(<App />);
    expect(await screen.findByText("Servicio no disponible.")).toBeDefined();
  });

  it("shows a failure when the service cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network error")));
    render(<App />);
    expect(await screen.findByText("Servicio no disponible.")).toBeDefined();
  });
});
