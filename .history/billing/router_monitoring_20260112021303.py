"""
Router Monitoring Service

Provides remote monitoring capabilities for tenant routers including:
- System resource monitoring (CPU, memory, disk)
- Bandwidth usage tracking
- Active user counts
- Interface status
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Max, Sum

from .models import Router, RouterMonitoringSnapshot, RouterBandwidthLog
from .mikrotik import get_tenant_mikrotik_api, safe_close

logger = logging.getLogger(__name__)


class RouterMonitor:
    """
    Monitor router health and collect metrics
    """

    def __init__(self, router):
        self.router = router

    def collect_metrics(self):
        """
        Collect current metrics from router and save snapshot
        """
        api = None
        snapshot_data = {
            "router": self.router,
            "is_reachable": False,
            "error_message": "",
        }

        try:
            api = get_tenant_mikrotik_api(self.router, retries=1, timeout=15)
            if not api:
                snapshot_data["error_message"] = "Could not connect to router"
                return self._save_snapshot(snapshot_data)

            snapshot_data["is_reachable"] = True

            # Get system resources
            resources = self._get_system_resources(api)
            snapshot_data.update(resources)

            # Get hotspot users
            snapshot_data["active_hotspot_users"] = self._get_hotspot_user_count(api)

            # Get interface stats
            interface_stats = self._get_interface_stats(api)
            snapshot_data.update(interface_stats)

            # Update router status
            self.router.status = "online"
            self.router.last_seen = timezone.now()
            self.router.last_error = ""
            self.router.save(update_fields=["status", "last_seen", "last_error"])

        except Exception as e:
            logger.error(f"Error collecting metrics for {self.router.name}: {e}")
            snapshot_data["error_message"] = str(e)

            # Update router status
            self.router.status = "error"
            self.router.last_error = str(e)
            self.router.save(update_fields=["status", "last_error"])

        finally:
            if api:
                safe_close(api)

        return self._save_snapshot(snapshot_data)

    def _get_system_resources(self, api):
        """Get CPU, memory, disk, uptime"""
        data = {
            "cpu_load": 0,
            "memory_used": 0,
            "memory_total": 0,
            "disk_used": 0,
            "disk_total": 0,
            "uptime": 0,
        }

        try:
            resources = api.get_resource("/system/resource")
            if resources:
                res = resources[0]
                data["cpu_load"] = int(res.get("cpu-load", 0))
                data["memory_total"] = int(res.get("total-memory", 0))
                data["memory_used"] = data["memory_total"] - int(
                    res.get("free-memory", 0)
                )
                data["disk_total"] = int(res.get("total-hdd-space", 0))
                data["disk_used"] = data["disk_total"] - int(
                    res.get("free-hdd-space", 0)
                )
                # Parse uptime (format: 1w2d3h4m5s)
                data["uptime"] = self._parse_uptime(res.get("uptime", "0s"))

                # Update router info
                self.router.router_version = res.get("version", "")
                self.router.router_model = res.get("board-name", "")
                self.router.save(update_fields=["router_version", "router_model"])

        except Exception as e:
            logger.error(f"Error getting resources: {e}")

        return data

    def _get_hotspot_user_count(self, api):
        """Get count of active hotspot users"""
        try:
            users = api.get_resource("/ip/hotspot/active")
            return len(users) if users else 0
        except Exception as e:
            logger.error(f"Error getting hotspot users: {e}")
            return 0

    def _get_interface_stats(self, api):
        """Get interface counts and bandwidth"""
        data = {
            "total_interfaces": 0,
            "interfaces_up": 0,
            "rx_bytes": 0,
            "tx_bytes": 0,
        }

        try:
            interfaces = api.get_resource("/interface")
            if interfaces:
                data["total_interfaces"] = len(interfaces)
                for iface in interfaces:
                    if iface.get("running") == "true":
                        data["interfaces_up"] += 1
                    data["rx_bytes"] += int(iface.get("rx-byte", 0))
                    data["tx_bytes"] += int(iface.get("tx-byte", 0))
        except Exception as e:
            logger.error(f"Error getting interfaces: {e}")

        return data

    def _parse_uptime(self, uptime_str):
        """Parse MikroTik uptime format to seconds"""
        total_seconds = 0
        try:
            import re

            weeks = re.search(r"(\d+)w", uptime_str)
            days = re.search(r"(\d+)d", uptime_str)
            hours = re.search(r"(\d+)h", uptime_str)
            minutes = re.search(r"(\d+)m", uptime_str)
            seconds = re.search(r"(\d+)s", uptime_str)

            if weeks:
                total_seconds += int(weeks.group(1)) * 604800
            if days:
                total_seconds += int(days.group(1)) * 86400
            if hours:
                total_seconds += int(hours.group(1)) * 3600
            if minutes:
                total_seconds += int(minutes.group(1)) * 60
            if seconds:
                total_seconds += int(seconds.group(1))
        except Exception:
            pass
        return total_seconds

    def _save_snapshot(self, data):
        """Save monitoring snapshot"""
        try:
            snapshot = RouterMonitoringSnapshot.objects.create(**data)
            return snapshot
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
            return None

    def get_current_status(self):
        """Get current router status without saving"""
        api = None
        status = {
            "router_id": self.router.id,
            "router_name": self.router.name,
            "host": self.router.host,
            "is_reachable": False,
            "status": self.router.status,
            "last_seen": self.router.last_seen.isoformat() if self.router.last_seen else None,
            "metrics": {},
        }

        try:
            api = get_tenant_mikrotik_api(self.router, retries=1, timeout=10)
            if api:
                status["is_reachable"] = True
                status["status"] = "online"

                # Get resources
                resources = api.get_resource("/system/resource")
                if resources:
                    res = resources[0]
                    memory_total = int(res.get("total-memory", 0))
                    memory_used = memory_total - int(res.get("free-memory", 0))
                    disk_total = int(res.get("total-hdd-space", 0))
                    disk_used = disk_total - int(res.get("free-hdd-space", 0))

                    status["metrics"] = {
                        "cpu_load": int(res.get("cpu-load", 0)),
                        "memory_used_mb": round(memory_used / (1024 * 1024), 1),
                        "memory_total_mb": round(memory_total / (1024 * 1024), 1),
                        "memory_percent": round(
                            (memory_used / memory_total * 100) if memory_total else 0, 1
                        ),
                        "disk_used_mb": round(disk_used / (1024 * 1024), 1),
                        "disk_total_mb": round(disk_total / (1024 * 1024), 1),
                        "disk_percent": round(
                            (disk_used / disk_total * 100) if disk_total else 0, 1
                        ),
                        "uptime": res.get("uptime", "0s"),
                        "version": res.get("version", ""),
                        "board": res.get("board-name", ""),
                    }

                # Get active users
                users = api.get_resource("/ip/hotspot/active")
                status["metrics"]["active_users"] = len(users) if users else 0

                # Get interfaces
                interfaces = api.get_resource("/interface")
                if interfaces:
                    up_count = sum(1 for i in interfaces if i.get("running") == "true")
                    status["metrics"]["interfaces"] = {
                        "total": len(interfaces),
                        "up": up_count,
                    }

        except Exception as e:
            status["error"] = str(e)
        finally:
            if api:
                safe_close(api)

        return status


class BandwidthReporter:
    """
    Generate bandwidth usage reports
    """

    def __init__(self, router):
        self.router = router

    def get_hourly_report(self, start_date, end_date):
        """Get hourly bandwidth data for a date range"""
        logs = RouterBandwidthLog.objects.filter(
            router=self.router,
            hour_start__gte=start_date,
            hour_start__lt=end_date,
        ).order_by("hour_start")

        return [
            {
                "hour": log.hour_start.isoformat(),
                "rx_mb": log.rx_mb,
                "tx_mb": log.tx_mb,
                "total_mb": log.rx_mb + log.tx_mb,
                "peak_users": log.peak_users,
                "avg_users": round(log.avg_users, 1),
            }
            for log in logs
        ]

    def get_daily_report(self, start_date, end_date):
        """Get daily aggregated bandwidth data"""
        from django.db.models.functions import TruncDate

        daily_data = (
            RouterBandwidthLog.objects.filter(
                router=self.router,
                hour_start__gte=start_date,
                hour_start__lt=end_date,
            )
            .annotate(date=TruncDate("hour_start"))
            .values("date")
            .annotate(
                total_rx=Sum("rx_bytes"),
                total_tx=Sum("tx_bytes"),
                peak_users=Max("peak_users"),
                avg_users=Avg("avg_users"),
            )
            .order_by("date")
        )

        return [
            {
                "date": item["date"].isoformat(),
                "rx_gb": round(item["total_rx"] / (1024 * 1024 * 1024), 2),
                "tx_gb": round(item["total_tx"] / (1024 * 1024 * 1024), 2),
                "total_gb": round(
                    (item["total_rx"] + item["total_tx"]) / (1024 * 1024 * 1024), 2
                ),
                "peak_users": item["peak_users"],
                "avg_users": round(item["avg_users"] or 0, 1),
            }
            for item in daily_data
        ]

    def get_summary(self, days=30):
        """Get summary stats for the last N days"""
        start_date = timezone.now() - timedelta(days=days)

        stats = RouterBandwidthLog.objects.filter(
            router=self.router,
            hour_start__gte=start_date,
        ).aggregate(
            total_rx=Sum("rx_bytes"),
            total_tx=Sum("tx_bytes"),
            peak_users=Max("peak_users"),
            avg_users=Avg("avg_users"),
        )

        total_rx = stats["total_rx"] or 0
        total_tx = stats["total_tx"] or 0

        return {
            "period_days": days,
            "total_rx_gb": round(total_rx / (1024 * 1024 * 1024), 2),
            "total_tx_gb": round(total_tx / (1024 * 1024 * 1024), 2),
            "total_gb": round((total_rx + total_tx) / (1024 * 1024 * 1024), 2),
            "daily_avg_gb": round(
                (total_rx + total_tx) / (1024 * 1024 * 1024) / days, 2
            ),
            "peak_concurrent_users": stats["peak_users"] or 0,
            "avg_concurrent_users": round(stats["avg_users"] or 0, 1),
        }

    def calculate_bandwidth_delta(self):
        """
        Calculate bandwidth used since last snapshot
        Returns delta rx and tx bytes
        """
        snapshots = RouterMonitoringSnapshot.objects.filter(
            router=self.router, is_reachable=True
        ).order_by("-created_at")[:2]

        if len(snapshots) < 2:
            return None

        latest = snapshots[0]
        previous = snapshots[1]

        # Handle counter rollover (router reboot)
        rx_delta = latest.rx_bytes - previous.rx_bytes
        tx_delta = latest.tx_bytes - previous.tx_bytes

        if rx_delta < 0:
            rx_delta = latest.rx_bytes  # Counter was reset
        if tx_delta < 0:
            tx_delta = latest.tx_bytes

        time_delta = (latest.created_at - previous.created_at).total_seconds()

        return {
            "rx_bytes": rx_delta,
            "tx_bytes": tx_delta,
            "duration_seconds": time_delta,
            "rx_rate_bps": round(rx_delta * 8 / time_delta) if time_delta > 0 else 0,
            "tx_rate_bps": round(tx_delta * 8 / time_delta) if time_delta > 0 else 0,
        }


def collect_all_router_metrics(tenant):
    """
    Collect metrics from all active routers for a tenant
    """
    results = []
    routers = Router.objects.filter(tenant=tenant, is_active=True)

    for router in routers:
        monitor = RouterMonitor(router)
        snapshot = monitor.collect_metrics()
        results.append(
            {
                "router_id": router.id,
                "router_name": router.name,
                "success": snapshot is not None and snapshot.is_reachable,
                "error": snapshot.error_message if snapshot else "Failed to save snapshot",
            }
        )

    return results


def aggregate_hourly_bandwidth(router):
    """
    Aggregate recent snapshots into hourly bandwidth log
    Should be run hourly
    """
    now = timezone.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    hour_end = hour_start + timedelta(hours=1)

    # Get snapshots for this hour
    snapshots = RouterMonitoringSnapshot.objects.filter(
        router=router,
        created_at__gte=hour_start,
        created_at__lt=hour_end,
        is_reachable=True,
    )

    if not snapshots.exists():
        return None

    # Calculate aggregates
    user_counts = [s.active_hotspot_users for s in snapshots]

    # Get bandwidth delta (difference between first and last snapshot of the hour)
    first = snapshots.order_by("created_at").first()
    last = snapshots.order_by("-created_at").first()

    rx_delta = max(0, last.rx_bytes - first.rx_bytes)
    tx_delta = max(0, last.tx_bytes - first.tx_bytes)

    duration = (last.created_at - first.created_at).total_seconds()

    # Create or update hourly log
    log, created = RouterBandwidthLog.objects.update_or_create(
        router=router,
        hour_start=hour_start,
        defaults={
            "rx_bytes": rx_delta,
            "tx_bytes": tx_delta,
            "peak_users": max(user_counts) if user_counts else 0,
            "avg_users": sum(user_counts) / len(user_counts) if user_counts else 0,
            "avg_rx_rate": round(rx_delta / duration) if duration > 0 else 0,
            "avg_tx_rate": round(tx_delta / duration) if duration > 0 else 0,
        },
    )

    return log
