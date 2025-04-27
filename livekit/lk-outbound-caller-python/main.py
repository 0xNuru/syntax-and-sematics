from dotenv import load_dotenv

from livekit import api
import json
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    openai,
    elevenlabs,
    deepgram,
    cartesia,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.plugins.elevenlabs import VoiceSettings

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="""You are an AI assistant making outbound calls for Outbound AI (website: outbound.im), a company that helps businesses automate their outbound calling process using conversational AI (just like this call).

Your name is mark, your goal is to concisely and clearly introduce Outbound AI to prospects, highlighting how they can benefit from automating their outbound calls with conversational AI. Your style should be professional yet approachable—concise, a little witty, and engaging.

Follow these instructions carefully:

Be patient and conversational: Don't say everything at once; introduce points gradually. but don't be too slow. don't make the conversation too long.
Highlight benefits naturally: Explain clearly how automating calls with AI (like this one) saves time, reduces costs, and boosts efficiency.

Maintain a polite yet lightly witty tone: Don't overdo humor, but a slight touch of warmth and personality is welcome.

Encourage engagement: Invite them to visit outbound.im for more details or to schedule a personalized demo.""")


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()

    # If a phone number was provided, then place an outbound call
    # By having a condition like this, you can use the same agent for inbound/outbound telephony as well as web/mobile/etc.
    dial_info = json.loads(ctx.job.metadata)
    phone_number = dial_info["phone_number"]

    # The participant's identity can be anything you want, but this example uses the phone number itself
    sip_participant_identity = phone_number
    if phone_number is not None:
        # The outbound call will be placed after this method is executed
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    # This ensures the participant joins the correct room
                    room_name=ctx.room.name,
                    # This is the outbound trunk ID to use (i.e. which phone number the call will come from)
                    # You can get this from LiveKit CLI with `lk sip outbound list`
                    sip_trunk_id="ST_8tLXJQjgewzt",
                    # The outbound phone number to dial and identity to use
                    sip_call_to=phone_number,
                    participant_identity=sip_participant_identity,
                    # This will wait until the call is answered before returning
                    wait_until_answered=True,
                )
            )

            print("call picked up successfully")
        except api.TwirpError as e:
            print(
                f"error creating SIP participant: {e.message}, "
                f"SIP status: {e.metadata.get('sip_status_code')} "
                f"{e.metadata.get('sip_status')}"
            )
            ctx.shutdown()

        # .. create and start your AgentSession as normal ...
        session = AgentSession(
            stt=deepgram.STT(model="nova-3", language="multi"),
            llm=openai.LLM(model="gpt-4o-mini"),
            tts=openai.TTS(
                voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
                model="tts-1-hd",  # "tts-1-hd" for higher quality
            ),
            vad=silero.VAD.load(),
            turn_detection=MultilingualModel(),
        )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
        ),
    )

    await session.generate_reply(
        instructions="Introduce yourself as an AI assistant calling on behalf of Outbound AI and express interest in discussing how their business might benefit from automating outbound calls."
    )

    # This ensure the agent only speaks first in an inbound scenario.
    # When placing an outbound call, its more customary for the recipient to speak first
    if phone_number is None:
        await session.generate_reply(
            instructions="Introduce yourself as an AI assistant from Outbound AI and ask how you can help them today."
        )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            # agent_name is required for explicit dispatch
            agent_name="my-telephony-agent",
        )
    )
