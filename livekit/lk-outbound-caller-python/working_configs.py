"""
Simple storage for working configurations.
"""

# ElevenLabs configurations that worked
ELEVENLABS_CONFIGS = {
    """
    tts=elevenlabs.TTS(
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.5,
            style=0.5,
            use_speaker_boost=True,
            speed=0.9,
        ),
    ), 
    """
}

# Cartesia TTS
CARTESIA_CONFIG = """
tts=cartesia.TTS()
"""

# OpenAI TTS configurations
OPENAI_TTS_CONFIGS = {
    "alloy": """
    tts=openai.TTS(
        voice="alloy",
        model="tts-1",
    )
    """,
    
    "hd": """
    tts=openai.TTS(
        voice="nova",
        model="tts-1-hd",
    )
    """
} 
