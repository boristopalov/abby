# Abby - AI Music Production Assistant 🎹

Abby is an assistant for music producers using Ableton Live. Abby can listen to your music, provide feedback, and suggest improvements to your production.

This project started as a fork of [https://github.com/vroomai/live](https://github.com/vroomai/live).

## Notes

Abby is under active development. There are bugs.

## Features

- **Automatic Tracking**: Abby keeps track of any changes you make, like tweaking device parameters
- **Chat Interface**: Chat with Abby about your music and ask for suggestions

## Prerequisites

- Python 3.12+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Ableton Live](https://www.ableton.com/) with [AbletonOSC](https://github.com/ideoforms/AbletonOSC) remote script installed
- [Google Gemini API key](https://ai.google.dev/)

## Setup

### 1. Clone the repository with submodules

```bash
git clone https://github.com/boristopalov/abby.git
cd abby
git submodule update --init --recursive
```

### 2. Backend setup

```bash
cd backend

# Install dependencies with uv
uv sync

# Create .env file with your API keys
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env

# Optional: Add TTS support
# echo "FISH_API_KEY=your_fish_api_key" >> .env
# echo "FISH_AUDIO_REFERENCE_ID=your_reference_id" >> .env
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

## Running

Start both servers (in separate terminals):

```bash
# Terminal 1: Backend
cd backend
uv run fastapi dev app/main.py
```

```bash
# Terminal 2: Frontend
cd frontend
npm run dev
```

The UI will be accessible at http://localhost:5173

The API documentation is available at http://localhost:8000/docs

## TODO

- [] Listen to raw audio from tracks and provide feedback
- [] Add more direct DAW integrations

## Contributing

Contributions are welcome. Please feel free to submit a Pull Request.

## License

MIT License
