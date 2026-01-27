# management/commands/load_permissions.py
# Run: python manage.py load_permissions

from django.core.management.base import BaseCommand
from api.role_models import Permission

class Command(BaseCommand):
    help = 'Load all permissions into database'

    def handle(self, *args, **kwargs):
        permissions_data = [

            # BUSINESS TRIPS
            ('business_trips.request.view', 'View Business Trip Requests', 'Business Trips'),
            ('business_trips.request.create', 'Create Business Trip Request', 'Business Trips'),
            ('business_trips.request.update', 'Update Business Trip Request', 'Business Trips'),
            ('business_trips.request.delete', 'Delete Business Trip Request', 'Business Trips'),
            ('business_trips.request.submit', 'Submit Business Trip Request', 'Business Trips'),
            ('business_trips.request.approve', 'Approve Business Trip Request', 'Business Trips'),
            ('business_trips.request.cancel', 'Cancel Business Trip', 'Business Trips'),
            ('business_trips.request.view_pending', 'View Pending Approvals', 'Business Trips'),
            ('business_trips.request.view_statistics', 'View Trip Statistics', 'Business Trips'),
            ('business_trips.export_all', 'Export All Business Trip Records', 'Business Trips'),
            ('business_trips.settings.view', 'View Trip Settings', 'Business Trips'),
            ('business_trips.settings.update', 'Update Trip Settings', 'Business Trips'),
            

           
        ]
        
        created_count = 0
        updated_count = 0
        
        for codename, name, category in permissions_data:
            permission, created = Permission.objects.update_or_create(
                codename=codename,
                defaults={
                    'name': name,
                    'category': category,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {codename}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Updated: {codename}'))
        
        # Summary by category
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY BY CATEGORY:'))
        self.stdout.write('='*60)
        
        categories = {}
        for codename, name, category in permissions_data:
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        for category, count in sorted(categories.items()):
            self.stdout.write(f'  {category}: {count} permissions')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✓ Created: {created_count} permissions'))
        self.stdout.write(self.style.SUCCESS(f'↻ Updated: {updated_count} permissions'))
        self.stdout.write(self.style.SUCCESS(f'Total: {created_count + updated_count} permissions'))
        self.stdout.write('='*60)