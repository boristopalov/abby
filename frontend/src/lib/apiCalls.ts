// Client-side code
const base_uri = `http://localhost:8080`;
type GenreResponse = {
  defaultGenre: string;
  genres: string[];
};
export async function fetchGenres(): Promise<GenreResponse> {
  const response = await fetch(`${base_uri}/api/genres`);
  const data = await response.json();
  return data; // { genres: string[], defaultGenre: string }
}

// Add this function to handle genre selection
export async function setGenre(genre: string) {
  try {
    const response = await fetch(`${base_uri}/api/genre`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ genre }),
    });

    if (!response.ok) {
      throw new Error("Failed to set genre");
    }

    // You might want to add some visual feedback here
    console.log(`Genre ${genre} selected successfully`);
  } catch (error) {
    console.error("Error setting genre:", error);
  }
}
