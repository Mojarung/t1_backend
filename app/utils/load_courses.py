"""
Утилита для загрузки курсов из bd_course.txt в базу данных.
Парсит файл с курсами и создает записи в таблице courses.
"""

import os
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Course


class CoursesLoader:
    """
    Загрузчик курсов из текстового файла в базу данных.
    Парсит структурированный файл bd_course.txt и извлекает информацию о курсах.
    """

    def __init__(self):
        self.category_mapping = {
            "Backend Development (Python)": "Backend Development",
            "Backend Development (Java)": "Backend Development", 
            "Frontend Development (React)": "Frontend Development",
            "Frontend Development (Vue.js)": "Frontend Development",
            "Machine Learning & AI": "Machine Learning",
            "Data Science & Analytics": "Data Science",
            "DevOps & Cloud Infrastructure": "DevOps",
            "Mobile Development (Android)": "Mobile Development",
            "Mobile Development (iOS)": "Mobile Development",
            "Game Development (Unity)": "Game Development",
            "Game Development (Unreal Engine)": "Game Development",
            "Cybersecurity": "Cybersecurity",
            "QA & Software Testing": "QA Testing",
            "Blockchain Development": "Blockchain",
            "UI/UX Design": "UI/UX Design"
        }

    def parse_courses_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Парсит файл с курсами и возвращает список словарей с данными курсов.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл курсов не найден: {file_path}")

        courses = []
        current_category = None
        
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        for line in lines:
            line = line.strip()
            
            # Пропускаем пустые строки и заголовок файла
            if not line or line.startswith("База Данных Курсов"):
                continue
            
            # Определяем категорию (строки с номерами, например "1. Backend Development (Python)")
            category_match = re.match(r'^\d+\.\s+(.+)$', line)
            if category_match:
                current_category = category_match.group(1)
                continue
                
            # Если это не категория и есть текущая категория, считаем это названием курса
            if current_category and line and not line.startswith("База Данных"):
                course_data = self._create_course_data(line, current_category)
                courses.append(course_data)
        
        print(f"📚 Parsed {len(courses)} courses from {file_path}")
        return courses

    def _create_course_data(self, title: str, category: str) -> Dict[str, Any]:
        """
        Создает данные курса на основе названия и категории.
        Автоматически определяет навыки, технологии и уровень.
        """
        # Очищенное название курса
        clean_title = title.strip()
        
        # Определяем навыки и технологии на основе названия
        skills, technologies = self._extract_skills_and_technologies(clean_title, category)
        
        # Определяем уровень на основе ключевых слов
        level = self._determine_level(clean_title)
        
        # Примерная длительность на основе сложности
        duration = self._estimate_duration(clean_title, level)
        
        # Ключевые слова для поиска
        search_keywords = self._generate_search_keywords(clean_title, skills, technologies)

        return {
            "title": clean_title,
            "category": self.category_mapping.get(category, category),
            "description": f"Курс по теме: {clean_title}",
            "skills": skills,
            "technologies": technologies,
            "level": level,
            "duration_hours": duration,
            "search_keywords": search_keywords
        }

    def _extract_skills_and_technologies(self, title: str, category: str) -> tuple[List[str], List[str]]:
        """
        Извлекает навыки и технологии из названия курса.
        """
        title_lower = title.lower()
        
        # Технологии и инструменты
        tech_patterns = {
            'python': ['Python'],
            'java': ['Java'],  
            'javascript': ['JavaScript'],
            'react': ['React'],
            'vue': ['Vue.js'],
            'angular': ['Angular'],
            'django': ['Django'],
            'flask': ['Flask'],
            'fastapi': ['FastAPI'],
            'spring': ['Spring Framework'],
            'node': ['Node.js'],
            'typescript': ['TypeScript'],
            'sql': ['SQL'],
            'postgresql': ['PostgreSQL'], 
            'mysql': ['MySQL'],
            'mongodb': ['MongoDB'],
            'redis': ['Redis'],
            'docker': ['Docker'],
            'kubernetes': ['Kubernetes'],
            'aws': ['AWS'],
            'azure': ['Azure'],
            'gcp': ['Google Cloud'],
            'git': ['Git'],
            'jenkins': ['Jenkins'],
            'terraform': ['Terraform'],
            'ansible': ['Ansible'],
            'prometheus': ['Prometheus'],
            'grafana': ['Grafana'],
            'elk': ['ELK Stack'],
            'kafka': ['Apache Kafka'],
            'spark': ['Apache Spark'],
            'hadoop': ['Hadoop'],
            'tensorflow': ['TensorFlow'],
            'pytorch': ['PyTorch'],
            'keras': ['Keras'],
            'pandas': ['Pandas'],
            'numpy': ['NumPy'],
            'matplotlib': ['Matplotlib'],
            'scikit': ['Scikit-learn'],
            'opencv': ['OpenCV'],
            'unity': ['Unity'],
            'unreal': ['Unreal Engine'],
            'swift': ['Swift'],
            'kotlin': ['Kotlin'],
            'flutter': ['Flutter'],
            'xamarin': ['Xamarin'],
            'figma': ['Figma'],
            'sketch': ['Sketch']
        }
        
        # Навыки и концепции
        skill_patterns = {
            'api': ['REST API', 'API Development'],
            'microservices': ['Microservices Architecture'], 
            'testing': ['Software Testing'],
            'security': ['Cybersecurity'],
            'machine learning': ['Machine Learning'],
            'ai': ['Artificial Intelligence'],
            'data science': ['Data Science'],
            'analytics': ['Data Analytics'],
            'visualization': ['Data Visualization'],
            'devops': ['DevOps'],
            'ci/cd': ['CI/CD'],
            'agile': ['Agile Methodology'],
            'scrum': ['Scrum'],
            'ui': ['UI Design'],
            'ux': ['UX Design'],
            'mobile': ['Mobile Development'],
            'web': ['Web Development'],
            'frontend': ['Frontend Development'],
            'backend': ['Backend Development'],
            'fullstack': ['Full-Stack Development'],
            'database': ['Database Design'],
            'algorithms': ['Algorithms'],
            'data structures': ['Data Structures'],
            'architecture': ['Software Architecture'],
            'performance': ['Performance Optimization'],
            'scalability': ['System Scalability'],
            'monitoring': ['System Monitoring'],
            'logging': ['Application Logging'],
            'blockchain': ['Blockchain Technology'],
            'crypto': ['Cryptography'],
            'game': ['Game Development'],
            'graphics': ['Computer Graphics'],
            'animation': ['Animation'],
            '3d': ['3D Modeling'],
            'vr': ['Virtual Reality'],
            'ar': ['Augmented Reality']
        }
        
        technologies = []
        skills = []
        
        # Поиск технологий
        for pattern, tech_list in tech_patterns.items():
            if pattern in title_lower:
                technologies.extend(tech_list)
        
        # Поиск навыков
        for pattern, skill_list in skill_patterns.items():
            if pattern in title_lower:
                skills.extend(skill_list)
        
        # Добавляем навыки на основе категории
        category_skills = {
            'Backend Development': ['Backend Development', 'Server-side Programming'],
            'Frontend Development': ['Frontend Development', 'Client-side Programming'],
            'Machine Learning': ['Machine Learning', 'Data Analysis'],
            'Data Science': ['Data Science', 'Statistical Analysis'],
            'DevOps': ['DevOps', 'Infrastructure Management'],
            'Mobile Development': ['Mobile Development', 'App Development'],
            'Game Development': ['Game Development', 'Interactive Media'],
            'Cybersecurity': ['Information Security', 'Cyber Defense'],
            'QA Testing': ['Quality Assurance', 'Software Testing'],
            'Blockchain': ['Blockchain Development', 'Distributed Systems'],
            'UI/UX Design': ['User Interface Design', 'User Experience Design']
        }
        
        if category in category_skills:
            skills.extend(category_skills[category])
        
        # Удаляем дубликаты
        technologies = list(set(technologies))
        skills = list(set(skills))
        
        return skills, technologies

    def _determine_level(self, title: str) -> str:
        """
        Определяет уровень курса на основе ключевых слов в названии.
        """
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['основы', 'введение', 'начинающих', 'базовый']):
            return 'junior'
        elif any(word in title_lower for word in ['продвинутый', 'advanced', 'профессиональный', 'senior']):
            return 'senior'
        elif any(word in title_lower for word in ['архитектура', 'оптимизация', 'масштабирование', 'enterprise']):
            return 'senior'
        else:
            return 'middle'

    def _estimate_duration(self, title: str, level: str) -> int:
        """
        Оценивает длительность курса в часах на основе названия и уровня.
        """
        base_hours = {
            'junior': 20,
            'middle': 40,
            'senior': 60
        }
        
        duration = base_hours.get(level, 40)
        
        # Корректируем на основе ключевых слов
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['полный курс', 'complete', 'comprehensive']):
            duration += 20
        elif any(word in title_lower for word in ['краткий', 'основы', 'введение']):
            duration -= 10
        
        return max(10, duration)  # Минимум 10 часов

    def _generate_search_keywords(self, title: str, skills: List[str], technologies: List[str]) -> List[str]:
        """
        Генерирует ключевые слова для поиска курса.
        """
        keywords = []
        
        # Добавляем слова из названия
        title_words = [word.lower() for word in re.findall(r'\w+', title) if len(word) > 3]
        keywords.extend(title_words)
        
        # Добавляем навыки и технологии
        keywords.extend([skill.lower() for skill in skills])
        keywords.extend([tech.lower() for tech in technologies])
        
        # Удаляем дубликаты и возвращаем
        return list(set(keywords))

    def load_courses_to_db(self, courses_data: List[Dict[str, Any]], db: Session) -> int:
        """
        Загружает данные курсов в базу данных.
        """
        loaded_count = 0
        
        for course_data in courses_data:
            try:
                # Проверяем, существует ли курс с таким названием
                existing_course = db.query(Course).filter(
                    Course.title == course_data["title"]
                ).first()
                
                if not existing_course:
                    # Создаем новый курс
                    course = Course(**course_data)
                    db.add(course)
                    loaded_count += 1
                else:
                    # Обновляем существующий курс
                    for key, value in course_data.items():
                        setattr(existing_course, key, value)
                
            except Exception as e:
                print(f"❌ Error loading course '{course_data.get('title', 'Unknown')}': {e}")
                continue
        
        try:
            db.commit()
            print(f"✅ Successfully loaded {loaded_count} courses to database")
        except Exception as e:
            db.rollback()
            print(f"❌ Database commit failed: {e}")
            raise
        
        return loaded_count


def main():
    """
    Основная функция для загрузки курсов из файла в базу данных.
    Может использоваться как отдельный скрипт.
    """
    courses_file = "app/ai_assistant/course/bd_course.txt"
    
    if not os.path.exists(courses_file):
        print(f"❌ Файл курсов не найден: {courses_file}")
        return
    
    # Создаем загрузчик
    loader = CoursesLoader()
    
    try:
        # Парсим файл с курсами
        print("📚 Parsing courses file...")
        courses_data = loader.parse_courses_file(courses_file)
        
        # Подключаемся к базе данных
        print("🗄️ Connecting to database...")
        db = next(get_db())
        
        # Загружаем курсы в базу данных
        print("⬆️ Loading courses to database...")
        loaded_count = loader.load_courses_to_db(courses_data, db)
        
        print(f"🎉 Complete! Loaded {loaded_count} courses")
        
    except Exception as e:
        print(f"❌ Error during courses loading: {e}")
    finally:
        if 'db' in locals():
            db.close()


if __name__ == "__main__":
    main()
