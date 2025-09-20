#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.gemini_multimodal_live.gemini import (
    GeminiMultimodalLiveLLMService,
    InputParams,
    GeminiVADParams,
    GeminiMultimodalModalities
)
from pipecat.services.gemini_multimodal_live.events import (
    StartSensitivity,
    EndSensitivity
)
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transcriptions.language import Language
from simli import SimliConfig
from pipecat.services.simli.video import SimliVideoService
from datetime import datetime
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
# Load environment variables
load_dotenv(override=True)

logger.add(
    "pipecat_debug.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} - {message}"
)
# We store functions so objects (e.g. SileroVADAnalyzer) don't get
# instantiated. The function will be called when the desired transport gets
# selected.
datetime_function = FunctionSchema(
    name="get_current_datetime",
    description="Get the current datetime so you can calculate time left for interview",
    properties={},
    required=[]
)
tools = ToolsSchema(standard_tools=[datetime_function])
async def get_current_datetime(params: FunctionCallParams):
    # Fetch weather data from your API
    datetime_data = {"datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    await params.result_callback(datetime_data)
# Create a tools schema with your functions


async def run_bot(webrtc_connection):
    logger.info(f"Starting bot")
    pipecat_transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        video_out_enabled=True,
        video_out_is_live=True,
        video_out_width=632,
        video_out_height=632,
        # set stop_secs to something roughly similar to the internal setting
        # of the Multimodal Live api, just to align events.
        vad_analyzer=None
    ),
    )
    # Create the Gemini Multimodal Live LLM service
    system_instruction = f"""
Ты — Александра, продвинутый HR-интервьюер.

**Задача:** Провести структурированное интервью на **русском языке**, соблюдая этические нормы (без дискриминационных вопросов). Твоя роль — оценить кандидата и подготовить отчет для HR-менеджера, **а не принимать решение о найме**.

**Входные данные:**
* **Вакансия:Frontend Developer, база знаний React, TypeScript, JavaScript, HTML/CSS, описание: Собеседование на позицию Frontend разработчика с опытом работы от 3 лет**
* **Резюме:Храмов Альберт Марсович
Мужчина, 19 лет, родился 19 января 2006
+7 (939) 3473144 — предпочитаемый способ связи
albert1yandex@gmail.com
@albert_khramov — telegram
Проживает: Москва
Гражданство: Россия, есть разрешение на работу: Россия
Не готов к переезду, не готов к командировкам
Желаемая должность и зарплата
Аналитик-программист
Специализации:
— Аналитик, ML-инженер
Занятость: частичная занятость, стажировка
График работы: сменный график, гибкий график, удаленная работа
Желательное время в пути до работы: не имеет значения
Образование
Неоконченное высшее
2028
 Национальный исследовательский технологический
университет «МИСИС», Москва
ИКН, Информатика и вычислительная техника
Повышение квалификации, курсы
2024
 Deep Learning School (DLS) 1 семестр - 01.09–31.12
CV-week (Яндекс) - 25.11–30.11
Введение в машинное обучение (Сириус Курсы) - 01.08–31.08
2023
 Основы статистики (Stepik, Anatoliy Karpov) - 01.10–15.11
Навыки
Знание языков
Навыки
Русский — Родной
Python Английский язык Аналитическое мышление Обучение и развитие
Анализ данных PostgreSQL Data Analysis Алгоритмы ML pandas Git sklearn
Data Science PyTorch CV CatBoost Seaborn Matplotlib transformers NLTK
TensorFlow Прогнозирование
Опыт работы над проектами
Pet-проект: Telegram-бот для DND (AI-ARROW Hackathon, 2024)
Описание проекта:
Разработан Telegram-бот, выполняющий роль ведущего для настольной ролевой игры
Dungeons & Dragons. Использует API ChatGPT для генерации квестов, событий и
персонажей, а также FLUX API и FreeSound для мультимедийного сопровождения.
Цель проекта:
Автоматизация работы ведущего игры, добавление интерактивного мультимедиа.
Моя роль в проекте:
• Разработка структуры JSON для хранения состояния игры
• Написание логики обработки команд
• Интеграция с API
• Подготовка пользовательской документации
• Презентация проекта
Результат:
Проект размещен на GitHub: https://github.com/c0lbarator/truedungeons
Почему я выбрал направление ML?
Первое знакомство с ML произошло в 2023 году на хакатоне «Цифровой прорыв», где я заинтересовался
анализом данных. Позже, готовясь к олимпиаде НТО БДИМО, я начал углубленно изучать ML и участвовать в
тематических мероприятиях.
Ключевые события, укрепившие интерес к ML:
•
•
•
Data Dojo (Яндекс, 2024) — разбор решений победителей ML-соревнований
Moscow AI №0 (МТС, 2024) — обсуждение AI-агентов, генерации видео, моделей типа Kandinsky
День студента (Сбер, 2025) — лекции о DeepSeek R1 и концепции Scheming у AI
Соревнования и достижения
Олимпиады:
•
 Олимпиада DANO 2023 — финалист
•
 Олимпиада НТО БДИМО (RecSys) 2024 — финалист
•
 Олимпиада Изумруд по математике 2024 — призер 3 степени
Хакатоны (https://github.com/RetRoBich921 пара проектов выложены на моём гите):
•
 AI-ARROW 2024 — победитель в специальной номинации
•
 Цифровой прорыв (Международный, CV) 2024 — 12 место
•
 Alfa Hack (бинарная классификация) 2024 — 5 место
•
 ФИЦ (Time Series) 2024 — 4 место
•
 Норникель: интеллектуальные горизонты 2024 — 5 место**
* **Время (минут):5**
Текущее время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

### **План Действий**

**1. Внутренний анализ (перед первым вопросом):**
* Выдели из вакансии 5-7 ключевых компетенций.
* Сопоставь их с резюме, определи главные темы для проверки.

**2. Проведение интервью (взаимодействие с кандидатом):**
* **Структура по времени:** Придерживайся плана: Вступление (~5%), Основные вопросы (~70%), Вопросы кандидата (~15%), Завершение (~10%).
* **Начало:** Кратко представься и озвучь план беседы.
* **Диалог:** Задавай по **одному** вопросу за раз. Если ответ неполный — задавай уточняющие вопросы.
* **Завершение:** Будь нейтрален. Поблагодари, озвучь следующие шаги (например, «Мы свяжемся с вами в течение N дней») и пожелай хорошего дня. Не давай никаких намеков на решение.

**3. Итоговый отчет (для HR-менеджера):**
* **Оценка по компетенциям:**
    * `[Компетенция]`: `[Подтверждена / Частично / Не подтверждена]` — `[Краткое обоснование]`
* **Сильные стороны:** (список 2-3)
* **Риски / Зоны роста:** (список 1-2)
* **Рекомендация:** `[Рекомендовать / Рассмотреть / Не рекомендовать]` с четкой аргументацией.
Пожалуйста, произноси числительные на русском языке, для этого можешь перевести их в письменную форму, например, 3 - "три
    """
    context = OpenAILLMContext(
    messages=[
        {
            "role": "system",
            "content": system_instruction
        }    
    ],
    tools=tools
)
    llm = GeminiMultimodalLiveLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        system_instruction=system_instruction,
        voice_id="Aoede",  # Aoede, Charon, Fenrir, Kore, Puck
        language=Language.RU_RU,
        vad=GeminiVADParams(
                start_sensitivity=StartSensitivity.HIGH,    # Быстро детектируем начало речи
                end_sensitivity=EndSensitivity.LOW,         # Даем больше времени на паузы
                prefix_padding_ms=500,                      # Увеличиваем буфер до речи
                silence_duration_ms=2000,                   # Увеличиваем время тишины до 2 сек
            ),
    )
    context_aggregator = llm.create_context_aggregator(context)
    llm.register_function(
    "get_current_datetime",
    get_current_datetime,
    cancel_on_interruption=True,  # Cancel if user interrupts (default: True)
    )
    simli = SimliVideoService(
        SimliConfig(
            apiKey=os.getenv("SIMLI_API_KEY"),
            faceId=os.getenv("SIMLI_FACE_ID"),
            handleSilence=True,
            maxSessionLength=300,
            maxIdleTime=30,
        ),
        use_turn_server=True,
        latency_interval=0
    )
    # Build the pipeline
    pipeline = Pipeline(
        [
            pipecat_transport.input(),
            context_aggregator.user(),
            llm,
            simli,
            pipecat_transport.output(),
            context_aggregator.assistant()
        ]
    )

    # Configure the pipeline task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        )
    )

    # Handle client connection event
    @pipecat_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        # Kick off the conversation.
        await task.queue_frames(
            [
                LLMMessagesAppendFrame(
                    messages=[
                        {
                            "role": "user",
                            "content": f"Поприветствовать пользователя и представиться.",
                        }
                    ]
                )
            ]
        )

    # Handle client disconnection events
    @pipecat_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        await task.cancel()

    # Run the pipeline
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)