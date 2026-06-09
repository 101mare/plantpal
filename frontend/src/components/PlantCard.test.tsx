import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlantCard } from "./PlantCard";
import { I18nProvider } from "../i18n";
import type { Plant } from "../types";

const base: Plant = {
  id: 1,
  name: "Monstera",
  interval_days: 7,
  image_url: null,
  last_watered_at: new Date().toISOString(), // watered today -> healthy status
  created_at: "2026-05-21T08:00:00",
  notes: null,
  water_amount_ml: null,
  location_room: null,
  is_thirsty: false,
  days_overdue: 0,
};

function renderCard(plant: Plant, onClick: () => void = () => {}) {
  return render(
    <I18nProvider>
      <PlantCard plant={plant} onClick={onClick} />
    </I18nProvider>,
  );
}

describe("PlantCard", () => {
  it("shows the name (interval moved to detail sheet)", () => {
    renderCard(base);
    expect(screen.getByText("Monstera")).toBeInTheDocument();
    expect(screen.queryByText(/7/)).toBeNull();
  });

  it("shows the overdue-day badge when thirsty", () => {
    renderCard({ ...base, is_thirsty: true, days_overdue: 5 });
    expect(screen.getByText(/5d/)).toBeInTheDocument();
  });

  it("shows no overdue badge when healthy", () => {
    renderCard(base);
    expect(screen.queryByText(/^\d+d$/)).toBeNull();
  });

  it("fires onClick", () => {
    const onClick = vi.fn();
    renderCard(base, onClick);
    screen.getByRole("button").click();
    expect(onClick).toHaveBeenCalledOnce();
  });
});
