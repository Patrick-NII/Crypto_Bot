/** App version injected at build time via Docker ARG / NEXT_PUBLIC env vars */

export const APP_VERSION =
  process.env.NEXT_PUBLIC_APP_VERSION || "0.0.0-dev";

export const APP_ENV =
  (process.env.NEXT_PUBLIC_APP_ENV as "development" | "staging" | "production") ||
  "development";

export const BUILD_SHA =
  process.env.NEXT_PUBLIC_BUILD_SHA || "local";

/** Short display string: "v0.9.0 (staging)" */
export const VERSION_DISPLAY = `v${APP_VERSION}`;

/** Full build info: "v0.9.0-staging-abc1234" */
export const VERSION_FULL = `v${APP_VERSION}-${APP_ENV}-${BUILD_SHA.slice(0, 7)}`;

/** Color for the environment badge */
export const ENV_COLOR: Record<string, string> = {
  development: "#f59e0b", // amber
  staging: "#8b5cf6",     // purple
  production: "#22c55e",  // green
};
