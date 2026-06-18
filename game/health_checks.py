from django.db import connection
from django.db.utils import DatabaseError
import logging

from .models import (
    ChessPuzzle,
    Achievement,
    LessonProgress,
    OpeningProgress,
)

logger = logging.getLogger(__name__)


def check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except DatabaseError:
        return False
    except Exception:
        logger.exception(
            "Unexpected error during database health check"
        )
        return False


def check_puzzles():
    try:
        ChessPuzzle.objects.exists()
        return True
    except DatabaseError:
        return False
    except Exception:
        logger.exception(
            "Unexpected error during puzzle health check"
        )
        return False


def check_achievements():
    try:
        Achievement.objects.exists()
        return True
    except DatabaseError:
        return False
    except Exception:
        logger.exception(
            "Unexpected error during achievement health check"
        )
        return False


def check_lessons():
    try:
        LessonProgress.objects.exists()
        return True
    except DatabaseError:
        return False
    except Exception:
        logger.exception(
            "Unexpected error during lesson health check"
        )
        return False


def check_openings():
    try:
        OpeningProgress.objects.exists()
        return True
    except DatabaseError:
        return False
    except Exception:
        logger.exception(
            "Unexpected error during opening trainer health check"
        )
        return False
