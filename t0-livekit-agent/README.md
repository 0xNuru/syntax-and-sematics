# Outbound AI Agent

<p align="center">
  <img src="path-to-your-logo.png" alt="Outbound AI Logo" width="200">
</p>

## Overview

t0-livekit-agent

## Features

## Prerequisites

- Python >=3.11.2
- OpenAI API key
- LiveKit account and credentials
- SIP trunk configuration for outbound calls
- Additional API keys based on chosen speech models (e.g., Deepgram for STT if not using OpenAI for all)

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/outbound-ai-agent.git
cd outbound-ai-agent

# Create and activate virtual environment (uv can manage this automatically too)
uv venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies (from pyproject.toml)
uv pip install .

# Download required model files (for VAD, turn detection, etc.)
python main.py download-files
```

## Configuration

1. Copy the example environment file:

   ```bash
   cp .env.example .env.local
   ```

2. Configure the following variables in `.env.local`:
   - `LIVEKIT_URL`
   - `LIVEKIT_API_KEY`
   - `LIVEKIT_API_SECRET`
   - `OPENAI_API_KEY`
   - `SIP_OUTBOUND_TRUNK_ID`
   - `DEEPGRAM_API_KEY` (if using Deepgram STT as in `main.py`)
   - Any other necessary API keys for your chosen plugins

## Usage

### Start the Agent

For development (with hot reloading):

```bash
uv run main.py dev
```

For production:

```bash
uv run main.py start
```

Your worker is now running and waiting for dispatches to make outbound calls.

### Make a Call

You can dispatch an agent to make a call by using the `lk` CLI:

```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-ai-agent \
  --metadata '{"phone_number": "+1234567890", "prompt": "Your custom prompt for this specific call"}'
```

Note: The metadata should be a valid JSON string. The `prompt` key in the metadata corresponds to the dynamic prompt your agent uses.

## Modes

The agent supports two operation modes:

### Voice Pipeline Agent

Utilizes a three-step process:

1. Speech-to-Text (STT)
2. Language Model Processing (LLM)
3. Text-to-Speech (TTS)
