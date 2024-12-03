import { bundle } from "jsr:@deno/emit";

const entryPoint = new URL("./frontend/src/script.ts", import.meta.url);

async function build() {
  try {
    const result = await bundle(entryPoint);
    await Deno.mkdir("frontend/dist", { recursive: true });

    await Deno.writeTextFile("frontend/dist/bundle.js", result.code);
    console.log("✅ Bundle created successfully");
  } catch (e) {
    console.error("❌ Bundle failed:", e);
  }
}
await build();
