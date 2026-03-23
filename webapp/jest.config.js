/** @type {import('jest').Config} */
const config = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  testMatch: ["**/__tests__/**/*.test.ts", "**/__tests__/**/*.test.tsx"],
  moduleNameMapper: {
    // Handle module aliases
    "^@/(.*)$": "<rootDir>/$1",
  },
  transform: {
    "^.+\\.(ts|tsx)$": ["ts-jest", {
      tsconfig: {
        // Relax for tests
        strict: false,
        esModuleInterop: true,
      },
    }],
  },
  // Don't transform node_modules except as needed
  transformIgnorePatterns: ["/node_modules/"],
  globals: {},
};

module.exports = config;
