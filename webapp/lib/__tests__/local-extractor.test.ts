/**
 * Tests for local-extractor.ts
 * Run with: cd webapp && npm test
 */

import { extractFromMessage, extractFromConversation } from "../local-extractor";

describe("extractFromMessage", () => {
  // ── Name extraction ──────────────────────────────────────────────────────

  test("extracts name from 'my name is'", () => {
    const result = extractFromMessage("My name is Alice.");
    const nameMem = result.memories.find((m) => m.content.includes("Alice"));
    expect(nameMem).toBeDefined();
    expect(nameMem?.memory_type).toBe("fact");
    expect(nameMem?.importance).toBeGreaterThan(0.8);
    expect(nameMem?.tags).toContain("name");
  });

  test("extracts name from 'call me'", () => {
    const result = extractFromMessage("Call me Bob please.");
    const nameMem = result.memories.find((m) => m.content.includes("Bob"));
    expect(nameMem).toBeDefined();
    expect(result.relationships.some((r) => r.type === "is_named" && r.target === "Bob")).toBe(true);
  });

  test("does NOT extract false positives for name", () => {
    const result = extractFromMessage("I'm feeling sorry about that.");
    const nameMem = result.memories.find((m) => m.tags?.includes("name"));
    expect(nameMem).toBeUndefined();
  });

  test("does NOT extract 'happy' as a name", () => {
    const result = extractFromMessage("I'm happy to help!");
    const entities = result.entities.filter((e) => e.name === "happy" || e.name === "Happy");
    expect(entities).toHaveLength(0);
  });

  // ── Location extraction ──────────────────────────────────────────────────

  test("extracts location from 'I live in'", () => {
    const result = extractFromMessage("I live in London.");
    const locMem = result.memories.find((m) => m.content.includes("London"));
    expect(locMem).toBeDefined();
    expect(locMem?.tags).toContain("location");
    expect(result.relationships.some((r) => r.type === "lives_in" && r.target === "London")).toBe(true);
  });

  test("extracts location from 'I'm from'", () => {
    const result = extractFromMessage("I'm from Paris originally.");
    const locMem = result.memories.find((m) => m.content.includes("Paris"));
    expect(locMem).toBeDefined();
  });

  test("extracts location from 'I moved to'", () => {
    const result = extractFromMessage("I moved to Berlin last year.");
    const locMem = result.memories.find((m) => m.content.includes("Berlin"));
    expect(locMem).toBeDefined();
  });

  // ── Occupation extraction ────────────────────────────────────────────────

  test("extracts job from 'I work at'", () => {
    const result = extractFromMessage("I work at Google.");
    const mem = result.memories.find((m) => m.content.includes("Google"));
    expect(mem).toBeDefined();
    expect(result.relationships.some((r) => r.type === "works_at" && r.target === "Google")).toBe(true);
  });

  test("extracts role from 'I'm a'", () => {
    const result = extractFromMessage("I'm a software engineer.");
    const mem = result.memories.find((m) => m.content.toLowerCase().includes("engineer"));
    expect(mem).toBeDefined();
  });

  test("does NOT extract 'feeling' as occupation", () => {
    const result = extractFromMessage("I'm feeling great today!");
    const mem = result.memories.find((m) => m.content.includes("feeling"));
    const occupation_mem = mem && mem.tags?.includes("occupation");
    expect(occupation_mem).toBeFalsy();
  });

  // ── Pet extraction ───────────────────────────────────────────────────────

  test("extracts pet from 'I have a dog named'", () => {
    const result = extractFromMessage("I have a dog named Max.");
    const mem = result.memories.find((m) => m.content.includes("Max"));
    expect(mem).toBeDefined();
    expect(mem?.tags).toContain("pet");
    expect(result.relationships.some((r) => r.type === "has_pet" && r.target === "Max")).toBe(true);
    expect(result.relationships.some((r) => r.source === "Max" && r.type === "is_a" && r.target === "dog")).toBe(true);
  });

  test("extracts cat pet", () => {
    const result = extractFromMessage("My cat's name is Whiskers.");
    const mem = result.memories.find((m) => m.content.includes("Whiskers"));
    expect(mem).toBeDefined();
  });

  // ── Preference extraction ─────────────────────────────────────────────────

  test("extracts likes", () => {
    const result = extractFromMessage("I like hiking and outdoor activities.");
    const mem = result.memories.find((m) => m.memory_type === "preference");
    expect(mem).toBeDefined();
    expect(mem?.tags).toContain("likes");
  });

  test("extracts loves", () => {
    const result = extractFromMessage("I love pizza.");
    const mem = result.memories.find((m) => m.content.includes("pizza"));
    expect(mem).toBeDefined();
    expect(mem?.memory_type).toBe("preference");
  });

  test("extracts dislikes", () => {
    const result = extractFromMessage("I hate Mondays.");
    const mem = result.memories.find((m) => m.tags?.includes("dislikes"));
    expect(mem).toBeDefined();
    expect(result.relationships.some((r) => r.type === "dislikes")).toBe(true);
  });

  test("extracts favorites", () => {
    const result = extractFromMessage("My favorite is Italian food.");
    const mem = result.memories.find((m) => m.tags?.includes("favorite"));
    expect(mem).toBeDefined();
  });

  // ── Age extraction ───────────────────────────────────────────────────────

  test("extracts age from 'I'm X years old'", () => {
    const result = extractFromMessage("I'm 28 years old.");
    const mem = result.memories.find((m) => m.content.includes("28") && m.tags?.includes("age"));
    expect(mem).toBeDefined();
    expect(mem?.importance).toBeGreaterThan(0.7);
  });

  test("rejects invalid age (0)", () => {
    const result = extractFromMessage("I'm 0 years old.");
    const mem = result.memories.find((m) => m.tags?.includes("age"));
    expect(mem).toBeUndefined();
  });

  test("rejects invalid age (200)", () => {
    const result = extractFromMessage("I'm 200 years old.");
    const mem = result.memories.find((m) => m.tags?.includes("age"));
    expect(mem).toBeUndefined();
  });

  // ── Emotion extraction ────────────────────────────────────────────────────

  test("extracts emotion from 'I'm stressed'", () => {
    const result = extractFromMessage("I'm stressed about work.");
    const mem = result.memories.find((m) => m.memory_type === "emotion");
    expect(mem).toBeDefined();
    expect(mem?.tags).toContain("stress");
  });

  test("extracts emotion from 'I feel'", () => {
    const result = extractFromMessage("I feel really tired today.");
    const mem = result.memories.find((m) => m.memory_type === "emotion");
    expect(mem).toBeDefined();
  });

  // ── Life events ───────────────────────────────────────────────────────────

  test("extracts life event from 'I just got'", () => {
    const result = extractFromMessage("I just got a new job at Tesla.");
    const mem = result.memories.find((m) => m.memory_type === "event");
    expect(mem).toBeDefined();
    expect(mem?.tags).toContain("life_event");
  });

  test("extracts graduation event", () => {
    const result = extractFromMessage("I graduated from university last month.");
    const mem = result.memories.find((m) => m.memory_type === "event");
    expect(mem).toBeDefined();
  });

  // ── Languages ─────────────────────────────────────────────────────────────

  test("extracts spoken language", () => {
    const result = extractFromMessage("I speak English and Spanish.");
    const mems = result.memories.filter((m) => m.tags?.includes("language"));
    expect(mems.length).toBeGreaterThan(0);
    const rels = result.relationships.filter((r) => r.type === "speaks");
    expect(rels.length).toBeGreaterThan(0);
  });

  // ── Studies ──────────────────────────────────────────────────────────────

  test("extracts study subject", () => {
    const result = extractFromMessage("I study computer science.");
    const mem = result.memories.find((m) => m.tags?.includes("studies"));
    expect(mem).toBeDefined();
  });

  test("extracts study subject and school", () => {
    const result = extractFromMessage("I study medicine at Oxford University.");
    const mems = result.memories.filter((m) => m.tags?.includes("education"));
    expect(mems.length).toBeGreaterThan(0);
  });

  // ── Empty / edge cases ───────────────────────────────────────────────────

  test("handles empty message", () => {
    const result = extractFromMessage("");
    expect(result.memories).toHaveLength(0);
    expect(result.entities).toHaveLength(0);
    expect(result.relationships).toHaveLength(0);
  });

  test("handles whitespace-only message", () => {
    const result = extractFromMessage("   ");
    expect(result.memories).toHaveLength(0);
  });

  test("handles message with no extractable info", () => {
    const result = extractFromMessage("Hello! How are you today?");
    // May extract nothing or very little
    expect(result).toBeDefined();
  });

  // ── Output format consistency (matches Python server) ─────────────────────

  test("output format matches Python server format", () => {
    const result = extractFromMessage("My name is Sarah and I live in Tokyo.");
    for (const mem of result.memories) {
      expect(typeof mem.content).toBe("string");
      expect(["fact", "preference", "event", "emotion", "relationship"]).toContain(mem.memory_type);
      expect(typeof mem.importance).toBe("number");
      expect(mem.importance).toBeGreaterThanOrEqual(0);
      expect(mem.importance).toBeLessThanOrEqual(1);
      expect(Array.isArray(mem.tags)).toBe(true);
    }
  });

  test("entities have correct structure", () => {
    const result = extractFromMessage("I work at Apple as a designer.");
    for (const ent of result.entities) {
      expect(typeof ent.name).toBe("string");
      expect(ent.name.length).toBeGreaterThan(0);
      expect(["person", "place", "organization", "animal", "food", "activity", "language", "concept"]).toContain(ent.type);
    }
  });

  test("relationships have correct structure", () => {
    const result = extractFromMessage("I live in New York.");
    for (const rel of result.relationships) {
      expect(typeof rel.source).toBe("string");
      expect(typeof rel.type).toBe("string");
      expect(typeof rel.target).toBe("string");
    }
  });

  // ── Deduplication ─────────────────────────────────────────────────────────

  test("does not duplicate the same memory", () => {
    // Same fact twice shouldn't produce duplicates
    const result = extractFromMessage("I live in London. I live in London.");
    const londonMems = result.memories.filter((m) => m.content.includes("London"));
    expect(londonMems.length).toBe(1);
  });
});

// ─── extractFromConversation ───────────────────────────────────────────────────

describe("extractFromConversation", () => {
  test("extracts from multiple user messages", () => {
    const messages = [
      { role: "user", content: "My name is James." },
      { role: "assistant", content: "Hi James!" },
      { role: "user", content: "I live in London." },
    ];
    const result = extractFromConversation(messages);
    const nameMem = result.memories.find((m) => m.content.includes("James"));
    const locMem = result.memories.find((m) => m.content.includes("London"));
    expect(nameMem).toBeDefined();
    expect(locMem).toBeDefined();
  });

  test("skips assistant messages", () => {
    const messages = [
      { role: "assistant", content: "My name is Nobi and I live in the cloud." },
    ];
    const result = extractFromConversation(messages);
    // Should not extract from assistant messages
    expect(result.memories).toHaveLength(0);
  });

  test("deduplicates across turns", () => {
    const messages = [
      { role: "user", content: "I live in London." },
      { role: "user", content: "I live in London." },
    ];
    const result = extractFromConversation(messages);
    const londonMems = result.memories.filter((m) => m.content.includes("London"));
    expect(londonMems.length).toBe(1);
  });
});
