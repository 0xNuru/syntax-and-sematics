import datetime
from dotenv import load_dotenv

from livekit import api
import json
from livekit import agents
from livekit.agents import AgentSession, Agent, metrics, MetricsCollectedEvent
from livekit.agents import RoomInputOptions
from livekit.plugins import (
    deepgram,
    silero,
    openai,
    elevenlabs,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import os
import asyncio
from core import settings 
from logger import setup_logging, get_logger, log_call_event
from tensorzero import AsyncTensorZeroGateway

load_dotenv()

# Initialize logging
setup_logging()
logger = get_logger(__name__)

logger.info(f"🔗 Attempting to connect to LiveKit URL: {settings.LIVEKIT_URL}")
logger.info(f"🔐 Using LiveKit API Key: {'✓' if settings.LIVEKIT_API_KEY else '✗'}")


def prewarm(proc: agents.JobProcess):
    """Prewarm function to load all heavy models before job execution"""
    logger.info("🔥 Prewarming all AI models...")
    start_time = datetime.datetime.now()

    # Load all models and store them in the process' userdata
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.03,
        min_silence_duration=0.2,
        prefix_padding_duration=0.3,
    )
    proc.userdata["stt"] = deepgram.STT(model="nova-3", language="en")
    proc.userdata["llm"] = openai.LLM(model="gpt-4.1-mini")
    proc.userdata["tts"] = elevenlabs.TTS(
        voice_id="x86DtpnPPuq2BpEiKPRy",
        model="eleven_flash_v2_5",
    )

    # Initialize TensorZero gateway and store in the process userdata
    try:
        val = settings.OPENAI_API_KEY
        if val:
            os.environ["OPENAI_API_KEY"] = val

        proc.userdata["t0_gateway"] = AsyncTensorZeroGateway.build_embedded(
            config_file="config/tensorzero.toml",
            clickhouse_url=settings.CLICKHOUSE_URL,
            async_setup=False,
        )
        logger.info("🧠 TensorZero gateway initialized in prewarm")
    except Exception as e:
        logger.warning(f"⚠️ TensorZero gateway initialization failed: {e}")

    prewarm_time = (datetime.datetime.now() - start_time).total_seconds()
    logger.info(f"🔥 All models prewarmed in {prewarm_time:.3f}s")
    proc.userdata["prewarm_time"] = prewarm_time


class Assistant(Agent):
    def __init__(self, main_prompt=None) -> None:
        prompt_path = os.path.join(os.path.dirname(__file__), "general_prompt.md")
        with open(prompt_path, "r") as f:
            instructions = f.read()
        
        if main_prompt:
            instructions = f"{instructions}\n\nMain instructions:\n{main_prompt}"
        
        super().__init__(instructions=instructions)


def get_t0_gateway(ctx: agents.JobContext):
    return ctx.proc.userdata.get("t0_gateway")


async def entrypoint(ctx: agents.JobContext):
    call_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    await ctx.connect()

    # event handlers for call lifecycle
    call_failed = False  
    call_start_time = None  
    actual_call_duration = None  

    @ctx.room.on("participant_disconnected") 
    def on_participant_disconnected(participant):
        nonlocal call_failed, call_start_time, actual_call_duration
        logger.info(f"📞 PARTICIPANT DISCONNECTED | Identity: {participant.identity} | Room: {ctx.room.name}")
        if participant.identity == sip_participant_identity and not call_failed:
            if call_start_time:
                actual_call_duration = int((datetime.datetime.now() - call_start_time).total_seconds())
                log_call_event("CALL COMPLETED", phone_number=phone_number, duration=actual_call_duration, room_name=ctx.room.name)
            else:
                log_call_event("CALL COMPLETED", phone_number=phone_number, room_name=ctx.room.name)

    dial_info = json.loads(ctx.job.metadata)
    phone_number = dial_info["phone_number"]
    prompt = dial_info.get("prompt", "you're a good outbound caller")

    sip_participant_identity = phone_number
    if phone_number is not None:
        # The outbound call will be placed after this method is executed
        try:
            log_call_event("CALL DIALING", phone_number=phone_number, room_name=ctx.room.name)
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id="ST_ckfvg2Zv5yp5",
                    sip_call_to=phone_number,
                    participant_identity=sip_participant_identity,
                    wait_until_answered=True,
                )
            )

            log_call_event("CALL ANSWERED", phone_number=phone_number, room_name=ctx.room.name)
            call_start_time = datetime.datetime.now()

        except api.TwirpError as e:
            error_details = {
                'message': e.message,
                'sip_status_code': e.metadata.get('sip_status_code'),
                'sip_status': e.metadata.get('sip_status')
            }
            logger.error(f"📞 CALL FAILED | Phone: {phone_number} | Room: {ctx.room.name}")
            logger.error(f"   ├─ Error: {error_details['message']}")
            logger.error(f"   ├─ SIP Status Code: {error_details['sip_status_code']}")
            logger.error(f"   └─ SIP Status: {error_details['sip_status']}")

            webhook_status = "failed"  
            if error_details['sip_status_code']:
                if error_details['sip_status_code'] == '486':
                    logger.warning("📞 REASON: Number is busy")
                    webhook_status = "rejected"
                elif error_details['sip_status_code'] in ['480', '404']:
                    logger.warning("📞 REASON: Number not reachable/not found")
                elif error_details['sip_status_code'] == '603':
                    logger.warning("📞 REASON: Call declined")
                    webhook_status = "rejected"  
                elif error_details['sip_status_code'] in ['408', '487']:
                    logger.warning("📞 REASON: Call timeout/cancelled")

            call_failed = True
            ctx.shutdown()
        except Exception as e:
            logger.error(f"📞 UNEXPECTED ERROR | Phone: {phone_number} | Room: {ctx.room.name} | Error: {str(e)}")
            call_failed = True
            ctx.shutdown()    

    # Use prewarmed VAD model from userdata
    logger.info(f"✅ Using prewarmed VAD model (saved {ctx.proc.userdata.get('prewarm_time', 0):.3f}s)")

    t0_gateway = get_t0_gateway(ctx)
    if t0_gateway is not None:
        try:
            t0_response = await t0_gateway.inference(
                function_name="analyze_transcript",
                input={
                    "messages": [
                        {
                            "role": "user",
                            "content": "tell me a dad joke",
                        }
                    ],
                },
            )
            logger.info(f"🔍 TensorZero response: {t0_response}")
        except Exception as e:
            logger.warning(f"⚠️ TensorZero inference failed: {e}")
    else:
        logger.warning("⚠️ TensorZero gateway is not available; skipping test inference")

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=ctx.proc.userdata["stt"],
        llm=ctx.proc.userdata["llm"],
        tts=ctx.proc.userdata["tts"],
        turn_detection=MultilingualModel(),  # This is lightweight, fine to init here
        preemptive_generation=True,
        use_tts_aligned_transcript=True,
        max_endpointing_delay=3,
        min_endpointing_delay=0.2,
    )

    # Register TensorZero shutdown callback if available
    t0_gateway = get_t0_gateway(ctx)
    if t0_gateway is not None:
        async def t0_shutdown():
            try:
                await t0_gateway.close()
            except Exception as e:
                logger.warning(f"⚠️ TensorZero gateway close error: {e}")

        ctx.add_shutdown_callback(t0_shutdown)

    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics, logger=logger)

    # Start session immediately, warmup runs in background
    await session.start(
        room=ctx.room,
        agent=Assistant(main_prompt=prompt),
        room_input_options=RoomInputOptions(
            pre_connect_audio=True,
            pre_connect_audio_timeout=10.0
        )
    )
    # This ensures the agent only speaks first in an inbound scenario.
    # When placing an outbound call, its more customary for the recipient to speak first
    if phone_number is None:
        await session.generate_reply(
            instructions="say Hello"
        )
    else:
        # Auto-greeting logic for outbound calls
        timeout_seconds = 5.0
        user_spoke_event = asyncio.Event()

        def on_user_state_changed(event):
            if event.new_state == "speaking":
                user_spoke_event.set()

        session.on("user_state_changed", on_user_state_changed)

        try:
            await asyncio.wait_for(user_spoke_event.wait(), timeout=timeout_seconds)
            logger.info("👤 User spoke first, agent will respond naturally")
        except asyncio.TimeoutError:
            logger.info("🤖 User silence detected, agent will greet first")
            await session.generate_reply(
                instructions=f"greet the caller politely by saying hello, remember, you're an outbound caller. you are the one that called them. greet them and wait for them to respond, this is your full script, if name is in the script, use it, otherwise, just say hello"
            )
        finally:
            session.off("user_state_changed", on_user_state_changed)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm, 
            # agent_name is required for explicit dispatch
            agent_name=settings.LIVEKIT_AGENT,
        )
    )
