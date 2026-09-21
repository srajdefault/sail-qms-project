from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

# ------------------------------------------------------------------
# 1. USER PROFILES & ROLE-BASED ACCESS (Maker-Checker Workflow)
# ------------------------------------------------------------------
class OperatorProfile(models.Model):
    ROLE_CHOICES = [
        ('OPERATOR', 'Field Operator (Maker)'),
        ('SUPERVISOR', 'Supervisor (Checker)'),
        ('MANAGER', 'Manager'),
        ('ADMIN', 'System Administrator'),  # <--- Added Admin Role
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='operator_profile')
    employee_id = models.CharField(max_length=20, unique=True, help_text="e.g., EMP001")
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OPERATOR')
    
    # OTP Authentication Fields
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    
    # Field Tracking (For Manager View)
    is_active_on_field = models.BooleanField(
        default=False, 
        help_text="Manager Status Indicator: True = Green Dot (Working), False = Red Dot (Not Working)"
    )
    last_active = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "Working (Green)" if self.is_active_on_field else "Not Working (Red)"
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()} - {self.employee_id}) - {status}"


# ------------------------------------------------------------------
# 2. MASTER DATA (Sector & Quarter Management)
# ------------------------------------------------------------------
class Sector(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="e.g., Sector 4F")
    
    # Coordinates & Radius for Haversine Distance Geofencing
    center_latitude = models.FloatField(
        null=True, 
        blank=True, 
        help_text="Sector center latitude (e.g., 23.6688)"
    )
    center_longitude = models.FloatField(
        null=True, 
        blank=True, 
        help_text="Sector center longitude (e.g., 86.1489)"
    )
    allowed_radius_meters = models.FloatField(
        default=500.0, 
        help_text="Maximum allowed distance in meters from center for verification (e.g., 500.0)"
    )
    
    # Optional Polygon cache boundary
    boundary_coordinates = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of coordinate dicts defining the sector polygon boundary"
    )

    def __str__(self):
        return self.name


class QuarterMaster(models.Model):
    quarter_code = models.CharField(
        max_length=20, 
        primary_key=True, 
        help_text="Primary Key format: 04F/C/1281"
    )
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='quarters')
    quarter_type = models.CharField(
        max_length=1, 
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
        help_text="Quarter Category: A, B, C, or D"
    )
    quarter_number = models.IntegerField(
        help_text="Numeric component (e.g., 1281). System automatically zero-pads to 4 digits."
    )

    def clean(self):
        if self.quarter_number < 0 or self.quarter_number > 9999:
            raise ValidationError({'quarter_number': 'Quarter number must be between 0 and 9999.'})

    def save(self, *args, **kwargs):
        raw_sector = self.sector.name.upper().replace("SECTOR", "").strip()
        formatted_sector = f"0{raw_sector}" if len(raw_sector) == 2 else raw_sector
        formatted_type = self.quarter_type.upper()
        formatted_num = f"{self.quarter_number:04d}"

        self.quarter_code = f"{formatted_sector}/{formatted_type}/{formatted_num}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.quarter_code


# ------------------------------------------------------------------
# 3. INSPECTION REPORTS (Maker-Checker Workflow)
# ------------------------------------------------------------------
class InspectionReport(models.Model):
    STATUS_CHOICES = [
        ('LOCKED', 'Locked'),
        ('VACANT', 'Vacant'),
        ('OCCUPIED_AUTHORIZED', 'Occupied (Authorized)'),
        ('OCCUPIED_UNAUTHORIZED', 'Occupied (Unauthorized / Others)'),
    ]
    
    VERIFICATION_CHOICES = [
        ('PENDING', 'Pending Supervisor Approval'),
        ('APPROVED', 'Approved'),
        ('RECHECK', 'Sent Back for Recheck'),
    ]

    quarter = models.ForeignKey(QuarterMaster, on_delete=models.CASCADE, related_name='inspections')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='operator_inspections')
    
    quarter_status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    photo = models.ImageField(upload_to='inspection_photos/')
    remarks = models.TextField(blank=True, null=True, help_text="Operator optional notes/remarks space")
    
    captured_latitude = models.FloatField(null=True, blank=True)
    captured_longitude = models.FloatField(null=True, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)

    is_location_verified = models.BooleanField(
        default=False, 
        help_text="Set to True via Haversine radius check"
    )
    verification_status = models.CharField(
        max_length=20, 
        choices=VERIFICATION_CHOICES, 
        default='PENDING'
    )
    
    supervisor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='supervisor_reviews'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    supervisor_feedback = models.TextField(blank=True, null=True, help_text="Supervisor feedback notes for rechecks")

    def __str__(self):
        return f"{self.quarter.quarter_code} - Status: {self.quarter_status} ({self.verification_status})"