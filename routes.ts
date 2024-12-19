import { Router } from "https://deno.land/x/oak/mod.ts";
import { dbService } from "./db.ts";
import { generateRandomGenre } from "./genre_generator.ts";
import { context } from "./context.ts";

const router = new Router();

router.get("/genres", (ctx) => {
  try {
    const genres = dbService.getGenres();
    const defaultGenre = dbService.getDefaultGenre();
    const current = context.currentGenre.genre;

    ctx.response.body = {
      genres: genres.map((g) => g.name),
      defaultGenre: defaultGenre?.name || null,
      currentGenre: current,
    };
  } catch (error) {
    console.error("Error fetching genres:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch genres" };
  }
});

router.post("/genres/set-current", async (ctx) => {
  try {
    const { genre } = await ctx.request.body.json();

    if (!genre) {
      ctx.response.status = 400;
      ctx.response.body = { error: "Genre name is required" };
      return;
    }

    const existingGenre = dbService.getGenreByName(genre);
    if (!existingGenre) {
      ctx.response.status = 404;
      ctx.response.body = { error: "Genre not found" };
      return;
    }

    context.setCurrentGenre(genre);
    ctx.response.body = { success: true, genre };
  } catch (error) {
    console.error("Error setting current genre:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to set current genre" };
  }
});

router.post("/genres/set-default", async (ctx) => {
  try {
    const { genre } = await ctx.request.body.json();

    if (!genre) {
      ctx.response.status = 400;
      ctx.response.body = { error: "Genre name is required" };
      return;
    }

    const existingGenre = dbService.getGenreByName(genre);
    if (!existingGenre) {
      ctx.response.status = 404;
      ctx.response.body = { error: "Genre not found" };
      return;
    }

    dbService.setDefaultGenre(genre);
    ctx.response.body = { success: true, genre };
  } catch (error) {
    console.error("Error setting default genre:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to set default genre" };
  }
});

router.get("/parameter-changes", (ctx) => {
  try {
    const changes = dbService.getRecentParameterChanges();
    if (!changes.length) {
      ctx.response.body = {
        changes: [],
        message: "No recent parameter changes found",
      };
      return;
    }
    ctx.response.body = { changes };
  } catch (error) {
    console.error("Error fetching parameter changes:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch parameter changes" };
  }
});

router.get("/random-genre", async (ctx) => {
  try {
    const { genreName, prompt } = await generateRandomGenre();
    if (!genreName) {
      ctx.response.status = 500;
      ctx.response.body = { error: "Failed to generate genre name" };
      return;
    }
    dbService.addGenre(genreName, prompt);

    ctx.response.body = {
      success: true,
      genre: genreName,
      systemPrompt: prompt,
    };
  } catch (error) {
    console.error("Error generating random genre:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to generate random genre" };
  }
});

router.get("/session/:id/messages", (ctx) => {
  try {
    const sessionId = ctx.params.id;
    console.log("SESSION ID:", sessionId);
    const session = dbService.getSession(sessionId);

    if (!session) {
      ctx.response.status = 404;
      ctx.response.body = { error: "Session not found" };
      return;
    }

    ctx.response.body = { messages: session.messages };
  } catch (error) {
    console.error("Error fetching session messages:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch session messages" };
  }
});

export default router;
