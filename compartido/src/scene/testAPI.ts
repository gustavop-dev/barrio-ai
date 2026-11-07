// Minimal structural contract accepted by both Jest and Vitest, without a runner dependency.
export interface Assertions {
  not: Omit<Assertions, 'not'>;
  toBe(value: unknown): void;
  toEqual(value: unknown): void;
  toBeNull(): void;
  toBeDefined(): void;
  toBeGreaterThan(value: number): void;
  toBeLessThan(value: number): void;
  toHaveLength(value: number): void;
  toContain(value: unknown): void;
}
export interface TestAPI {
  describe(name: string, run: () => void): unknown;
  it(name: string, run: () => void): unknown;
  expect(value: unknown, message?: string): Assertions;
}
