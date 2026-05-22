import { describe, expect, it } from "vitest";
import { ApiError } from "./api";

describe("ApiError", () => {
  it("carries status, code and message", () => {
    const err = new ApiError(404, "plant_not_found", "Nicht gefunden");
    expect(err.status).toBe(404);
    expect(err.code).toBe("plant_not_found");
    expect(err.message).toBe("Nicht gefunden");
    expect(err).toBeInstanceOf(Error);
  });
});
