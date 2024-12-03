const frontendPort = 3000;

Deno.serve(
  { port: frontendPort },

  async (req) => {
    const url = new URL(req.url);
    const filePath = url.pathname === "/" ? "/index.html" : url.pathname;

    try {
      const file = await Deno.readFile(`./frontend${filePath}`);
      const contentType = filePath.endsWith(".html")
        ? "text/html"
        : filePath.endsWith(".js")
        ? "application/javascript"
        : filePath.endsWith(".css")
        ? "text/css"
        : "application/octet-stream";

      return new Response(file, {
        headers: {
          "content-type": contentType,
        },
      });
    } catch (e) {
      console.error("Error occured:", e);
      return new Response(null, {
        status: 404,
      });
    }
  }
);
