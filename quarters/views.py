import json
import math
import random
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings

from .models import QuarterMaster, InspectionReport, OperatorProfile, Sector
from .decorators import role_required


# ------------------------------------------------------------------
# HAVERSINE DISTANCE HELPER FUNCTION
# ------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on Earth in meters.
    """
    R = 6371000.0  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c  # Distance in meters


# ------------------------------------------------------------------
# RAY-CASTING POINT-IN-POLYGON HELPER FUNCTION
# ------------------------------------------------------------------
def is_point_in_polygon(lat, lng, polygon_coords):
    """
    Ray-Casting Algorithm to check if a point (lat, lng) is inside a polygon boundary.
    Handles any dynamic number of vertices (polygon_coords).
    polygon_coords: List of dicts -> [{'lat': 23.66, 'lng': 86.15}, ...]
    """
    n = len(polygon_coords)
    inside = False

    p1x, p1y = polygon_coords[0]['lat'], polygon_coords[0]['lng']
    for i in range(n + 1):
        p2x, p2y = polygon_coords[i % n]['lat'], polygon_coords[i % n]['lng']
        if lng > min(p1y, p2y):
            if lng <= max(p1y, p2y):
                if lat <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lng - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lat <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


# ------------------------------------------------------------------
# 1. AUTHENTICATION & OTP SYSTEM
# ------------------------------------------------------------------
def request_otp_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()  # Phone, Username, or Email

        user = User.objects.filter(
            models.Q(username=identifier) |
            models.Q(email=identifier) |
            models.Q(operator_profile__phone_number=identifier)
        ).first()

        if not user:
            user = User.objects.create_user(
                username=identifier,
                email=identifier if '@' in identifier else ''
            )
            profile = OperatorProfile.objects.create(
                user=user,
                employee_id=f"EMP{random.randint(100, 999)}",
                role='OPERATOR'
            )
        else:
            profile, _ = OperatorProfile.objects.get_or_create(user=user)

        generated_otp = str(random.randint(100000, 999999))
        profile.otp_code = generated_otp
        profile.otp_created_at = timezone.now()
        profile.save()

        print("\n" + "=" * 40)
        print(f"🔥 OTP FOR {user.username}: {generated_otp}")
        print("=" * 40 + "\n")

        request.session['auth_user_id'] = user.id
        
        next_url = request.GET.get('next', '')
        if next_url:
            return redirect(f"/verify-otp/?next={next_url}")
            
        return redirect('verify_otp')

    return render(request, 'quarters/login_request_otp.html')


def verify_otp_view(request):
    user_id = request.session.get('auth_user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    profile, _ = OperatorProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()

        if profile.otp_code and profile.otp_code == entered_otp:
            profile.otp_code = None
            profile.save()
            login(request, user)

            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)

            if profile.role == 'SUPERVISOR':
                return redirect('supervisor_dashboard')
            elif profile.role == 'MANAGER':
                return redirect('manager_overview')
            else:
                return redirect('operator_submit')
        else:
            messages.error(request, "Invalid or expired OTP. Please try again.")

    return render(request, 'quarters/verify_otp.html', {'user': user})


def logout_view(request):
    """
    User logout view: Deactivates live field status on logout.
    """
    if request.user.is_authenticated:
        profile = getattr(request.user, 'operator_profile', None)
        if profile:
            profile.is_active_on_field = False
            profile.save()

    logout(request)
    return redirect('login')


# ------------------------------------------------------------------
# 2. OPERATOR (MAKER) VIEW: Submit Inspection
# ------------------------------------------------------------------
@login_required
@role_required(allowed_roles=['OPERATOR'])
def operator_submit_view(request):
    if request.method == 'POST':
        quarter_code = request.POST.get('quarter_code')
        status = request.POST.get('quarter_status')
        remarks = request.POST.get('remarks')
        photo = request.FILES.get('photo')
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')

        quarter = get_object_or_404(QuarterMaster, quarter_code=quarter_code)

        InspectionReport.objects.create(
            quarter=quarter,
            operator=request.user,
            quarter_status=status,
            photo=photo,
            remarks=remarks,
            captured_latitude=float(lat) if lat else None,
            captured_longitude=float(lng) if lng else None,
        )

        profile, _ = OperatorProfile.objects.get_or_create(user=request.user)
        profile.is_active_on_field = True
        profile.save()

        return redirect('operator_success')

    quarters = QuarterMaster.objects.all()
    return render(request, 'quarters/operator_form.html', {'quarters': quarters})


@login_required
@role_required(allowed_roles=['OPERATOR'])
def operator_success_view(request):
    return render(request, 'quarters/operator_success.html')


# ------------------------------------------------------------------
# 3. SUPERVISOR (CHECKER) VIEW: Review & Action Dashboard
# ------------------------------------------------------------------
@login_required
@role_required(allowed_roles=['SUPERVISOR'])
def supervisor_dashboard_view(request):
    selected_sector = request.GET.get('sector', '')
    reports = InspectionReport.objects.all().order_by('-captured_at')

    if selected_sector:
        reports = reports.filter(quarter__sector__name=selected_sector)

    sectors = Sector.objects.all()
    return render(request, 'quarters/supervisor_dashboard.html', {
        'reports': reports,
        'sectors': sectors,
        'selected_sector': selected_sector
    })


@login_required
@role_required(allowed_roles=['SUPERVISOR'])
def review_inspection_view(request, report_id=0):
    if request.method == 'POST':
        # --- A. Bulk Processing Flow ---
        selected_ids = request.POST.getlist('selected_reports')
        bulk_action = request.POST.get('bulk_action')

        if selected_ids and bulk_action:
            reports = InspectionReport.objects.filter(id__in=selected_ids)
            updated_count = 0
            for report in reports:
                # Guardrail: Approval strictly requires GPS verification
                if bulk_action == 'APPROVED' and not report.is_location_verified:
                    continue

                report.verification_status = bulk_action
                report.supervisor = request.user
                report.reviewed_at = timezone.now()
                feedback = request.POST.get(f'feedback_{report.id}')
                if feedback:
                    report.supervisor_feedback = feedback
                report.save()
                updated_count += 1

            messages.success(request, f"Successfully processed {updated_count} report(s) to {bulk_action}.")
            return redirect('supervisor_dashboard')

        # --- B. Single Row Processing Flow ---
        single_action = request.POST.get('single_action')
        if single_action and '_' in single_action:
            action, r_id = single_action.split('_')
            report = get_object_or_404(InspectionReport, id=r_id)

            # Security Guardrail: Approve karne ke liye location verification mandatory hai
            if action == 'APPROVED' and not report.is_location_verified:
                messages.error(request, f"Cannot Approve Quarter {report.quarter.quarter_code}. GPS verification required first!")
                return redirect('supervisor_dashboard')

            report.verification_status = action
            report.supervisor = request.user
            report.reviewed_at = timezone.now()
            report.supervisor_feedback = request.POST.get(f'feedback_{r_id}', '')
            report.save()

            messages.success(request, f"Quarter {report.quarter.quarter_code} status updated to {action}.")
            return redirect('supervisor_dashboard')

        # --- C. Fallback Individual Processing ---
        if report_id > 0:
            report = get_object_or_404(InspectionReport, id=report_id)
            action = request.POST.get('action')
            feedback = request.POST.get('supervisor_feedback', '')

            if action in ['APPROVED', 'RECHECK']:
                if action == 'APPROVED' and not report.is_location_verified:
                    messages.error(request, f"Cannot Approve Quarter {report.quarter.quarter_code}. GPS verification required first!")
                    return redirect('supervisor_dashboard')

                report.verification_status = action
                report.supervisor = request.user
                report.reviewed_at = timezone.now()
                report.supervisor_feedback = feedback
                report.save()

                messages.success(request, f"Quarter {report.quarter.quarter_code} status updated to {action}.")

    return redirect('supervisor_dashboard')


# ------------------------------------------------------------------
# 4. MANAGER VIEW: Operational Overview & Metrics
# ------------------------------------------------------------------
@login_required
@role_required(allowed_roles=['MANAGER'])
def manager_overview_view(request):
    # Only fetch Field Operators for live tracking (Filtering out Supervisors & Managers)
    operators = OperatorProfile.objects.filter(role='OPERATOR').select_related('user')
    
    total_inspections = InspectionReport.objects.count()
    pending_reviews = InspectionReport.objects.filter(verification_status='PENDING').count()
    approved_count = InspectionReport.objects.filter(verification_status='APPROVED').count()
    recheck_count = InspectionReport.objects.filter(verification_status='RECHECK').count()

    return render(request, 'quarters/manager_overview.html', {
        'operators': operators,
        'total_inspections': total_inspections,
        'pending_reviews': pending_reviews,
        'approved_count': approved_count,
        'recheck_count': recheck_count,
    })


# ------------------------------------------------------------------
# 5. GEOFENCING API: Smart Hybrid Geofencing Verification
# ------------------------------------------------------------------
@login_required
@role_required(allowed_roles=['SUPERVISOR', 'MANAGER'])
def verify_gps_api(request, report_id):
    try:
        report = get_object_or_404(InspectionReport, id=report_id)
        
        captured_lat = report.captured_latitude
        captured_lng = report.captured_longitude
        
        if not report.quarter:
            return JsonResponse({'status': 'error', 'is_verified': False, 'message': 'Report se koi Quarter linked nahi hai.'}, status=200)
            
        if not report.quarter.sector:
            return JsonResponse({'status': 'error', 'is_verified': False, 'message': 'Quarter se koi Sector linked nahi hai.'}, status=200)

        sector = report.quarter.sector

        if captured_lat is None or captured_lng is None:
            return JsonResponse({'status': 'error', 'is_verified': False, 'message': 'GPS Lat/Lng coordinates missing hain.'}, status=200)

        # -------------------------------------------------------------
        # AUTOMATIC CHECK 1: Polygon Boundary Check (Ray-Casting)
        # -------------------------------------------------------------
        polygon_coords = getattr(sector, 'boundary_coordinates', None)

        if polygon_coords:
            if isinstance(polygon_coords, str):
                polygon_coords = json.loads(polygon_coords)

            if len(polygon_coords) >= 3:
                is_inside = is_point_in_polygon(captured_lat, captured_lng, polygon_coords)
                report.is_location_verified = is_inside
                report.save()

                print("\n" + "=" * 50)
                print(f"📍 CAPTURED GPS: {captured_lat}, {captured_lng}")
                print(f"🗺️ POLYGON CHECK ({len(polygon_coords)} vertices): INSIDE = {is_inside}")
                print("=" * 50 + "\n")

                if is_inside:
                    return JsonResponse({
                        'status': 'success',
                        'is_verified': True,
                        'message': f"Verified! Position is strictly INSIDE polygon boundary for {sector.name}."
                    })
                else:
                    return JsonResponse({
                        'status': 'success',
                        'is_verified': False,
                        'message': f"Fraud Alert! Position is OUTSIDE polygon boundary for {sector.name}."
                    })

        # -------------------------------------------------------------
        # AUTOMATIC FALLBACK 2: Circular Radius Check (Haversine Formula)
        # -------------------------------------------------------------
        center_lat = getattr(sector, 'center_latitude', None)
        center_lng = getattr(sector, 'center_longitude', None)

        if center_lat is None or center_lng is None:
            return JsonResponse({
                'status': 'error', 
                'is_verified': False, 
                'message': f"Sector '{sector.name}' ke boundary points or center coordinates Admin Panel me missing hain."
            }, status=200)

        distance_meters = haversine_distance(captured_lat, captured_lng, center_lat, center_lng)
        allowed_radius = getattr(sector, 'allowed_radius_meters', None) or 500.0

        print("\n" + "=" * 50)
        print(f"📍 CAPTURED GPS: {captured_lat}, {captured_lng}")
        print(f"🎯 SECTOR CENTER: {center_lat}, {center_lng}")
        print(f"📏 CALCULATED DISTANCE: {round(distance_meters, 2)}m | ALLOWED: {allowed_radius}m")
        print("=" * 50 + "\n")

        if distance_meters <= allowed_radius:
            report.is_location_verified = True
            report.save()
            return JsonResponse({
                'status': 'success',
                'is_verified': True,
                'message': f"Verified! Distance: {round(distance_meters, 1)}m from {sector.name} center (Allowed: {int(allowed_radius)}m)."
            })
        else:
            report.is_location_verified = False
            report.save()
            return JsonResponse({
                'status': 'success',
                'is_verified': False,
                'message': f"Fraud Alert! Distance: {round(distance_meters, 1)}m is outside allowed radius ({int(allowed_radius)}m) for {sector.name}."
            })

    except Exception as e:
        print(f"\n💥 GPS VERIFICATION EXCEPTION: {str(e)}\n")
        return JsonResponse({
            'status': 'error', 
            'is_verified': False, 
            'message': f"Server Exception: {str(e)}"
        }, status=200)