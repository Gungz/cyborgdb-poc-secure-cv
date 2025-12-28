"""Security monitoring and alerting service."""

import json
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

from app.services.audit_service import audit_service, SecurityEventType


class AlertLevel(str, Enum):
    """Alert severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SecurityAlert:
    """Security alert data structure."""
    alert_id: str
    timestamp: str
    alert_type: str
    level: AlertLevel
    message: str
    details: Dict
    source_events: List[str]
    resolved: bool = False


class SecurityMonitor:
    """Real-time security monitoring and alerting."""
    
    def __init__(self):
        self.alerts: List[SecurityAlert] = []
        self.event_history: deque = deque(maxlen=10000)  # Keep last 10k events
        self.ip_activity: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.user_activity: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.blocked_ips: Set[str] = set()
        self.suspicious_ips: Set[str] = set()
        
        # Thresholds for detection
        self.thresholds = {
            "failed_logins_per_ip": 10,  # per hour
            "failed_logins_per_user": 5,  # per hour
            "requests_per_minute": 100,
            "unique_endpoints_per_minute": 20,
            "error_rate_threshold": 0.5,  # 50% error rate
            "suspicious_user_agents": {
                "sqlmap", "nikto", "nmap", "masscan", "zap", "burp"
            }
        }
        
        # Start monitoring thread
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def record_event(self, event_type: str, ip_address: str, user_id: str = None, 
                    user_agent: str = "", endpoint: str = "", details: Dict = None):
        """Record a security event for monitoring."""
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "ip_address": ip_address,
            "user_id": user_id,
            "user_agent": user_agent,
            "endpoint": endpoint,
            "details": details or {}
        }
        
        self.event_history.append(event)
        self.ip_activity[ip_address].append(event)
        
        if user_id:
            self.user_activity[user_id].append(event)
        
        # Immediate threat detection
        self._check_immediate_threats(event)
    
    def _check_immediate_threats(self, event: Dict):
        """Check for immediate security threats."""
        ip_address = event["ip_address"]
        user_id = event["user_id"]
        event_type = event["event_type"]
        
        # Check for brute force attacks
        if event_type == "authentication_failure":
            self._check_brute_force_attack(ip_address, user_id)
        
        # Check for suspicious user agents
        if any(suspicious in event["user_agent"].lower() 
               for suspicious in self.thresholds["suspicious_user_agents"]):
            self._create_alert(
                alert_type="suspicious_user_agent",
                level=AlertLevel.HIGH,
                message=f"Suspicious user agent detected from {ip_address}",
                details={"user_agent": event["user_agent"], "ip": ip_address},
                source_events=[str(event)]
            )
        
        # Check for rapid requests from single IP
        self._check_request_rate(ip_address)
        
        # Check for endpoint scanning
        self._check_endpoint_scanning(ip_address)
    
    def _check_brute_force_attack(self, ip_address: str, user_id: str = None):
        """Check for brute force attacks."""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Check failed logins from IP
        ip_failures = [
            event for event in self.ip_activity[ip_address]
            if (event["timestamp"] > hour_ago and 
                event["event_type"] == "authentication_failure")
        ]
        
        if len(ip_failures) >= self.thresholds["failed_logins_per_ip"]:
            self.blocked_ips.add(ip_address)
            self._create_alert(
                alert_type="brute_force_attack_ip",
                level=AlertLevel.CRITICAL,
                message=f"Brute force attack detected from IP {ip_address}",
                details={
                    "ip": ip_address,
                    "failed_attempts": len(ip_failures),
                    "time_window": "1 hour"
                },
                source_events=[str(event) for event in ip_failures[-5:]]
            )
        
        # Check failed logins for user
        if user_id:
            user_failures = [
                event for event in self.user_activity[user_id]
                if (event["timestamp"] > hour_ago and 
                    event["event_type"] == "authentication_failure")
            ]
            
            if len(user_failures) >= self.thresholds["failed_logins_per_user"]:
                self._create_alert(
                    alert_type="brute_force_attack_user",
                    level=AlertLevel.HIGH,
                    message=f"Multiple failed login attempts for user {user_id}",
                    details={
                        "user_id": user_id,
                        "failed_attempts": len(user_failures),
                        "time_window": "1 hour"
                    },
                    source_events=[str(event) for event in user_failures]
                )
    
    def _check_request_rate(self, ip_address: str):
        """Check for excessive request rates."""
        current_time = time.time()
        minute_ago = current_time - 60
        
        recent_requests = [
            event for event in self.ip_activity[ip_address]
            if event["timestamp"] > minute_ago
        ]
        
        if len(recent_requests) >= self.thresholds["requests_per_minute"]:
            self.suspicious_ips.add(ip_address)
            self._create_alert(
                alert_type="high_request_rate",
                level=AlertLevel.MEDIUM,
                message=f"High request rate detected from IP {ip_address}",
                details={
                    "ip": ip_address,
                    "requests_per_minute": len(recent_requests)
                },
                source_events=[str(event) for event in recent_requests[-10:]]
            )
    
    def _check_endpoint_scanning(self, ip_address: str):
        """Check for endpoint scanning behavior."""
        current_time = time.time()
        minute_ago = current_time - 60
        
        recent_requests = [
            event for event in self.ip_activity[ip_address]
            if event["timestamp"] > minute_ago
        ]
        
        unique_endpoints = set(event["endpoint"] for event in recent_requests)
        
        if len(unique_endpoints) >= self.thresholds["unique_endpoints_per_minute"]:
            self.suspicious_ips.add(ip_address)
            self._create_alert(
                alert_type="endpoint_scanning",
                level=AlertLevel.HIGH,
                message=f"Endpoint scanning detected from IP {ip_address}",
                details={
                    "ip": ip_address,
                    "unique_endpoints": len(unique_endpoints),
                    "endpoints": list(unique_endpoints)[:10]  # Show first 10
                },
                source_events=[str(event) for event in recent_requests[-5:]]
            )
    
    def _create_alert(self, alert_type: str, level: AlertLevel, message: str, 
                     details: Dict, source_events: List[str]):
        """Create a new security alert."""
        alert = SecurityAlert(
            alert_id=f"alert_{int(time.time() * 1000)}",
            timestamp=datetime.now().isoformat(),
            alert_type=alert_type,
            level=level,
            message=message,
            details=details,
            source_events=source_events
        )
        
        self.alerts.append(alert)
        
        # Log the alert
        print(f"🚨 SECURITY ALERT [{level}]: {message}")
        
        # Send notification for high/critical alerts
        if level in [AlertLevel.HIGH, AlertLevel.CRITICAL]:
            self._send_alert_notification(alert)
    
    def _send_alert_notification(self, alert: SecurityAlert):
        """Send alert notification (placeholder for real implementation)."""
        # In a real implementation, this would send notifications via:
        # - Email
        # - Slack/Teams
        # - SMS
        # - PagerDuty
        # - SIEM systems
        
        notification_message = (
            f"SECURITY ALERT: {alert.message}\n"
            f"Level: {alert.level}\n"
            f"Time: {alert.timestamp}\n"
            f"Details: {json.dumps(alert.details, indent=2)}"
        )
        
        # For now, just log it prominently
        print(f"📧 ALERT NOTIFICATION: {notification_message}")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                self._periodic_analysis()
                time.sleep(60)  # Run every minute
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(60)
    
    def _periodic_analysis(self):
        """Perform periodic security analysis."""
        current_time = time.time()
        
        # Clean old data
        self._cleanup_old_data(current_time)
        
        # Analyze trends
        self._analyze_trends()
        
        # Check system health
        self._check_system_health()
    
    def _cleanup_old_data(self, current_time: float):
        """Clean up old monitoring data."""
        # Remove events older than 24 hours
        day_ago = current_time - 86400
        
        # Clean IP activity
        for ip in list(self.ip_activity.keys()):
            self.ip_activity[ip] = deque(
                [event for event in self.ip_activity[ip] if event["timestamp"] > day_ago],
                maxlen=1000
            )
            if not self.ip_activity[ip]:
                del self.ip_activity[ip]
        
        # Clean user activity
        for user_id in list(self.user_activity.keys()):
            self.user_activity[user_id] = deque(
                [event for event in self.user_activity[user_id] if event["timestamp"] > day_ago],
                maxlen=1000
            )
            if not self.user_activity[user_id]:
                del self.user_activity[user_id]
    
    def _analyze_trends(self):
        """Analyze security trends."""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Count recent events by type
        recent_events = [
            event for event in self.event_history
            if event["timestamp"] > hour_ago
        ]
        
        event_counts = defaultdict(int)
        for event in recent_events:
            event_counts[event["event_type"]] += 1
        
        # Check for unusual patterns
        if event_counts.get("authentication_failure", 0) > 50:
            self._create_alert(
                alert_type="high_authentication_failures",
                level=AlertLevel.MEDIUM,
                message="High number of authentication failures detected",
                details={"count": event_counts["authentication_failure"]},
                source_events=[]
            )
    
    def _check_system_health(self):
        """Check overall system security health."""
        # This would integrate with system metrics in a real implementation
        pass
    
    def get_security_dashboard(self) -> Dict:
        """Get security dashboard data."""
        current_time = time.time()
        hour_ago = current_time - 3600
        day_ago = current_time - 86400
        
        recent_events = [
            event for event in self.event_history
            if event["timestamp"] > hour_ago
        ]
        
        daily_events = [
            event for event in self.event_history
            if event["timestamp"] > day_ago
        ]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "alerts": {
                "total": len(self.alerts),
                "unresolved": len([a for a in self.alerts if not a.resolved]),
                "critical": len([a for a in self.alerts if a.level == AlertLevel.CRITICAL]),
                "high": len([a for a in self.alerts if a.level == AlertLevel.HIGH])
            },
            "activity": {
                "events_last_hour": len(recent_events),
                "events_last_day": len(daily_events),
                "unique_ips_last_hour": len(set(e["ip_address"] for e in recent_events)),
                "blocked_ips": len(self.blocked_ips),
                "suspicious_ips": len(self.suspicious_ips)
            },
            "top_event_types": dict(
                sorted(
                    defaultdict(int, {
                        event["event_type"]: sum(1 for e in recent_events if e["event_type"] == event["event_type"])
                        for event in recent_events
                    }).items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            )
        }
    
    def stop_monitoring(self):
        """Stop the monitoring service."""
        self.monitoring_active = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)


# Global monitoring service instance
security_monitor = SecurityMonitor()