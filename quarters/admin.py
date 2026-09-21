from django.contrib import admin
from .models import Sector, QuarterMaster, InspectionReport, OperatorProfile

@admin.register(OperatorProfile)
class OperatorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'role', 'is_active_on_field')

@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(QuarterMaster)
class QuarterMasterAdmin(admin.ModelAdmin):
    list_display = ('quarter_code', 'sector', 'quarter_type', 'quarter_number')

@admin.register(InspectionReport)
class InspectionReportAdmin(admin.ModelAdmin):
    list_display = ('quarter', 'operator', 'quarter_status', 'verification_status', 'captured_at')