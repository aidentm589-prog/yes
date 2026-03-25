import { browserActionSchema, createRunSchema } from "@/lib/schemas";

describe("schemas", () => {
  it("accepts a valid navigate action", () => {
    const action = browserActionSchema.parse({
      kind: "navigate",
      url: "https://example.com",
    });

    expect(action.kind).toBe("navigate");
  });

  it("rejects an invalid run request", () => {
    expect(() =>
      createRunSchema.parse({
        prompt: "too short",
      }),
    ).toThrow();
  });
});
