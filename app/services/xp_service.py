from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import User
import json

class XPService:
    """Сервис для расчета и управления XP пользователей на основе заполненности профиля"""
    
    # Конфигурация XP за различные поля профиля
    XP_CONFIG = {
        # Базовая информация
        "first_name": 10,
        "last_name": 10,
        "phone": 15,
        "birth_date": 10,
        "location": 20,
        "about": 30,
        
        # Профессиональная информация
        "desired_salary": 15,
        "ready_to_relocate": 10,
        "employment_type": 15,
        
        # Навыки и компетенции
        "programming_languages": {
            "base": 20,
            "per_item": 5,
            "max_items": 10
        },
        "foreign_languages": {
            "base": 15,
            "per_item": 10,
            "max_items": 5
        },
        "other_competencies": {
            "base": 15,
            "per_item": 3,
            "max_items": 15
        },
        
        # Опыт и образование
        "work_experience": {
            "base": 50,
            "per_item": 20,
            "max_items": 5
        },
        "education": {
            "base": 30,
            "per_item": 15,
            "max_items": 3
        }
    }
    
    # Бонусы за полноту профиля
    COMPLETION_BONUSES = {
        50: 50,   # Бонус за 50% заполненности
        75: 100,  # Бонус за 75% заполненности  
        100: 200  # Бонус за 100% заполненности
    }
    
    @classmethod
    def calculate_user_xp(cls, user: User) -> Dict[str, Any]:
        """
        Рассчитывает XP пользователя на основе заполненности профиля
        
        Returns:
            Dict с информацией о XP, включая детализацию по полям
        """
        xp_breakdown = {}
        total_xp = 0
        total_fields = 0
        filled_fields = 0
        
        # Проверяем простые поля
        simple_fields = [
            "first_name", "last_name", "phone", "birth_date", 
            "location", "about", "desired_salary", "ready_to_relocate", 
            "employment_type"
        ]
        
        for field in simple_fields:
            total_fields += 1
            value = getattr(user, field, None)
            
            if cls._is_field_filled(value):
                filled_fields += 1
                field_xp = cls.XP_CONFIG[field]
                total_xp += field_xp
                xp_breakdown[field] = {
                    "xp": field_xp,
                    "filled": True,
                    "description": cls._get_field_description(field)
                }
            else:
                xp_breakdown[field] = {
                    "xp": 0,
                    "filled": False,
                    "potential_xp": cls.XP_CONFIG[field],
                    "description": cls._get_field_description(field)
                }
        
        # Проверяем сложные поля (массивы)
        complex_fields = ["programming_languages", "foreign_languages", "other_competencies", "work_experience", "education"]
        
        for field in complex_fields:
            total_fields += 1
            value = getattr(user, field, None)
            field_config = cls.XP_CONFIG[field]
            
            if cls._is_field_filled(value) and isinstance(value, list) and len(value) > 0:
                filled_fields += 1
                # Базовый XP за наличие поля
                field_xp = field_config["base"]
                # XP за каждый элемент (с ограничением)
                items_count = min(len(value), field_config["max_items"])
                field_xp += items_count * field_config["per_item"]
                
                total_xp += field_xp
                xp_breakdown[field] = {
                    "xp": field_xp,
                    "filled": True,
                    "items_count": len(value),
                    "items_counted": items_count,
                    "base_xp": field_config["base"],
                    "items_xp": items_count * field_config["per_item"],
                    "description": cls._get_field_description(field)
                }
            else:
                xp_breakdown[field] = {
                    "xp": 0,
                    "filled": False,
                    "potential_base_xp": field_config["base"],
                    "potential_per_item": field_config["per_item"],
                    "max_items": field_config["max_items"],
                    "description": cls._get_field_description(field)
                }
        
        # Рассчитываем процент заполненности
        completion_percentage = (filled_fields / total_fields) * 100 if total_fields > 0 else 0
        
        # Добавляем бонусы за заполненность
        completion_bonus = 0
        for threshold, bonus in cls.COMPLETION_BONUSES.items():
            if completion_percentage >= threshold:
                completion_bonus = bonus
        
        total_xp += completion_bonus
        
        return {
            "total_xp": total_xp,
            "base_xp": total_xp - completion_bonus,
            "completion_bonus": completion_bonus,
            "completion_percentage": round(completion_percentage, 1),
            "filled_fields": filled_fields,
            "total_fields": total_fields,
            "xp_breakdown": xp_breakdown,
            "next_bonus": cls._get_next_bonus(completion_percentage)
        }
    
    @classmethod
    def update_user_xp(cls, user: User, db: Session) -> Dict[str, Any]:
        """
        Обновляет XP пользователя в базе данных
        
        Returns:
            Информация о новом XP
        """
        xp_info = cls.calculate_user_xp(user)
        old_xp = user.xp or 0
        new_xp = xp_info["total_xp"]
        
        user.xp = new_xp
        db.commit()
        
        xp_info["old_xp"] = old_xp
        xp_info["xp_gained"] = new_xp - old_xp
        
        return xp_info
    
    @classmethod
    def _is_field_filled(cls, value: Any) -> bool:
        """Проверяет, заполнено ли поле"""
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != "" and value.strip() != "—"
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, bool):
            return True  # Булевые поля считаются заполненными, если установлены
        return True
    
    @classmethod
    def _get_field_description(cls, field: str) -> str:
        """Возвращает описание поля для пользователя"""
        descriptions = {
            "first_name": "Имя",
            "last_name": "Фамилия", 
            "phone": "Номер телефона",
            "birth_date": "Дата рождения",
            "location": "Местоположение",
            "about": "О себе",
            "desired_salary": "Желаемая зарплата",
            "ready_to_relocate": "Готовность к переезду",
            "employment_type": "Тип занятости",
            "programming_languages": "Языки программирования",
            "foreign_languages": "Иностранные языки", 
            "other_competencies": "Другие компетенции",
            "work_experience": "Опыт работы",
            "education": "Образование"
        }
        return descriptions.get(field, field)
    
    @classmethod
    def _get_next_bonus(cls, current_percentage: float) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о следующем бонусе за заполненность"""
        for threshold, bonus in sorted(cls.COMPLETION_BONUSES.items()):
            if current_percentage < threshold:
                return {
                    "threshold": threshold,
                    "bonus": bonus,
                    "percentage_needed": threshold - current_percentage
                }
        return None

# Глобальный экземпляр сервиса
xp_service = XPService()
