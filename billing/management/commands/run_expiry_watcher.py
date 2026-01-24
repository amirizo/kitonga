"""
Management command to run the Access Expiry Watcher

This command runs the real-time access expiration watcher that monitors
users and disconnects them immediately when their access expires.

Usage:
    python manage.py run_expiry_watcher

    # For production (run as a service):
    python manage.py run_expiry_watcher --interval 15  # Check every 15 seconds
    
Options:
    --interval: Check interval in seconds (default: 30)
    --once: Run once and exit (for cron-like usage)
"""

import signal
import sys
import time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run the real-time access expiry watcher to auto-disconnect expired users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Check interval in seconds (default: 30)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit (useful for cron)'
        )
    
    def handle(self, *args, **options):
        from billing.expiry_watcher import AccessExpiryWatcher
        
        interval = options['interval']
        run_once = options['once']
        
        self.stdout.write(self.style.SUCCESS(
            f'\n🔍 Kitonga Access Expiry Watcher\n'
            f'================================\n'
            f'Check interval: {interval} seconds\n'
            f'Mode: {"Single run" if run_once else "Continuous monitoring"}\n'
        ))
        
        watcher = AccessExpiryWatcher()
        watcher._check_interval = interval
        
        if run_once:
            # Run a single check and exit
            self.stdout.write('Running single expiry check...\n')
            watcher._check_and_disconnect_expired()
            self.stdout.write(self.style.SUCCESS('✅ Check complete\n'))
            return
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write(self.style.WARNING('\n\n⚠️  Shutdown signal received, stopping watcher...\n'))
            watcher.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the watcher
        self.stdout.write(self.style.SUCCESS('🚀 Starting expiry watcher... Press Ctrl+C to stop\n\n'))
        
        try:
            watcher._running = True
            while watcher._running:
                watcher._check_and_disconnect_expired()
                self.stdout.write(f'💤 Sleeping for {interval} seconds...\n')
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n\n⚠️  Keyboard interrupt, stopping...\n'))
        finally:
            watcher._running = False
            self.stdout.write(self.style.SUCCESS('✅ Watcher stopped\n'))
