"""Cron-based task scheduler for AI News Agent."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Coroutine

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from ..collectors.rss_with_storage import RSSCollectorWithStorage
from ..config import settings
from ..digest import DigestGenerator


class ScheduledTask:
    """Represents a scheduled task."""
    
    def __init__(
        self,
        name: str,
        cron_expression: str,
        task_func: Callable[..., Coroutine[Any, Any, Any]],
        args: tuple = (),
        kwargs: dict | None = None,
    ):
        """Initialize scheduled task.
        
        Args:
            name: Task name for identification
            cron_expression: Cron expression for scheduling
            task_func: Async function to execute
            args: Positional arguments for task function
            kwargs: Keyword arguments for task function
        """
        self.name = name
        self.cron_expression = cron_expression
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs or {}
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self.run_count: int = 0
        self.error_count: int = 0
        self.last_error: str | None = None


class Scheduler:
    """Main scheduler for automated tasks."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.tasks: dict[str, ScheduledTask] = {}
        self.collector = RSSCollectorWithStorage()
        self.digest_generator = DigestGenerator()
        
    def add_task(self, task: ScheduledTask) -> None:
        """Add a task to the scheduler.
        
        Args:
            task: Task to schedule
        """
        if task.name in self.tasks:
            logger.warning(f"Task {task.name} already exists, replacing")
            self.remove_task(task.name)
        
        # Parse cron expression
        try:
            trigger = CronTrigger.from_crontab(task.cron_expression)
        except Exception as e:
            logger.error(f"Invalid cron expression '{task.cron_expression}': {e}")
            raise ValueError(f"Invalid cron expression: {e}")
        
        # Add job to scheduler
        job = self.scheduler.add_job(
            self._run_task,
            trigger=trigger,
            args=[task],
            id=task.name,
            name=task.name,
            replace_existing=True,
        )
        
        # Update next run time (may be None if scheduler not started)
        if hasattr(job, 'next_run_time'):
            task.next_run = job.next_run_time
        self.tasks[task.name] = task
        
        logger.info(
            f"Scheduled task '{task.name}' with cron '{task.cron_expression}', "
            f"next run: {task.next_run}"
        )
    
    def remove_task(self, task_name: str) -> None:
        """Remove a task from the scheduler.
        
        Args:
            task_name: Name of task to remove
        """
        if task_name in self.tasks:
            self.scheduler.remove_job(task_name)
            del self.tasks[task_name]
            logger.info(f"Removed task '{task_name}'")
    
    async def _run_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task.
        
        Args:
            task: Task to execute
        """
        logger.info(f"Running scheduled task: {task.name}")
        start_time = datetime.now(UTC)
        
        try:
            # Execute task function
            result = await task.task_func(*task.args, **task.kwargs)
            
            # Update task stats
            task.last_run = start_time
            task.run_count += 1
            task.last_error = None
            
            # Get next run time
            job = self.scheduler.get_job(task.name)
            if job and hasattr(job, 'next_run_time'):
                task.next_run = job.next_run_time
            
            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info(
                f"Task '{task.name}' completed successfully in {duration:.1f}s"
            )
            
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            logger.error(f"Task '{task.name}' failed: {e}", exc_info=True)
    
    def setup_default_tasks(self) -> None:
        """Set up default scheduled tasks from configuration."""
        # RSS collection task
        if hasattr(settings, 'scheduler_rss_cron'):
            rss_task = ScheduledTask(
                name="collect_rss",
                cron_expression=settings.scheduler_rss_cron,
                task_func=self.collect_news,
            )
            self.add_task(rss_task)
        
        # Daily digest task
        if hasattr(settings, 'scheduler_daily_digest_cron'):
            daily_digest_task = ScheduledTask(
                name="daily_digest",
                cron_expression=settings.scheduler_daily_digest_cron,
                task_func=self.generate_digest,
                kwargs={"period": "daily"},
            )
            self.add_task(daily_digest_task)
        
        # Weekly digest task
        if hasattr(settings, 'scheduler_weekly_digest_cron'):
            weekly_digest_task = ScheduledTask(
                name="weekly_digest", 
                cron_expression=settings.scheduler_weekly_digest_cron,
                task_func=self.generate_digest,
                kwargs={"period": "weekly"},
            )
            self.add_task(weekly_digest_task)
        
        # Cleanup task
        if hasattr(settings, 'scheduler_cleanup_cron'):
            cleanup_task = ScheduledTask(
                name="cleanup_old_data",
                cron_expression=settings.scheduler_cleanup_cron,
                task_func=self.cleanup_old_data,
            )
            self.add_task(cleanup_task)
    
    async def collect_news(self) -> dict[str, Any]:
        """Collect news from RSS feeds."""
        logger.info("Starting scheduled RSS collection")
        
        try:
            new_items, stats = await self.collector.collect_and_store()
            
            logger.info(
                f"Collected {stats['total']} items: "
                f"{stats['new']} new, {stats['duplicates']} duplicates"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"RSS collection failed: {e}")
            raise
    
    async def generate_digest(self, period: str = "daily") -> dict[str, Any]:
        """Generate news digest.
        
        Args:
            period: Digest period ('daily' or 'weekly')
        """
        logger.info(f"Generating {period} digest")
        
        try:
            # Determine time range
            if period == "daily":
                since = datetime.now(UTC) - timedelta(days=1)
            else:  # weekly
                since = datetime.now(UTC) - timedelta(days=7)
            
            # Get recent items
            items = await self.collector.get_recent_items(
                days=7 if period == "weekly" else 1
            )
            
            if not items:
                logger.info(f"No items found for {period} digest")
                return {"status": "no_items", "period": period}
            
            # Generate digest
            digest = await self.digest_generator.generate_digest(
                items,
                period=period,
                max_items=settings.digest_max_items if hasattr(settings, 'digest_max_items') else 20,
            )
            
            # Save digest (you might want to email it, save to file, etc.)
            digest_path = f"digests/{period}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.md"
            # TODO: Implement digest saving/sending
            
            logger.info(f"Generated {period} digest with {len(digest.items)} items")
            
            return {
                "status": "success",
                "period": period,
                "items_count": len(digest.items),
                "categories": list(digest.categories.keys()),
            }
            
        except Exception as e:
            logger.error(f"Digest generation failed: {e}")
            raise
    
    async def cleanup_old_data(self) -> dict[str, Any]:
        """Clean up old data from database and caches."""
        logger.info("Starting scheduled cleanup")
        
        try:
            # Clean deduplication cache
            cleanup_days = getattr(settings, 'cleanup_days', 30)
            stats = await self.collector.cleanup_old_duplicates(days=cleanup_days)
            
            logger.info(
                f"Cleanup complete: removed {stats['database_entries_removed']} "
                f"DB entries and {stats['cache_files_removed']} cache files"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise
    
    def start(self) -> None:
        """Start the scheduler."""
        if self.scheduler.running:
            logger.warning("Scheduler already running")
            return
        
        self.scheduler.start()
        logger.info(f"Scheduler started with {len(self.tasks)} tasks")
        
        # Log next run times
        for task in self.tasks.values():
            logger.info(f"Task '{task.name}' next run: {task.next_run}")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if not self.scheduler.running:
            logger.warning("Scheduler not running")
            return
        
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    
    def get_status(self) -> dict[str, Any]:
        """Get scheduler status and task information."""
        return {
            "running": self.scheduler.running,
            "tasks": {
                name: {
                    "cron": task.cron_expression,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "next_run": task.next_run.isoformat() if task.next_run else None,
                    "run_count": task.run_count,
                    "error_count": task.error_count,
                    "last_error": task.last_error,
                }
                for name, task in self.tasks.items()
            }
        }
    
    async def run_task_now(self, task_name: str) -> None:
        """Run a specific task immediately.
        
        Args:
            task_name: Name of task to run
        """
        if task_name not in self.tasks:
            raise ValueError(f"Task '{task_name}' not found")
        
        task = self.tasks[task_name]
        logger.info(f"Running task '{task_name}' manually")
        await self._run_task(task)