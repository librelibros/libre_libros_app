import { build } from "esbuild";

await build({
  entryPoints: ["frontend/editor/index.js"],
  outfile: "app/static/js/editor-rich.js",
  bundle: true,
  format: "iife",
  target: ["es2020"],
  sourcemap: false,
  minify: false,
});
