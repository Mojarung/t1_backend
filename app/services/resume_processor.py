from sqlalchemy.orm import Session
from app.models import Resume

async def process_resume(resume_id: int, db: Session):
    """Маркирует резюме как обработанное без генерации мок-анализа.

    Реальную аналитику выполняют другие сервисы/очереди. Эта функция
    оставлена для совместимости с существующими вызовами.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        return

    resume.processed = True
    db.commit()
    return None
