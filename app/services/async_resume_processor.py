"""
Асинхронный процессор резюме с расширенной обработкой и таймаутом
"""

import asyncio
import httpx
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import Resume, ResumeAnalysis, ProcessingStatus, ApplicationStatus, Interview
from app.services.resume_analysis_service import get_resume_analysis_service

logger = logging.getLogger(__name__)

class AsyncResumeProcessor:
    """Расширенный асинхронный процессор резюме с обработкой ошибок и таймаутом"""
    
    MAX_PROCESSING_TIME = 120  # 2 минуты максимальное время обработки
    MAX_RETRY_ATTEMPTS = 3  # Максимальное число попыток обработки
    
    def __init__(self):
        self.service = get_resume_analysis_service()
    
    async def process_resume_async(self, resume_id: int) -> None:
        """
        Расширенная асинхронная обработка резюме с таймаутом и обработкой ошибок
        """
        start_time = datetime.utcnow()
        retry_count = 0
        
        while retry_count < self.MAX_RETRY_ATTEMPTS:
            db = SessionLocal()
            try:
                # Получаем резюме из БД
                resume = db.query(Resume).filter(Resume.id == resume_id).first()
                if not resume:
                    logger.error(f"❌ Резюме {resume_id} не найдено")
                    return
                
                # Обновляем статус на "в обработке"
                resume.processing_status = ProcessingStatus.PROCESSING
                db.commit()
                
                # Проверка времени обработки
                if (datetime.utcnow() - start_time).total_seconds() > self.MAX_PROCESSING_TIME:
                    logger.warning(f"⏰ Превышено время обработки для резюме {resume_id}")
                    resume.processing_status = ProcessingStatus.FAILED
                    resume.status = ApplicationStatus.PENDING
                    resume.notes = "Требует дополнительной проверки (превышено время обработки)"
                    db.commit()
                    return
                
                # 1. Извлекаем текст через OCR
                ocr_text = await self.extract_text_with_ocr(resume.file_path)
                if not ocr_text:
                    logger.warning(f"❌ OCR не смог извлечь текст из резюме {resume_id}")
                    retry_count += 1
                    continue
                
                # 2. Получаем описание вакансии
                job_description = resume.vacancy.description if resume.vacancy else ""
                
                # 3. Анализируем резюме через нейронку
                ai_result = await self.analyze_resume_with_ai(ocr_text, job_description)
                if not ai_result:
                    logger.warning(f"❌ Нейронка не смогла проанализировать резюме {resume_id}")
                    retry_count += 1
                    continue
                
                # 4. Сохраняем результат анализа
                await self.save_analysis_result(resume_id, ai_result, db)
                
                # 5. Обновляем статусы
                resume.status = ApplicationStatus.PENDING
                resume.processed = True
                resume.processing_status = ProcessingStatus.COMPLETED
                resume.notes = ai_result.get('recommendation', 'Требует дополнительного анализа')
                db.commit()
                
                # 6. Автоназначение интервью по порогу вакансии
                try:
                    vacancy = resume.vacancy
                    if vacancy and getattr(vacancy, "auto_interview_enabled", False):
                        threshold = getattr(vacancy, "auto_interview_threshold", None)
                        # Извлекаем числовое значение процента соответствия из анализа (например, "82%")
                        match_score_raw = (ai_result.get("basic_info", {}) or {}).get("match_score") or "0"
                        try:
                            match_percent = int(str(match_score_raw).strip().replace('%', '').split()[0])
                        except Exception:
                            match_percent = 0
                        if threshold is None:
                            threshold = 0
                        if match_percent >= int(threshold):
                            # Проверяем, что интервью ещё не создано
                            existing = db.query(Interview).filter(
                                Interview.resume_id == resume.id,
                                Interview.vacancy_id == vacancy.id
                            ).first()
                            if not existing:
                                interview = Interview(
                                    vacancy_id=vacancy.id,
                                    resume_id=resume.id,
                                    scheduled_date=None,
                                )
                                db.add(interview)
                                # Обновим статус заявки
                                resume.status = ApplicationStatus.INTERVIEW_SCHEDULED
                                db.commit()
                except Exception as auto_e:
                    logger.error(f"❌ Ошибка автоназначения интервью для резюме {resume_id}: {auto_e}")

                logger.info(f"✅ Резюме {resume_id} успешно обработано")
                return
            
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке резюме {resume_id}: {e}")
                retry_count += 1
                
                # Обновляем статус на "ошибка"
                resume.processing_status = ProcessingStatus.FAILED
                resume.notes = f"Ошибка обработки: {str(e)}"
                db.commit()
            
            finally:
                db.close()
        
        # Если все попытки исчерпаны
        db = SessionLocal()
        try:
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume:
                resume.processing_status = ProcessingStatus.FAILED
                resume.status = ApplicationStatus.PENDING
                resume.notes = "Не удалось обработать резюме. Требуется ручная проверка."
                db.commit()
        except Exception as final_error:
            logger.error(f"❌ Критическая ошибка при финальной обработке {resume_id}: {final_error}")
        finally:
            db.close()
    
    async def extract_text_with_ocr(self, file_path: str) -> Optional[str]:
        """Извлечение текста через OCR с поддержкой S3 и расширенной обработкой ошибок"""
        try:
            ocr_url = os.getenv("OCR_URL", "https://mojarung-vtb-mortech-ocr-1103.twc1.net/ocr/process-file")

            # Подготовим bytes и имя файла
            filename = os.path.basename(file_path)
            file_bytes: Optional[bytes] = None
            if file_path.startswith("s3://"):
                from app.services.storage_s3 import get_s3_storage
                s3 = get_s3_storage()
                _, key = s3.parse_s3_uri(file_path)
                file_bytes = s3.get_object_bytes(key)
            else:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"file": (filename, file_bytes, "application/octet-stream")}
                response = await client.post(ocr_url, files=files)

                if response.status_code == 200:
                    result = response.json()
                    extracted_text = result.get("text", "")

                    # Дополнительная валидация текста
                    if len(extracted_text) < 50:  # Слишком короткий текст
                        logger.warning(f"⚠️ Извлечен слишком короткий текст: {len(extracted_text)} символов")
                        return None

                    return extracted_text
                else:
                    logger.error(f"❌ OCR сервис вернул ошибку: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Критическая ошибка OCR: {e}")
            return None
    
    async def analyze_resume_with_ai(self, resume_text: str, job_description: str) -> Optional[Dict[str, Any]]:
        """Анализ резюме с расширенной обработкой ошибок"""
        try:
            service = get_resume_analysis_service()
            analysis_result = await service.analyze_resume(job_description, resume_text)
            
            # Дополнительные проверки результата
            if not analysis_result or 'basic_info' not in analysis_result:
                logger.warning("❌ Некорректный результат анализа")
                return None
            
            return analysis_result
        
        except Exception as e:
            logger.error(f"❌ Ошибка анализа резюме: {e}")
            return None
    
    async def save_analysis_result(self, resume_id: int, analysis_data: Dict[str, Any], db: Session) -> None:
        """Сохранение результата с расширенной обработкой"""
        try:
            # Берем связанную вакансию для корректной позиции
            resume_obj = db.query(Resume).filter(Resume.id == resume_id).first()
            vacancy_title = resume_obj.vacancy.title if resume_obj and resume_obj.vacancy else None

            existing_analysis = db.query(ResumeAnalysis).filter(ResumeAnalysis.resume_id == resume_id).first()
            
            basic_info = analysis_data.get("basic_info", {})
            extended_info = analysis_data.get("extended_info", {})
            resume_quality = analysis_data.get("resume_quality", {})
            anti_manipulation = analysis_data.get("anti_manipulation", {})
            detailed_analysis = analysis_data.get("detailed_analysis", {})
            
            if existing_analysis:
                # Обновляем существующий анализ
                self._update_analysis(existing_analysis, basic_info, extended_info, resume_quality, anti_manipulation)
                # Новые поля
                existing_analysis.strengths = detailed_analysis.get("strengths", [])
                existing_analysis.weaknesses = detailed_analysis.get("weaknesses", [])
                existing_analysis.missing_skills = detailed_analysis.get("missing_skills", [])
                # Краткая причина (обрежем до 500 символов)
                brief = detailed_analysis.get("analysis_text") or basic_info.get("recommendation") or ""
                if brief:
                    existing_analysis.brief_reason = (brief[:500]).strip()
                # Позицию берем из вакансии, если доступна
                if vacancy_title:
                    existing_analysis.position = vacancy_title
            else:
                # Создаем новый анализ
                analysis = self._create_analysis(resume_id, basic_info, extended_info, resume_quality, anti_manipulation)
                # Новые поля
                analysis.strengths = detailed_analysis.get("strengths", [])
                analysis.weaknesses = detailed_analysis.get("weaknesses", [])
                analysis.missing_skills = detailed_analysis.get("missing_skills", [])
                brief = detailed_analysis.get("analysis_text") or basic_info.get("recommendation") or ""
                if brief:
                    analysis.brief_reason = (brief[:500]).strip()
                # Позицию берем из вакансии, если доступна
                if vacancy_title:
                    analysis.position = vacancy_title
                db.add(analysis)
            
            db.commit()
            logger.info(f"✅ Результат анализа сохранен для резюме {resume_id}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результата анализа: {e}")
            db.rollback()
            raise
    
    def _update_analysis(self, analysis, basic_info, extended_info, resume_quality, anti_manipulation):
        """Обновление существующего анализа"""
        analysis.name = basic_info.get("name")
        analysis.position = basic_info.get("position")
        analysis.experience = basic_info.get("experience")
        analysis.education = basic_info.get("education")
        analysis.match_score = basic_info.get("match_score")
        analysis.key_skills = basic_info.get("key_skills", [])
        analysis.recommendation = basic_info.get("recommendation")
        
        # Дополнительные поля
        analysis.projects = extended_info.get("projects", [])
        analysis.work_experience = extended_info.get("work_experience", [])
        analysis.technologies = extended_info.get("technologies", [])
        analysis.achievements = extended_info.get("achievements", [])
        # Новые поля
        detailed = analysis_data_safe = {
            "strengths": [],
            "weaknesses": [],
            "missing_skills": [],
            "analysis_text": "",
        }
        # Пытаемся вытащить из analysis_data detailed_analysis
        try:
            # basic_info/extended_info/resume_quality уже переданы отдельно, detailed_analysis хранится в исходных данных
            # Для обновления используем безопасный доступ из параметров функции, если они включены в них
            pass
        except Exception:
            pass
        # Мы ожидаем, что detailed_analysis был извлечен ранее при подготовке аргументов
        # поэтому добавим специальные поля в метод вызова
        
        analysis.structured = resume_quality.get("structured", False)
        analysis.effort_level = resume_quality.get("effort_level")
        
        analysis.suspicious_phrases_found = anti_manipulation.get("suspicious_phrases_found", False)
        analysis.suspicious_examples = anti_manipulation.get("examples", [])
    
    def _create_analysis(self, resume_id, basic_info, extended_info, resume_quality, anti_manipulation):
        """Создание нового анализа"""
        return ResumeAnalysis(
            resume_id=resume_id,
            name=basic_info.get("name"),
            position=basic_info.get("position"),
            experience=basic_info.get("experience"),
            education=basic_info.get("education"),
            match_score=basic_info.get("match_score"),
            key_skills=basic_info.get("key_skills", []),
            recommendation=basic_info.get("recommendation"),
            projects=extended_info.get("projects", []),
            work_experience=extended_info.get("work_experience", []),
            technologies=extended_info.get("technologies", []),
            achievements=extended_info.get("achievements", []),
            # Новые поля (будут заполнены в save_analysis_result ниже)
            strengths=[],
            weaknesses=[],
            missing_skills=[],
            brief_reason=None,
            structured=resume_quality.get("structured", False),
            effort_level=resume_quality.get("effort_level"),
            suspicious_phrases_found=anti_manipulation.get("suspicious_phrases_found", False),
            suspicious_examples=anti_manipulation.get("examples", [])
        )

# Глобальный экземпляр процессора
async_resume_processor = AsyncResumeProcessor()
