import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlantCard } from "./PlantCard";
import type { Plant } from "../types";

const base: Plant = {
  id: 1,
  name: "Monstera",
  interval_days: 7,
  image_url: null,
  last_watered_at: "2026-05-21T08:00:00",
  created_at: "2026-05-21T08:00:00",
  notes: null,
  water_amount_ml: null,
  is_thirsty: false,
  days_overdue: 0,
};

describe("PlantCard", () => {
  it("shows the name and interval", () => {
    render(<PlantCard plant={base} onClick={() => {}} />);
    expect(screen.getByText("Monstera")).toBeInTheDocument();
    expect(screen.getByText(/Water: 7 Days/)).toBeInTheDocument();
  });

  it("shows the water drop only when thirsty", () => {
    const { rerender } = render(<PlantCard plant={base} onClick={() => {}} />);
    expect(screen.queryByLabelText("thirsty")).toBeNull();
    rerender(<PlantCard plant={{ ...base, is_thirsty: true }} onClick={() => {}} />);
    expect(screen.getByLabelText("thirsty")).toBeInTheDocument();
  });

  it("fires onClick", () => {
    const onClick = vi.fn();
    render(<PlantCard plant={base} onClick={onClick} />);
    screen.getByRole("button").click();
    expect(onClick).toHaveBeenCalledOnce();
  });
});
