/**
 * Project Nobi — Browser-Side Memory Extractor
 * =============================================
 * Regex-based memory extraction running entirely in the user's browser.
 * No data leaves the device during extraction. Matches the output format
 * of the server-side extract_memories_from_message() in nobi/memory/store.py.
 *
 * This is a port of the Python regex extractor with TypeScript idioms.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export type MemoryType = "fact" | "preference" | "event" | "emotion" | "relationship";

export interface ExtractedMemory {
  content: string;
  memory_type: MemoryType;
  importance: number;
  tags: string[];
}

export interface ExtractedEntity {
  name: string;
  type: "person" | "place" | "organization" | "animal" | "food" | "activity" | "language" | "concept";
}

export interface ExtractedRelationship {
  source: string;
  type: string;
  target: string;
}

export interface ExtractionResult {
  memories: ExtractedMemory[];
  entities: ExtractedEntity[];
  relationships: ExtractedRelationship[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const FAMILY_RELATIONS: Record<string, string> = {
  mother: "mother_of",
  mom: "mother_of",
  mum: "mother_of",
  father: "father_of",
  dad: "father_of",
  sister: "sister_of",
  brother: "brother_of",
  daughter: "child_of",
  son: "child_of",
  wife: "married_to",
  husband: "married_to",
  partner: "partner_of",
  girlfriend: "partner_of",
  boyfriend: "partner_of",
  grandmother: "related_to",
  grandfather: "related_to",
  grandma: "related_to",
  grandpa: "related_to",
  aunt: "related_to",
  uncle: "related_to",
  cousin: "related_to",
  friend: "friend_of",
  "best friend": "friend_of",
};

const SKIP_NAMES = new Set([
  "sorry", "fine", "good", "okay", "well", "sure", "happy",
  "feeling", "stressed", "tired", "excited", "worried", "great", "bad",
]);

const SKIP_ROLES = new Set([
  "feeling", "doing", "going", "trying", "looking", "bit", "little",
  "very", "so", "really", "just", "not", "also", "still", "currently",
  "vegetarian", "okay", "fine", "good",
]);

const ANIMAL_WORDS = new Set([
  "dog", "cat", "bird", "fish", "hamster", "rabbit", "turtle", "snake",
  "parrot", "guinea pig", "puppy", "kitten", "golden retriever", "labrador",
  "poodle", "bunny",
]);

// Life event signals (lowercase)
const LIFE_EVENT_SIGNALS = [
  "i just got ", "i recently ", "i'm starting ", "i am starting ",
  "i moved to ", "i graduated ", "i got married",
  "i had a baby", "i got a new job", "i'm pregnant", "i am pregnant",
];

// Emotion signals with metadata
const EMOTION_SIGNALS: Array<[string, number, string[]]> = [
  ["i'm feeling ", 0.5, ["mood"]],
  ["i am feeling ", 0.5, ["mood"]],
  ["i feel ", 0.5, ["mood"]],
  ["i'm stressed", 0.6, ["stress", "mood"]],
  ["i am stressed", 0.6, ["stress", "mood"]],
  ["i'm happy", 0.5, ["happiness", "mood"]],
  ["i am happy", 0.5, ["happiness", "mood"]],
  ["i'm worried", 0.6, ["worry", "mood"]],
  ["i am worried", 0.6, ["worry", "mood"]],
  ["i'm excited", 0.5, ["excitement", "mood"]],
  ["i am excited", 0.5, ["excitement", "mood"]],
  ["i'm sad", 0.6, ["sadness", "mood"]],
  ["i am sad", 0.6, ["sadness", "mood"]],
  ["i'm anxious", 0.6, ["anxiety", "mood"]],
  ["i am anxious", 0.6, ["anxiety", "mood"]],
];

// ─── Helper: guess entity type ────────────────────────────────────────────────

function guessEntityType(text: string): ExtractedEntity["type"] {
  const t = text.toLowerCase();
  const foods = ["pizza", "sushi", "coffee", "tea", "wine", "beer", "chocolate", "pasta"];
  const activities = ["running", "swimming", "cooking", "reading", "gaming", "hiking", "yoga", "music"];
  const languages = ["english", "spanish", "french", "german", "chinese", "japanese", "arabic", "portuguese"];

  if (foods.some((f) => t.includes(f))) return "food";
  if (activities.some((a) => t.includes(a))) return "activity";
  if (languages.some((l) => t.includes(l))) return "language";
  if (ANIMAL_WORDS.has(t)) return "animal";
  return "concept";
}

// ─── Main extractor ──────────────────────────────────────────────────────────

/**
 * Extract memories, entities, and relationships from a user message.
 * Runs entirely in the browser. Matches server-side Python output format.
 *
 * @param message - The user's message text
 * @returns ExtractionResult with memories, entities, relationships
 */
export function extractFromMessage(message: string): ExtractionResult {
  if (!message || !message.trim()) {
    return { memories: [], entities: [], relationships: [] };
  }

  const memories: ExtractedMemory[] = [];
  const entities: ExtractedEntity[] = [];
  const relationships: ExtractedRelationship[] = [];
  const msgLower = message.toLowerCase();

  // Track what we've already extracted to avoid duplicates
  const seenMemories = new Set<string>();

  function addMemory(mem: ExtractedMemory) {
    const key = mem.content.toLowerCase().trim();
    if (!seenMemories.has(key)) {
      seenMemories.add(key);
      memories.push(mem);
    }
  }

  function addEntity(name: string, type: ExtractedEntity["type"]) {
    if (!entities.some((e) => e.name.toLowerCase() === name.toLowerCase())) {
      entities.push({ name, type });
    }
  }

  function addRelationship(source: string, type: string, target: string) {
    const key = `${source}::${type}::${target}`.toLowerCase();
    if (!relationships.some((r) =>
      `${r.source}::${r.type}::${r.target}`.toLowerCase() === key
    )) {
      relationships.push({ source, type, target });
    }
  }

  // ── Pattern 1: Name extraction ───────────────────────────────────────────
  const namePatterns = [
    /(?:my name is|call me)\s+(\w{2,30})\b/i,
    /(?:I'm|i am)\s+([A-Z]\w+)\b/,
  ];
  for (const pattern of namePatterns) {
    const match = message.match(pattern);
    if (match) {
      const name = match[1].trim();
      if (!SKIP_NAMES.has(name.toLowerCase()) && name.length > 1 && name.length < 30) {
        addMemory({
          content: `User's name is ${name}`,
          memory_type: "fact",
          importance: 0.9,
          tags: ["name", "identity"],
        });
        addEntity("user", "person");
        addEntity(name, "person");
        addRelationship("user", "is_named", name);
        break;
      }
    }
  }

  // ── Pattern 1b: "My [relation] is/called [Name]" ─────────────────────────
  const familyPatterns = [
    /[Mm]y\s+([\w\s]+?)\s+(?:is\s+)?(?:called\s+|named\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g,
    /[Mm]y\s+([\w\s]+?)'s\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g,
  ];
  for (const pattern of familyPatterns) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(message)) !== null) {
      const relationWord = match[1].trim().toLowerCase();
      const name = match[2].trim();
      const relType = FAMILY_RELATIONS[relationWord];
      if (relType && name.length > 1 && !SKIP_NAMES.has(name.toLowerCase())) {
        addMemory({
          content: `User's ${relationWord} is ${name}`,
          memory_type: "fact",
          importance: 0.85,
          tags: ["family", "relationship"],
        });
        addEntity("user", "person");
        addEntity(name, "person");
        addRelationship("user", relType, name);
      }
    }
  }

  // ── Pattern 2: Location ───────────────────────────────────────────────────
  const locationPatterns: Array<[RegExp, string]> = [
    [/(?:I live in|I'm from|I moved to|I'm based in|I am based in|I am from|I come from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g, "lives_in"],
    [/(?:I am in|I'm in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g, "lives_in"],
  ];
  for (const [pattern, relType] of locationPatterns) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(message)) !== null) {
      const location = match[1].trim();
      if (location.length > 1) {
        addMemory({
          content: `User is from/lives in ${location}`,
          memory_type: "fact",
          importance: 0.8,
          tags: ["location"],
        });
        addEntity("user", "person");
        addEntity(location, "place");
        addRelationship("user", relType, location);
      }
    }
  }

  // ── Pattern 3: Occupation ─────────────────────────────────────────────────
  const workAtMatch = message.match(/I\s+work\s+at\s+([A-Z][\w\s&]+?)(?:\.|,|!|\?|$)/);
  if (workAtMatch) {
    const org = workAtMatch[1].trim();
    if (org.length > 1 && org.length < 60) {
      addMemory({
        content: `User works at: ${org}`,
        memory_type: "fact",
        importance: 0.8,
        tags: ["career", "occupation"],
      });
      addEntity("user", "person");
      addEntity(org, "organization");
      addRelationship("user", "works_at", org);
    }
  }

  const workPatterns = [
    /I(?:'m| am) (?:a|an)\s+([\w\s]{3,30}?)(?:\.|,|!|\?|$| at| in| for)/i,
    /I work (?:as|in|for)\s+(.+?)(?:\.|,|!|\?|$)/i,
  ];
  for (const pattern of workPatterns) {
    const match = message.match(pattern);
    if (match) {
      const role = match[1].trim();
      const firstWord = role.split(/\s+/)[0].toLowerCase();
      if (!SKIP_ROLES.has(firstWord) && role.length > 2 && role.length < 40) {
        addMemory({
          content: `User works as/is: ${role}`,
          memory_type: "fact",
          importance: 0.8,
          tags: ["career", "occupation"],
        });
        addEntity("user", "person");
        addEntity(role, "concept");
        addRelationship("user", "works_as", role);
        break;
      }
    }
  }

  // ── Pattern 4: Pets ───────────────────────────────────────────────────────
  const petPatterns = [
    /I\s+have\s+(?:a\s+)?(dog|cat|bird|fish|hamster|rabbit|turtle|snake|parrot|guinea pig)\s+(?:named|called)\s+([A-Z][a-z]+)/i,
    /[Mm]y\s+(dog|cat|bird|fish|hamster|rabbit|turtle|snake|parrot|guinea pig)(?:'s name is|,?\s+)\s*([A-Z][a-z]+)/i,
  ];
  for (const pattern of petPatterns) {
    const match = message.match(pattern);
    if (match) {
      const animalType = match[1].trim().toLowerCase();
      const petName = match[2].trim();
      if (petName.length > 1) {
        addMemory({
          content: `User has a ${animalType} named ${petName}`,
          memory_type: "fact",
          importance: 0.8,
          tags: ["pet", "animal"],
        });
        addEntity("user", "person");
        addEntity(petName, "animal");
        addEntity(animalType, "animal");
        addRelationship("user", "has_pet", petName);
        addRelationship(petName, "is_a", animalType);
      }
    }
  }

  // ── Pattern 5: Preferences (likes/dislikes) ───────────────────────────────
  const prefPatterns: Array<[RegExp, string, string[]]> = [
    [/I\s+(?:really\s+)?(?:love)\s+(.+?)(?:\.|,|!|\?|$)/i, "loves", ["love"]],
    [/I\s+(?:really\s+)?(?:like|enjoy|adore)\s+(.+?)(?:\.|,|!|\?|$)/i, "likes", ["likes"]],
    [/I\s+(?:hate|dislike|can't stand)\s+(.+?)(?:\.|,|!|\?|$)/i, "dislikes", ["dislikes"]],
    [/I\s+prefer\s+(.+?)(?:\.|,|!|\?|$)/i, "preference", ["preference"]],
    [/my\s+favorite(?:\s+is)?\s+(.+?)(?:\.|,|!|\?|$)/i, "favorite", ["favorite"]],
  ];
  for (const [pattern, relType, tags] of prefPatterns) {
    const match = message.match(pattern);
    if (match) {
      const thing = match[1].trim();
      if (thing.length > 2 && thing.length < 100) {
        const label = relType === "loves" ? "loves" :
                      relType === "likes" ? "likes" :
                      relType === "dislikes" ? "dislikes" :
                      relType === "favorite" ? "favorite" : "prefers";
        addMemory({
          content: `User ${label}: ${thing}`,
          memory_type: "preference",
          importance: 0.7,
          tags,
        });
        addEntity("user", "person");
        addEntity(thing, guessEntityType(thing));
        addRelationship("user", relType, thing);
      }
    }
  }

  // ── Pattern 6: Studies ────────────────────────────────────────────────────
  const studiesMatch = message.match(
    /I\s+(?:study|am studying|am studying)\s+(.+?)(?:\s+at\s+(.+?))?(?:\.|,|!|\?|$)/i
  );
  if (studiesMatch) {
    const subject = studiesMatch[1].trim();
    const school = studiesMatch[2]?.trim();
    if (subject && subject.length > 1 && subject.length < 60) {
      addMemory({
        content: `User studies: ${subject}`,
        memory_type: "fact",
        importance: 0.75,
        tags: ["education", "studies"],
      });
      addEntity("user", "person");
      addEntity(subject, "concept");
      addRelationship("user", "studies", subject);
    }
    if (school && school.length > 1 && school.length < 60) {
      addMemory({
        content: `User studies at: ${school}`,
        memory_type: "fact",
        importance: 0.75,
        tags: ["education", "school"],
      });
      addEntity(school, "organization");
      addRelationship("user", "studies_at", school);
    }
  }

  // ── Pattern 7: Language ───────────────────────────────────────────────────
  const speaksMatch = message.match(/I\s+speak\s+([\w\s,]+?)(?:\.|!|\?|$)/i);
  if (speaksMatch) {
    const langsRaw = speaksMatch[1].trim();
    const langs = langsRaw.split(/[,\s]+and\s+|,\s*/i).map((l) => l.trim()).filter((l) => l.length > 1);
    for (const lang of langs.slice(0, 5)) {
      if (lang.length > 1 && lang.length < 30) {
        addMemory({
          content: `User speaks: ${lang}`,
          memory_type: "fact",
          importance: 0.7,
          tags: ["language"],
        });
        addEntity("user", "person");
        addEntity(lang, "language");
        addRelationship("user", "speaks", lang);
      }
    }
  }

  // ── Pattern 8: Age ────────────────────────────────────────────────────────
  const agePatterns = [
    /I(?:'m| am)\s+(\d{1,3})\s+years?\s+old/i,
    /my age is\s+(\d{1,3})/i,
    /I(?:'m| am)\s+(\d{1,3})\b/i,
  ];
  for (const pattern of agePatterns) {
    const match = message.match(pattern);
    if (match) {
      const age = parseInt(match[1], 10);
      if (age >= 1 && age <= 120) {
        addMemory({
          content: `User is ${age} years old`,
          memory_type: "fact",
          importance: 0.8,
          tags: ["age", "personal"],
        });
        addEntity("user", "person");
        break;
      }
    }
  }

  // ── Pattern 9: Life events ────────────────────────────────────────────────
  for (const signal of LIFE_EVENT_SIGNALS) {
    if (msgLower.includes(signal)) {
      const idx = msgLower.indexOf(signal);
      const snippet = message.slice(idx, idx + 120).split(".")[0].trim();
      if (snippet.length > signal.length + 2) {
        addMemory({
          content: snippet,
          memory_type: "event",
          importance: 0.8,
          tags: ["life_event"],
        });
      }
    }
  }

  // ── Pattern 10: Emotions ─────────────────────────────────────────────────
  for (const [signal, importance, tags] of EMOTION_SIGNALS) {
    if (msgLower.includes(signal)) {
      const idx = msgLower.indexOf(signal);
      const snippet = message.slice(idx, idx + 80).split(".")[0].trim();
      if (snippet.length > signal.length) {
        addMemory({
          content: snippet,
          memory_type: "emotion",
          importance,
          tags,
        });
      }
    }
  }

  return { memories, entities, relationships };
}

/**
 * Extract memories from multiple messages (conversation history).
 * Deduplicates across turns.
 */
export function extractFromConversation(
  messages: Array<{ role: string; content: string }>
): ExtractionResult {
  const combined: ExtractionResult = { memories: [], entities: [], relationships: [] };
  const seenMemories = new Set<string>();
  const seenEntities = new Set<string>();
  const seenRels = new Set<string>();

  for (const msg of messages) {
    if (msg.role !== "user") continue;
    const result = extractFromMessage(msg.content);

    for (const mem of result.memories) {
      const key = mem.content.toLowerCase().trim();
      if (!seenMemories.has(key)) {
        seenMemories.add(key);
        combined.memories.push(mem);
      }
    }

    for (const ent of result.entities) {
      const key = `${ent.name}::${ent.type}`.toLowerCase();
      if (!seenEntities.has(key)) {
        seenEntities.add(key);
        combined.entities.push(ent);
      }
    }

    for (const rel of result.relationships) {
      const key = `${rel.source}::${rel.type}::${rel.target}`.toLowerCase();
      if (!seenRels.has(key)) {
        seenRels.add(key);
        combined.relationships.push(rel);
      }
    }
  }

  return combined;
}
