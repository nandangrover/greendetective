from django.db import migrations
from detective.models.payment_plan import PaymentPlan

def create_initial_plans(apps, schema_editor):
    PaymentPlan = apps.get_model('detective', 'PaymentPlan')
    
    plans = [
        {
            'name': 'BETA',
            'max_reports': 3,
            'price': 0.00,
            'description': 'Beta testing plan with limited features'
        },
        {
            'name': 'BASIC',
            'max_reports': 10,
            'price': 99,
            'description': 'Basic plan for small businesses'
        },
        {
            'name': 'PRO',
            'max_reports': 50,
            'price': 299,
            'description': 'Professional plan for growing businesses'
        },
        {
            'name': 'ENTERPRISE',
            'max_reports': 200,
            'price': 999,
            'description': 'Enterprise plan for large organizations'
        }
    ]
    
    for plan_data in plans:
        PaymentPlan.objects.get_or_create(**plan_data)

def assign_beta_plan_to_businesses(apps, schema_editor):
    PaymentPlan = apps.get_model('detective', 'PaymentPlan')
    Business = apps.get_model('detective', 'Business')
    
    beta_plan = PaymentPlan.objects.filter(name='BETA').first()
    if beta_plan:
        Business.objects.filter(payment_plan__isnull=True).update(payment_plan=beta_plan)

class Migration(migrations.Migration):

    dependencies = [
        ('detective', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_plans),
        migrations.RunPython(assign_beta_plan_to_businesses),
    ]