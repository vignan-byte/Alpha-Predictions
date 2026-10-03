// @vitest-environment jsdom
import React from "react";
import { it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { AuthGate, CalendarPage } from "./ResearchPages";
vi.mock("./Chart", () => ({ EquityChart: () => null }));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("keeps protected content hidden until authentication succeeds", async () => {
  let authenticated = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, opts: any) => ({
      ok: true,
      json: async () => {
        if (path === "/api/auth/login") {
          expect(JSON.parse(opts.body).token).toBe("access");
          authenticated = true;
        }
        return { enabled: true, authenticated };
      },
    })),
  );
  render(
    <AuthGate>
      <div>Protected terminal</div>
    </AuthGate>,
  );
  await screen.findByText("Unlock workspace");
  expect(screen.queryByText("Protected terminal")).toBeNull();
  fireEvent.change(screen.getByLabelText("Access token"), {
    target: { value: "access" },
  });
  fireEvent.click(screen.getByText("Unlock workspace"));
  await screen.findByText("Protected terminal");
});
it("shows provider blocked state without synthesizing calendar events", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "blocked",
        source: "Trading Economics",
        timezone: "Asia/Kolkata",
        message: "Calendar key required",
        events: [],
      }),
    })),
  );
  render(<CalendarPage />);
  await screen.findByText("BLOCKED");
  expect(screen.getByRole("alert").textContent).toBe("Calendar key required");
  expect(screen.queryByRole("table")).toBeNull();
});
it("applies calendar filters to the backend request", async () => {
  const f = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      status: "live",
      source: "Trading Economics",
      events: [],
    }),
  }));
  vi.stubGlobal("fetch", f);
  render(<CalendarPage />);
  await screen.findByText("LIVE");
  fireEvent.change(screen.getByLabelText("Impact filter"), {
    target: { value: "high" },
  });
  await waitFor(() =>
    expect(f.mock.calls.some((c: any) => c[0].includes("impact=high"))).toBe(
      true,
    ),
  );
});
