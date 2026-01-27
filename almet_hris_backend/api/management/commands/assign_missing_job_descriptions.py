# api/management/commands/assign_missing_job_descriptions.py
"""
Django management command to assign missing job descriptions to existing employees

Usage:
python manage.py assign_missing_job_descriptions
python manage.py assign_missing_job_descriptions --dry-run  # Test without saving
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Assign missing job descriptions to existing employees'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test run without saving changes',
        )
        
        parser.add_argument(
            '--employee-id',
            type=int,
            help='Assign only for specific employee ID',
        )
    
    def handle(self, *args, **options):
        # ✅ Lazy imports to avoid model loading issues
        from api.models import Employee
        from api.job_description_models import JobDescription, JobDescriptionAssignment, normalize_grading_level
        
        dry_run = options.get('dry_run', False)
        employee_id = options.get('employee_id')
        
        self.stdout.write("=" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 DRY RUN MODE - No changes will be saved"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ LIVE MODE - Changes will be saved"))
        self.stdout.write("=" * 80)
        
        total_assigned = 0
        total_checked = 0
        total_skipped = 0
        
        # Get employees
        if employee_id:
            employees = Employee.objects.filter(id=employee_id, is_deleted=False)
            if not employees.exists():
                self.stdout.write(self.style.ERROR(f"❌ Employee with ID {employee_id} not found"))
                return
        else:
            employees = Employee.objects.filter(is_deleted=False)
        
        employees = employees.select_related(
            'business_function', 'department', 'unit', 'job_function', 'position_group', 'line_manager'
        )
        
        self.stdout.write(f"\n📊 Processing {employees.count()} employees...\n")
        
        for employee in employees:
            total_checked += 1
            
            if not employee.job_title:
                self.stdout.write(self.style.WARNING(f"⚠️ No job title: {employee.full_name}"))
                total_skipped += 1
                continue
            
            # Find matching job descriptions
            matching_jds = JobDescription.objects.filter(
                job_title__iexact=employee.job_title.strip(),
                business_function=employee.business_function,
                department=employee.department,
                job_function=employee.job_function,
                position_group=employee.position_group,
                is_active=True
            )
            
            if employee.unit:
                matching_jds = matching_jds.filter(unit=employee.unit)
            
            if not matching_jds.exists():
                self.stdout.write(
                    self.style.WARNING(f"⚠️ No matching JD: {employee.full_name} ({employee.job_title})")
                )
                total_skipped += 1
                continue
            
            assigned_this_employee = False
            
            for jd in matching_jds:
                # Check grading level
                emp_grade_normalized = normalize_grading_level(employee.grading_level or '')
                jd_grades_normalized = [normalize_grading_level(gl) for gl in jd.grading_levels]
                
                if emp_grade_normalized not in jd_grades_normalized:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️ Grading mismatch: {employee.full_name} has '{employee.grading_level}' "
                            f"but JD requires {jd.grading_levels}"
                        )
                    )
                    continue
                
                # Check if already assigned
                existing_assignment = JobDescriptionAssignment.objects.filter(
                    job_description=jd,
                    employee=employee,
                    is_active=True
                ).exists()
                
                if existing_assignment:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Already assigned: {employee.full_name} -> {jd.job_title}")
                    )
                    assigned_this_employee = True
                    break
                
                # Create assignment
                if not dry_run:
                    try:
                        with transaction.atomic():
                            assignment = JobDescriptionAssignment.objects.create(
                                job_description=jd,
                                employee=employee,
                                is_vacancy=False,
                                reports_to=employee.line_manager
                            )
                            total_assigned += 1
                            assigned_this_employee = True
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"✅ ASSIGNED: {employee.full_name} -> {jd.job_title} (ID: {assignment.id})"
                                )
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Failed to assign {employee.full_name}: {str(e)}")
                        )
                else:
                    total_assigned += 1
                    assigned_this_employee = True
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ WOULD ASSIGN: {employee.full_name} -> {jd.job_title} (DRY RUN)"
                        )
                    )
                
                # Only assign to first matching JD
                break
            
            if not assigned_this_employee and not existing_assignment:
                total_skipped += 1
        
        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 SUMMARY:"))
        self.stdout.write(f"   Total Employees Checked: {total_checked}")
        self.stdout.write(f"   Total Assignments {'Would Be ' if dry_run else ''}Created: {total_assigned}")
        self.stdout.write(f"   Total Skipped: {total_skipped}")
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️ This was a DRY RUN - No changes were saved"))
            self.stdout.write(self.style.WARNING("Run without --dry-run to save changes"))
        self.stdout.write("=" * 80)# api/management/commands/assign_missing_job_descriptions.py
"""
Django management command to assign missing job descriptions to existing employees

Usage:
python manage.py assign_missing_job_descriptions
python manage.py assign_missing_job_descriptions --dry-run  # Test without saving
"""

from django.core.management.base import BaseCommand
from api.signals import assign_missing_job_descriptions  # ✅ Import from signals


class Command(BaseCommand):
    help = 'Assign missing job descriptions to existing employees'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test run without saving changes (not implemented yet)',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        self.stdout.write("=" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️ Note: Dry-run mode not fully implemented"))
        self.stdout.write(self.style.SUCCESS("🚀 Starting auto-assignment..."))
        self.stdout.write("=" * 80)
        
        # Call the helper function
        result = assign_missing_job_descriptions()
        
        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 SUMMARY:"))
        self.stdout.write(f"   Total Employees Checked: {result['total_checked']}")
        self.stdout.write(f"   Total Assignments Created: {result['total_assigned']}")
        self.stdout.write("=" * 80)