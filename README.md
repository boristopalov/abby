# Abby - AI Music Production Assistant 🎹

Abby is an assistant for music producers using Ableton Live.

This project started as a fork of [https://github.com/vroomai/live](https://github.com/vroomai/live).

## Features

- **Chat Interface**: Chat with Abby about your music and ask for suggestions
- **Voice Mode**:

## Dev Prerequisites

- Python 3.12+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Ableton Live](https://www.ableton.com/)
- Anthropic API key

## Dev Setup

### 1. Clone the repository

```bash
git clone https://github.com/boristopalov/abby.git
```

### 2. Backend setup

```bash
cd backend

# Install dependencies with uv
uv sync

# Create .env file with your API keys
export "ANTHROPIC_API_KEY=your_api_key_here" >> ~/.zshrc

# Optional: Add TTS support
# echo "FISH_API_KEY=your_fish_api_key" >> ~/.zshrc
# echo "FISH_AUDIO_REFERENCE_ID=your_reference_id" >> ~/.zshrc
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

## License

MIT License
