import { Router } from "https://deno.land/x/oak/mod.ts";
import {
  GENRE_SYSTEM_PROMPTS,
  setSystemGenre,
  systemGenre,
} from "./prompts.ts";
import { oscHandler } from "./connect.ts";

const router = new Router();

router.get("/api/genres", (ctx) => {
  const genres = Object.keys(GENRE_SYSTEM_PROMPTS);
  ctx.response.body = {
    genres,
    defaultGenre: systemGenre,
  };
});

router.post("/api/genre", async (ctx) => {
  const body = await ctx.request.body.json();
  const { genre } = body;

  if (!genre || typeof genre !== "string") {
    ctx.response.status = 400;
    ctx.response.body = { error: "Invalid genre provided" };
  }

  // Update the SYSTEM_GENRE variable
  setSystemGenre(genre);

  ctx.response.body = {
    success: true,
    message: "Genre updated successfully",
    currentGenre: systemGenre,
  };
});

router.get("/api/parameter-changes", (ctx) => {
  const changes = oscHandler.getRecentParameterChanges();
  ctx.response.body = { changes };
});

export default router;
