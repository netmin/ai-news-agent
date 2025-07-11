# Scheduler Module

The scheduler module provides automated task scheduling for the AI News Agent using cron expressions.

## Features

- **Cron-based scheduling**: Use standard cron expressions for flexible scheduling
- **Built-in tasks**:
  - RSS collection (default: every 6 hours)
  - Daily digest generation (default: 17:00 UTC)
  - Weekly digest generation (default: Sunday 08:00 UTC)
  - Data cleanup (default: Sunday 02:00 UTC)
- **Task management**: Add, remove, and monitor scheduled tasks
- **Error handling**: Tracks task failures and continues operation
- **Manual execution**: Run any scheduled task on demand

## Usage

```python
from ai_news_agent.scheduler import Scheduler, ScheduledTask

# Create scheduler
scheduler = Scheduler()

# Add custom task
task = ScheduledTask(
    name="my_task",
    cron_expression="*/30 * * * *",  # Every 30 minutes
    task_func=my_async_function,
    args=(arg1, arg2),
    kwargs={"param": value}
)
scheduler.add_task(task)

# Setup default tasks from config
scheduler.setup_default_tasks()

# Start scheduler
scheduler.start()

# Get status
status = scheduler.get_status()
print(f"Running: {status['running']}")
for name, info in status['tasks'].items():
    print(f"{name}: next run at {info['next_run']}")

# Run task immediately
await scheduler.run_task_now("collect_rss")

# Stop scheduler
scheduler.stop()
```

## Configuration

Configure default schedules in your `.env` file:

```env
AI_NEWS_SCHEDULER_RSS_CRON="0 */6 * * *"          # Every 6 hours
AI_NEWS_SCHEDULER_DAILY_DIGEST_CRON="0 17 * * *"  # Daily at 17:00 UTC
AI_NEWS_SCHEDULER_WEEKLY_DIGEST_CRON="0 8 * * 0"  # Sunday at 08:00 UTC
AI_NEWS_SCHEDULER_CLEANUP_CRON="0 2 * * 0"        # Sunday at 02:00 UTC
```

## Cron Expression Examples

- `"*/15 * * * *"` - Every 15 minutes
- `"0 * * * *"` - Every hour at minute 0
- `"0 9 * * *"` - Daily at 09:00
- `"0 9 * * 1-5"` - Weekdays at 09:00
- `"0 0 1 * *"` - First day of month at midnight
- `"0 */4 * * *"` - Every 4 hours

## Task Status

Each task tracks:
- `last_run`: When the task last executed
- `next_run`: When the task will execute next
- `run_count`: Number of successful executions
- `error_count`: Number of failed executions
- `last_error`: Most recent error message