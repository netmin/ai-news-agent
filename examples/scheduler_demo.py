"""Demo script for the scheduler functionality."""

import asyncio
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_news_agent.scheduler import Scheduler, ScheduledTask


async def demo_task(name: str):
    """Simple demo task."""
    logger.info(f"Demo task '{name}' executed at {datetime.now(UTC)}")
    return f"Task {name} completed"


async def main():
    """Run scheduler demo."""
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Create scheduler
    scheduler = Scheduler()
    
    # Add some demo tasks
    tasks = [
        ScheduledTask(
            name="frequent_task",
            cron_expression="*/1 * * * *",  # Every minute
            task_func=demo_task,
            args=("Frequent",),
        ),
        ScheduledTask(
            name="hourly_task",
            cron_expression="0 * * * *",  # Every hour
            task_func=demo_task,
            args=("Hourly",),
        ),
    ]
    
    for task in tasks:
        scheduler.add_task(task)
    
    # Add default tasks from config
    logger.info("Setting up default tasks from configuration...")
    scheduler.setup_default_tasks()
    
    # Show initial status
    status = scheduler.get_status()
    logger.info("Scheduler status:")
    for name, info in status["tasks"].items():
        logger.info(f"  {name}: cron='{info['cron']}', next run={info['next_run']}")
    
    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to stop.")
    
    # Handle shutdown gracefully
    def shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Run a task immediately
    logger.info("Running RSS collection task immediately...")
    try:
        await scheduler.run_task_now("collect_rss")
    except Exception as e:
        logger.error(f"Failed to run RSS collection: {e}")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(30)
            
            # Show periodic status
            running_status = scheduler.get_status()
            logger.info("Current task statistics:")
            for name, info in running_status["tasks"].items():
                logger.info(
                    f"  {name}: runs={info['run_count']}, "
                    f"errors={info['error_count']}, "
                    f"last_run={info['last_run'] or 'never'}"
                )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    from pathlib import Path
    asyncio.run(main())