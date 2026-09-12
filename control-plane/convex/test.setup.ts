/* Mirrors the Convex bundler, which skips file names with more than one dot. */
export const modules = import.meta.glob(["./**/*.ts", "./**/*.js", "!./**/*.*.*"]);
