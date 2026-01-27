# api/management/commands/reset_competency_sequences.py

from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Reset all competency table sequences'

    def handle(self, *args, **options):
        tables = [
            'competency_skills',
            'competency_skill_groups',
            'competency_behavioral',
            'competency_behavioral_groups',
            'competency_leadership_main_groups',
            'competency_leadership_child_groups',
            'competency_leadership_items',
        ]
        
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM {table}), 1),
                            true
                        );
                    """)
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {table} sequence reset edildi')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ {table} xəta: {str(e)}')
                    )