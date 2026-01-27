# api/management/commands/update_employee_statuses.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Employee
from api.status_management import EmployeeStatusManager
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Manually update all employee statuses based on contract dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--employee-id',
            type=int,
            help='Update specific employee by ID',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if status appears correct',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(f'🔄 EMPLOYEE STATUS UPDATE COMMAND'))
        self.stdout.write(self.style.SUCCESS(f'⏰ Started at: {timezone.now()}'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        employee_id = options.get('employee_id')
        force = options.get('force', False)
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('📋 DRY RUN MODE - No changes will be made'))
        
        if employee_id:
            # Update single employee
            self._update_single_employee(employee_id, force, dry_run)
        else:
            # Update all employees
            self._update_all_employees(force, dry_run)
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(f'✅ Command completed at: {timezone.now()}'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
    
    def _update_single_employee(self, employee_id, force, dry_run):
        """Update single employee"""
        try:
            employee = Employee.objects.get(id=employee_id)
            self.stdout.write(f"\n📌 Processing employee: {employee.employee_id} - {employee.full_name}")
            
            preview = EmployeeStatusManager.get_status_preview(employee)
            
            self.stdout.write(f"   Current Status: {preview['current_status']}")
            self.stdout.write(f"   Required Status: {preview['required_status']}")
            self.stdout.write(f"   Needs Update: {preview['needs_update']}")
            self.stdout.write(f"   Reason: {preview['reason']}")
            self.stdout.write(f"   Days Since Start: {preview['days_since_start']}")
            
            if preview['needs_update'] or force:
                if not dry_run:
                    result = EmployeeStatusManager.update_employee_status(employee, force_update=force, user=None)
                    if result:
                        self.stdout.write(self.style.SUCCESS(f"   ✅ Updated successfully"))
                    else:
                        self.stdout.write(self.style.WARNING(f"   ⚠️ Update returned False"))
                else:
                    self.stdout.write(self.style.WARNING(f"   [DRY RUN] Would update"))
            else:
                self.stdout.write(f"   ℹ️  No update needed")
                
        except Employee.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Employee {employee_id} not found'))
    
    def _update_all_employees(self, force, dry_run):
        """✅ FIXED: Only update employees who have started"""
        
        # ✅ CRITICAL: Only employees who have STARTED
        employees = Employee.objects.filter(
            is_deleted=False,
            start_date__lte=timezone.now().date()  # ✅ Only started employees
        ).select_related('status')
        
        total = employees.count()
        updated = 0
        no_update_needed = 0
        errors = 0
        future_start = 0
        
        self.stdout.write(f"\n📊 Processing {total} employees (who have started)\n")
        
        # ✅ Show future employees separately
        future_employees = Employee.objects.filter(
            is_deleted=False,
            start_date__gt=timezone.now().date()
        ).count()
        
        if future_employees > 0:
            self.stdout.write(f"ℹ️  {future_employees} employees with future start dates (will be skipped)\n")
        
        for employee in employees:
            try:
                preview = EmployeeStatusManager.get_status_preview(employee)
                
                # ✅ Double-check: Skip if future start
                if "future" in preview['reason'].lower() or "hasn't started" in preview['reason'].lower():
                    future_start += 1
                    continue
                
                if preview['needs_update'] or force:
                    self.stdout.write(f"⚡ {employee.employee_id} ({employee.full_name})")
                    self.stdout.write(f"   {preview['current_status']} → {preview['required_status']}")
                    self.stdout.write(f"   Reason: {preview['reason']}")
                    self.stdout.write(f"   Days Since Start: {preview['days_since_start']}")
                    
                    if not dry_run:
                        result = EmployeeStatusManager.update_employee_status(employee, force_update=force, user=None)
                        if result:
                            updated += 1
                            self.stdout.write(self.style.SUCCESS(f"   ✅ Updated"))
                        else:
                            self.stdout.write(self.style.WARNING(f"   ⚠️ No change"))
                    else:
                        updated += 1
                        self.stdout.write(self.style.WARNING(f"   [DRY RUN] Would update"))
                else:
                    no_update_needed += 1
                    
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f"❌ Error for {employee.employee_id}: {str(e)}"))
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Total Employees (Started): {total}")
        self.stdout.write(self.style.SUCCESS(f"   Updated: {updated}"))
        self.stdout.write(f"   No Update Needed: {no_update_needed}")
        self.stdout.write(f"   Future Start Dates: {future_start}")
        if errors > 0:
            self.stdout.write(self.style.ERROR(f"   Errors: {errors}"))