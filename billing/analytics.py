"""
Analytics and Reporting Module for Kitonga Tenant Portal
Provides comprehensive analytics for tenant dashboards
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncDate, TruncHour, TruncWeek, TruncMonth, ExtractHour

from .models import (
    Tenant, User, Payment, Voucher, Device, AccessLog, 
    Router, Bundle, SMSLog
)

logger = logging.getLogger(__name__)


class TenantAnalytics:
    """
    Comprehensive analytics for tenant dashboards
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get complete dashboard summary for tenant
        """
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        return {
            'overview': self._get_overview_stats(),
            'today': self._get_period_stats(today, today),
            'this_week': self._get_period_stats(week_ago.date(), today),
            'this_month': self._get_period_stats(month_ago.date(), today),
            'active_users': self._get_active_users_summary(),
            'revenue_trend': self._get_revenue_trend(days=30),
            'top_bundles': self._get_top_bundles(),
            'device_breakdown': self._get_device_breakdown(),
            'hourly_usage': self._get_hourly_usage_pattern(),
            'router_status': self._get_router_status(),
        }
    
    def _get_overview_stats(self) -> Dict[str, Any]:
        """Get overall tenant statistics"""
        return {
            'total_users': User.objects.filter(tenant=self.tenant).count(),
            'active_users': User.objects.filter(tenant=self.tenant, is_active=True).count(),
            'total_devices': Device.objects.filter(tenant=self.tenant).count(),
            'active_devices': Device.objects.filter(tenant=self.tenant, is_active=True).count(),
            'total_routers': Router.objects.filter(tenant=self.tenant, is_active=True).count(),
            'online_routers': Router.objects.filter(tenant=self.tenant, status='online').count(),
            'total_payments': Payment.objects.filter(tenant=self.tenant, status='completed').count(),
            'total_revenue': float(
                Payment.objects.filter(
                    tenant=self.tenant, status='completed'
                ).aggregate(total=Sum('amount'))['total'] or 0
            ),
            'total_vouchers_generated': Voucher.objects.filter(tenant=self.tenant).count(),
            'total_vouchers_used': Voucher.objects.filter(tenant=self.tenant, is_used=True).count(),
        }
    
    def _get_period_stats(self, start_date, end_date) -> Dict[str, Any]:
        """Get statistics for a specific date range"""
        payments = Payment.objects.filter(
            tenant=self.tenant,
            status='completed',
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )
        
        new_users = User.objects.filter(
            tenant=self.tenant,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        vouchers_used = Voucher.objects.filter(
            tenant=self.tenant,
            is_used=True,
            used_at__date__gte=start_date,
            used_at__date__lte=end_date
        )
        
        return {
            'payments_count': payments.count(),
            'revenue': float(payments.aggregate(total=Sum('amount'))['total'] or 0),
            'average_payment': float(payments.aggregate(avg=Avg('amount'))['avg'] or 0),
            'new_users': new_users.count(),
            'vouchers_redeemed': vouchers_used.count(),
        }
    
    def _get_active_users_summary(self) -> Dict[str, Any]:
        """Get breakdown of active users"""
        now = timezone.now()
        
        active_users = User.objects.filter(
            tenant=self.tenant,
            is_active=True,
            paid_until__gt=now
        )
        
        # Time until expiry breakdown
        expiring_soon = active_users.filter(paid_until__lte=now + timedelta(hours=2))
        expiring_today = active_users.filter(
            paid_until__gt=now + timedelta(hours=2),
            paid_until__lte=now + timedelta(hours=24)
        )
        expiring_this_week = active_users.filter(
            paid_until__gt=now + timedelta(hours=24),
            paid_until__lte=now + timedelta(days=7)
        )
        
        return {
            'total_active': active_users.count(),
            'expiring_soon': expiring_soon.count(),  # Within 2 hours
            'expiring_today': expiring_today.count(),  # 2-24 hours
            'expiring_this_week': expiring_this_week.count(),  # 1-7 days
        }
    
    def _get_revenue_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily revenue trend for the past N days"""
        start_date = timezone.now() - timedelta(days=days)
        
        daily_revenue = Payment.objects.filter(
            tenant=self.tenant,
            status='completed',
            completed_at__gte=start_date
        ).annotate(
            date=TruncDate('completed_at')
        ).values('date').annotate(
            revenue=Sum('amount'),
            count=Count('id')
        ).order_by('date')
        
        return [
            {
                'date': item['date'].isoformat() if item['date'] else None,
                'revenue': float(item['revenue'] or 0),
                'transactions': item['count']
            }
            for item in daily_revenue
        ]
    
    def _get_top_bundles(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top selling bundles"""
        top_bundles = Payment.objects.filter(
            tenant=self.tenant,
            status='completed',
            bundle__isnull=False
        ).values(
            'bundle__id', 'bundle__name', 'bundle__price', 'bundle__duration_hours'
        ).annotate(
            sales_count=Count('id'),
            total_revenue=Sum('amount')
        ).order_by('-sales_count')[:limit]
        
        return [
            {
                'bundle_id': item['bundle__id'],
                'name': item['bundle__name'],
                'price': float(item['bundle__price'] or 0),
                'duration_hours': item['bundle__duration_hours'],
                'sales_count': item['sales_count'],
                'total_revenue': float(item['total_revenue'] or 0)
            }
            for item in top_bundles
        ]
    
    def _get_device_breakdown(self) -> Dict[str, int]:
        """Get breakdown of devices by type"""
        devices = Device.objects.filter(tenant=self.tenant)
        
        breakdown = devices.values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        result = {}
        for item in breakdown:
            device_type = item['device_type'] or 'unknown'
            result[device_type] = item['count']
        
        return result
    
    def _get_hourly_usage_pattern(self) -> List[Dict[str, Any]]:
        """Get usage pattern by hour of day (based on payments)"""
        # Analyze last 30 days
        start_date = timezone.now() - timedelta(days=30)
        
        hourly_pattern = Payment.objects.filter(
            tenant=self.tenant,
            status='completed',
            completed_at__gte=start_date
        ).annotate(
            hour_of_day=ExtractHour('completed_at')
        ).values('hour_of_day').annotate(
            count=Count('id'),
            revenue=Sum('amount')
        ).order_by('hour_of_day')
        
        # Fill in missing hours
        result = []
        hour_data = {item['hour_of_day']: item for item in hourly_pattern}
        
        for hour in range(24):
            data = hour_data.get(hour, {})
            result.append({
                'hour': hour,
                'transactions': data.get('count', 0),
                'revenue': float(data.get('revenue', 0))
            })
        
        return result
    
    def _get_router_status(self) -> List[Dict[str, Any]]:
        """Get status summary of all routers"""
        routers = Router.objects.filter(tenant=self.tenant, is_active=True)
        
        return [
            {
                'id': router.id,
                'name': router.name,
                'host': router.host,
                'status': router.status,
                'last_seen': router.last_seen.isoformat() if router.last_seen else None,
                'location': router.location.name if router.location else None,
            }
            for router in routers
        ]
    
    def get_revenue_report(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = 'day'
    ) -> Dict[str, Any]:
        """
        Generate detailed revenue report
        
        Args:
            start_date: Report start date (default: 30 days ago)
            end_date: Report end date (default: now)
            group_by: 'hour', 'day', 'week', 'month'
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Base queryset
        payments = Payment.objects.filter(
            tenant=self.tenant,
            status='completed',
            completed_at__gte=start_date,
            completed_at__lte=end_date
        )
        
        # Group by period
        trunc_func = {
            'hour': TruncHour,
            'day': TruncDate,
            'week': TruncWeek,
            'month': TruncMonth,
        }.get(group_by, TruncDate)
        
        grouped = payments.annotate(
            period=trunc_func('completed_at')
        ).values('period').annotate(
            revenue=Sum('amount'),
            count=Count('id'),
            avg_amount=Avg('amount')
        ).order_by('period')
        
        # Calculate totals
        totals = payments.aggregate(
            total_revenue=Sum('amount'),
            total_count=Count('id'),
            avg_amount=Avg('amount')
        )
        
        # Payment channel breakdown
        channel_breakdown = payments.values('payment_channel').annotate(
            count=Count('id'),
            revenue=Sum('amount')
        ).order_by('-revenue')
        
        # Bundle breakdown
        bundle_breakdown = payments.filter(bundle__isnull=False).values(
            'bundle__name'
        ).annotate(
            count=Count('id'),
            revenue=Sum('amount')
        ).order_by('-revenue')
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'group_by': group_by,
            },
            'summary': {
                'total_revenue': float(totals['total_revenue'] or 0),
                'total_transactions': totals['total_count'] or 0,
                'average_transaction': float(totals['avg_amount'] or 0),
            },
            'trend': [
                {
                    'period': item['period'].isoformat() if item['period'] else None,
                    'revenue': float(item['revenue'] or 0),
                    'transactions': item['count'],
                    'average': float(item['avg_amount'] or 0)
                }
                for item in grouped
            ],
            'by_channel': [
                {
                    'channel': item['payment_channel'] or 'unknown',
                    'transactions': item['count'],
                    'revenue': float(item['revenue'] or 0)
                }
                for item in channel_breakdown
            ],
            'by_bundle': [
                {
                    'bundle': item['bundle__name'],
                    'sales': item['count'],
                    'revenue': float(item['revenue'] or 0)
                }
                for item in bundle_breakdown
            ],
        }
    
    def get_user_analytics(self) -> Dict[str, Any]:
        """Get detailed user analytics"""
        now = timezone.now()
        
        # User growth trend (last 30 days)
        growth_start = now - timedelta(days=30)
        daily_growth = User.objects.filter(
            tenant=self.tenant,
            created_at__gte=growth_start
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # User retention (users who paid multiple times)
        repeat_users = User.objects.filter(
            tenant=self.tenant,
            total_payments__gt=1
        ).count()
        
        total_paying_users = User.objects.filter(
            tenant=self.tenant,
            total_payments__gt=0
        ).count()
        
        # Payment frequency distribution
        payment_distribution = User.objects.filter(
            tenant=self.tenant
        ).values('total_payments').annotate(
            count=Count('id')
        ).order_by('total_payments')
        
        # Top spending users
        top_spenders = User.objects.filter(
            tenant=self.tenant,
            total_amount_paid__gt=0
        ).order_by('-total_amount_paid')[:10]
        
        return {
            'growth_trend': [
                {
                    'date': item['date'].isoformat() if item['date'] else None,
                    'new_users': item['count']
                }
                for item in daily_growth
            ],
            'retention': {
                'total_users': User.objects.filter(tenant=self.tenant).count(),
                'paying_users': total_paying_users,
                'repeat_users': repeat_users,
                'retention_rate': (repeat_users / total_paying_users * 100) if total_paying_users > 0 else 0,
            },
            'payment_distribution': [
                {
                    'payments': item['total_payments'],
                    'user_count': item['count']
                }
                for item in payment_distribution[:20]  # Limit to first 20
            ],
            'top_spenders': [
                {
                    'phone': user.phone_number[-4:].rjust(len(user.phone_number), '*'),  # Masked
                    'total_spent': float(user.total_amount_paid),
                    'total_payments': user.total_payments,
                    'is_active': user.is_active,
                }
                for user in top_spenders
            ],
        }
    
    def get_voucher_analytics(self) -> Dict[str, Any]:
        """Get voucher usage analytics"""
        now = timezone.now()
        month_ago = now - timedelta(days=30)
        
        vouchers = Voucher.objects.filter(tenant=self.tenant)
        
        # Overall stats
        total = vouchers.count()
        used = vouchers.filter(is_used=True).count()
        
        # By duration
        by_duration = vouchers.values('duration_hours').annotate(
            total=Count('id'),
            used=Count('id', filter=Q(is_used=True))
        ).order_by('duration_hours')
        
        # Recent usage trend
        recent_redemptions = vouchers.filter(
            is_used=True,
            used_at__gte=month_ago
        ).annotate(
            date=TruncDate('used_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # By batch
        by_batch = vouchers.exclude(batch_id='').values('batch_id').annotate(
            total=Count('id'),
            used=Count('id', filter=Q(is_used=True))
        ).order_by('-total')[:10]
        
        return {
            'summary': {
                'total_generated': total,
                'total_used': used,
                'total_available': total - used,
                'usage_rate': (used / total * 100) if total > 0 else 0,
            },
            'by_duration': [
                {
                    'duration_hours': item['duration_hours'],
                    'total': item['total'],
                    'used': item['used'],
                    'available': item['total'] - item['used']
                }
                for item in by_duration
            ],
            'recent_trend': [
                {
                    'date': item['date'].isoformat() if item['date'] else None,
                    'redemptions': item['count']
                }
                for item in recent_redemptions
            ],
            'top_batches': [
                {
                    'batch_id': item['batch_id'],
                    'total': item['total'],
                    'used': item['used'],
                    'usage_rate': (item['used'] / item['total'] * 100) if item['total'] > 0 else 0
                }
                for item in by_batch
            ],
        }
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time statistics for live dashboard updates"""
        now = timezone.now()
        last_5_min = now - timedelta(minutes=5)
        last_hour = now - timedelta(hours=1)
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            tenant=self.tenant,
            status='completed',
            completed_at__gte=last_hour
        ).order_by('-completed_at')[:10]
        
        # Currently active users
        active_users = User.objects.filter(
            tenant=self.tenant,
            is_active=True,
            paid_until__gt=now
        ).count()
        
        # Recent activity count
        recent_activity = AccessLog.objects.filter(
            tenant=self.tenant,
            timestamp__gte=last_5_min
        ).count()
        
        return {
            'timestamp': now.isoformat(),
            'active_users': active_users,
            'recent_activity_5min': recent_activity,
            'recent_payments': [
                {
                    'id': p.id,
                    'amount': float(p.amount),
                    'phone': p.phone_number[-4:].rjust(len(p.phone_number), '*'),
                    'bundle': p.bundle.name if p.bundle else None,
                    'time': p.completed_at.isoformat() if p.completed_at else None,
                }
                for p in recent_payments
            ],
        }


class ComparisonAnalytics:
    """
    Analytics for comparing periods (week over week, month over month)
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
    
    def compare_periods(
        self, 
        current_start: datetime,
        current_end: datetime,
        previous_start: datetime,
        previous_end: datetime
    ) -> Dict[str, Any]:
        """Compare two time periods"""
        
        def get_period_data(start, end):
            payments = Payment.objects.filter(
                tenant=self.tenant,
                status='completed',
                completed_at__gte=start,
                completed_at__lte=end
            )
            
            return {
                'revenue': float(payments.aggregate(total=Sum('amount'))['total'] or 0),
                'transactions': payments.count(),
                'new_users': User.objects.filter(
                    tenant=self.tenant,
                    created_at__gte=start,
                    created_at__lte=end
                ).count(),
                'vouchers_used': Voucher.objects.filter(
                    tenant=self.tenant,
                    is_used=True,
                    used_at__gte=start,
                    used_at__lte=end
                ).count(),
            }
        
        current = get_period_data(current_start, current_end)
        previous = get_period_data(previous_start, previous_end)
        
        def calc_change(current_val, previous_val):
            if previous_val == 0:
                return 100 if current_val > 0 else 0
            return ((current_val - previous_val) / previous_val) * 100
        
        return {
            'current_period': {
                'start': current_start.isoformat(),
                'end': current_end.isoformat(),
                **current
            },
            'previous_period': {
                'start': previous_start.isoformat(),
                'end': previous_end.isoformat(),
                **previous
            },
            'changes': {
                'revenue_change': calc_change(current['revenue'], previous['revenue']),
                'transactions_change': calc_change(current['transactions'], previous['transactions']),
                'new_users_change': calc_change(current['new_users'], previous['new_users']),
                'vouchers_change': calc_change(current['vouchers_used'], previous['vouchers_used']),
            }
        }
    
    def week_over_week(self) -> Dict[str, Any]:
        """Compare this week vs last week"""
        now = timezone.now()
        this_week_start = now - timedelta(days=7)
        last_week_start = this_week_start - timedelta(days=7)
        
        return self.compare_periods(
            current_start=this_week_start,
            current_end=now,
            previous_start=last_week_start,
            previous_end=this_week_start
        )
    
    def month_over_month(self) -> Dict[str, Any]:
        """Compare this month vs last month"""
        now = timezone.now()
        this_month_start = now - timedelta(days=30)
        last_month_start = this_month_start - timedelta(days=30)
        
        return self.compare_periods(
            current_start=this_month_start,
            current_end=now,
            previous_start=last_month_start,
            previous_end=this_month_start
        )


class ExportManager:
    """
    Handle data exports for tenant reporting
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
    
    def export_payments_csv(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> str:
        """Export payments to CSV format"""
        import csv
        import io
        
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        payments = Payment.objects.filter(
            tenant=self.tenant,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).select_related('bundle', 'user').order_by('-created_at')
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Transaction ID', 'Date', 'Phone Number', 'Amount', 'Bundle',
            'Channel', 'Status', 'Completed At'
        ])
        
        # Data rows
        for payment in payments:
            writer.writerow([
                payment.transaction_id,
                payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                payment.phone_number,
                payment.amount,
                payment.bundle.name if payment.bundle else 'N/A',
                payment.payment_channel or 'N/A',
                payment.status,
                payment.completed_at.strftime('%Y-%m-%d %H:%M:%S') if payment.completed_at else 'N/A'
            ])
        
        return output.getvalue()
    
    def export_users_csv(self) -> str:
        """Export users to CSV format"""
        import csv
        import io
        
        users = User.objects.filter(
            tenant=self.tenant
        ).order_by('-created_at')
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Phone Number', 'Name', 'Email', 'Created At', 'Is Active',
            'Paid Until', 'Total Payments', 'Total Amount Paid', 'Max Devices'
        ])
        
        # Data rows
        for user in users:
            writer.writerow([
                user.phone_number,
                user.name or 'N/A',
                user.email or 'N/A',
                user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if user.is_active else 'No',
                user.paid_until.strftime('%Y-%m-%d %H:%M:%S') if user.paid_until else 'N/A',
                user.total_payments,
                user.total_amount_paid,
                user.max_devices
            ])
        
        return output.getvalue()
    
    def export_vouchers_csv(self, batch_id: Optional[str] = None) -> str:
        """Export vouchers to CSV format"""
        import csv
        import io
        
        vouchers = Voucher.objects.filter(tenant=self.tenant)
        
        if batch_id:
            vouchers = vouchers.filter(batch_id=batch_id)
        
        vouchers = vouchers.select_related('used_by').order_by('-created_at')
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Code', 'Duration (Hours)', 'Batch ID', 'Is Used', 
            'Created At', 'Used At', 'Used By'
        ])
        
        # Data rows
        for voucher in vouchers:
            writer.writerow([
                voucher.code,
                voucher.duration_hours,
                voucher.batch_id or 'N/A',
                'Yes' if voucher.is_used else 'No',
                voucher.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                voucher.used_at.strftime('%Y-%m-%d %H:%M:%S') if voucher.used_at else 'N/A',
                voucher.used_by.phone_number if voucher.used_by else 'N/A'
            ])
        
        return output.getvalue()
