import threading
import queue
import time
import traceback
import asyncio
from typing import Optional

from app.database import SessionLocal
from app.models import Resume
from app.services.resume_processor import process_resume


class InProcessJobQueue:
    """Простая внутренняя очередь задач с воркерами в потоках."""

    def __init__(self, num_workers: int = 2):
        self._queue: "queue.Queue[int]" = queue.Queue()
        self._workers: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._started = False
        self._num_workers = max(1, num_workers)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._stop_event.clear()
        for i in range(self._num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"analysis-worker-{i}", daemon=False)
            t.start()
            self._workers.append(t)

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        self._stop_event.set()
        # Добавляем токены остановки для разблокировки get()
        for _ in self._workers:
            self._queue.put_nowait(-1)
        for t in self._workers:
            t.join(timeout=timeout)

    def enqueue_resume(self, resume_id: int) -> None:
        if not self._started:
            self.start()
        self._queue.put_nowait(resume_id)

    def recover_unprocessed(self) -> int:
        """Находит в БД все резюме без анализа и ставит их в очередь.

        Возвращает количество поставленных задач.
        """
        db = SessionLocal()
        try:
            resumes = db.query(Resume).filter(Resume.processed == False).all()  # noqa: E712
            count = 0
            for r in resumes:
                self.enqueue_resume(r.id)
                count += 1
            return count
        except Exception:
            traceback.print_exc()
            return 0
        finally:
            db.close()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                resume_id = self._queue.get()
                if resume_id == -1:
                    break
                self._process_single(resume_id)
            except Exception:
                traceback.print_exc()
            finally:
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def _process_single(self, resume_id: int) -> None:
        db = SessionLocal()
        try:
            # Выполняем async функцию в отдельном цикле событий этого потока
            asyncio.run(process_resume(resume_id, db))
        except Exception:
            traceback.print_exc()
        finally:
            db.close()


# Глобальный экземпляр очереди
job_queue = InProcessJobQueue(num_workers=2)


def start_job_workers_and_recover() -> None:
    job_queue.start()
    # Небольшая задержка для стабильного старта
    time.sleep(0.1)
    job_queue.recover_unprocessed()


def enqueue_analysis(resume_id: int) -> None:
    job_queue.enqueue_resume(resume_id)


