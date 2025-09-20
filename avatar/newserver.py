import os
import asyncio
from dotenv import load_dotenv
from loguru import logger
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams
from pipecat.transcriptions.language import Language
from simli import SimliConfig
from pipecat.services.simli.video import SimliVideoService

load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные для управления ботами
active_sessions = {}

async def create_bot_session(session_id: str, request_data: dict = None):
    """Создает новую сессию бота"""
    
    system_instruction = """
    Ты умный HR специалист в IT сфере. Ты помогаешь компаниям в поиске и найме квалифицированных специалистов. Ты умеешь анализировать резюме и предлагать лучшие варианты для найма.
    """

    # Создаем транспорт
    transport_params = TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        video_out_enabled=True,
        video_out_is_live=True,
        video_out_width=512,
        video_out_height=512,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.5)),
    )
    
    transport = SmallWebRTCTransport(params=transport_params)

    llm = GeminiMultimodalLiveLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        system_instruction=system_instruction,
        voice_id="Aoede",
        language=Language.RU_RU
    )
    
    simli = SimliVideoService(
        SimliConfig(
            apiKey=os.getenv("SIMLI_API_KEY"),
            faceId=os.getenv("SIMLI_FACE_ID"),
            handleSilence=True,
            maxSessionLength=180,
            maxIdleTime=30,
        ),
        use_turn_server=True,
        latency_interval=0
    )

    pipeline = Pipeline([
        transport.input(),
        llm,
        simli,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Клиент подключился к сессии {session_id}")
        await task.queue_frames([
            LLMMessagesAppendFrame(
                messages=[{
                    "role": "user",
                    "content": "Поприветствовать пользователя и представиться.",
                }]
            )
        ])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Клиент отключился от сессии {session_id}")
        if session_id in active_sessions:
            del active_sessions[session_id]
        await task.cancel()

    # Сохраняем сессию
    active_sessions[session_id] = {
        'transport': transport,
        'task': task,
        'runner': PipelineRunner()
    }
    
    # Запускаем задачу в фоне
    asyncio.create_task(active_sessions[session_id]['runner'].run(task))
    
    return transport

@app.post("/connect")
async def connect_endpoint(request: Request):
    """Endpoint для SmallWebRTC подключения"""
    try:
        body = await request.json()
        session_id = f"session_{len(active_sessions) + 1}"
        
        # Создаем новую сессию бота
        transport = await create_bot_session(session_id, body)
        
        # SmallWebRTC ожидает WebRTC offer/answer обработку
        # Это будет обработано автоматически транспортом
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": "WebRTC session created"
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания сессии: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Проверка состояния сервера"""
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
