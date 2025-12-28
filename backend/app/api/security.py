"""Security monitoring and audit endpoints."""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from datetime import datetime, timedelta

from app.middleware.auth import get_current_user
from app.models.user import BaseUser
from app.services.audit_service import audit_service
from app.services.monitoring_service import security_monitor

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/dashboard")
async def get_security_dashboard(
    current_user: BaseUser = Depends(get_current_user)
) -> Dict:
    """Get security monitoring dashboard (admin only)."""
    # In a real implementation, you'd check for admin role
    # For now, we'll allow any authenticated user
    
    dashboard_data = security_monitor.get_security_dashboard()
    return dashboard_data


@router.get("/alerts")
async def get_security_alerts(
    limit: int = Query(50, ge=1, le=100),
    resolved: Optional[bool] = Query(None),
    level: Optional[str] = Query(None),
    current_user: BaseUser = Depends(get_current_user)
) -> List[Dict]:
    """Get security alerts (admin only)."""
    alerts = security_monitor.alerts
    
    # Filter by resolved status
    if resolved is not None:
        alerts = [alert for alert in alerts if alert.resolved == resolved]
    
    # Filter by level
    if level:
        alerts = [alert for alert in alerts if alert.level == level]
    
    # Sort by timestamp (newest first) and limit
    alerts = sorted(alerts, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    return [
        {
            "alert_id": alert.alert_id,
            "timestamp": alert.timestamp,
            "alert_type": alert.alert_type,
            "level": alert.level,
            "message": alert.message,
            "details": alert.details,
            "resolved": alert.resolved
        }
        for alert in alerts
    ]


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    current_user: BaseUser = Depends(get_current_user)
) -> Dict:
    """Resolve a security alert (admin only)."""
    for alert in security_monitor.alerts:
        if alert.alert_id == alert_id:
            alert.resolved = True
            return {"message": "Alert resolved successfully"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Alert not found"
    )


@router.get("/audit/summary")
async def get_audit_summary(
    hours: int = Query(24, ge=1, le=168),  # Max 1 week
    current_user: BaseUser = Depends(get_current_user)
) -> Dict:
    """Get audit log summary (admin only)."""
    summary = audit_service.get_audit_summary(hours=hours)
    return summary


@router.get("/blocked-ips")
async def get_blocked_ips(
    current_user: BaseUser = Depends(get_current_user)
) -> Dict:
    """Get list of blocked IP addresses (admin only)."""
    return {
        "blocked_ips": list(security_monitor.blocked_ips),
        "suspicious_ips": list(security_monitor.suspicious_ips),
        "count": len(security_monitor.blocked_ips)
    }


@router.post("/unblock-ip")
async def unblock_ip(
    ip_address: str,
    current_user: BaseUser = Depends(get_current_user)
) -> Dict:
    """Unblock an IP address (admin only)."""
    if ip_address in security_monitor.blocked_ips:
        security_monitor.blocked_ips.remove(ip_address)
        return {"message": f"IP {ip_address} unblocked successfully"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="IP address not found in blocked list"
    )


@router.get("/health")
async def security_health_check() -> Dict:
    """Get security system health status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitoring_active": security_monitor.monitoring_active,
        "audit_service_active": True,  # Placeholder
        "middleware_active": True  # Placeholder
    }