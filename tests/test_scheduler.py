"""Tests for the scheduler module."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger

from ai_news_agent.scheduler import ScheduledTask, Scheduler


@pytest.fixture
def mock_collector():
    """Create mock RSS collector."""
    collector = AsyncMock()
    collector.collect_and_store.return_value = (
        [],  # new_items
        {
            "total": 10,
            "new": 5,
            "duplicates": 5,
            "failed_sources": [],
            "run_id": 1,
        }
    )
    collector.get_recent_items.return_value = []
    collector.cleanup_old_duplicates.return_value = {
        "database_entries_removed": 50,
        "cache_files_removed": 10,
    }
    return collector


@pytest.fixture
def mock_digest_generator():
    """Create mock digest generator."""
    generator = AsyncMock()
    mock_digest = MagicMock()
    mock_digest.items = [MagicMock() for _ in range(5)]
    mock_digest.categories = {"AI": 3, "Tech": 2}
    generator.generate_digest.return_value = mock_digest
    return generator


@pytest.fixture
def scheduler(mock_collector, mock_digest_generator):
    """Create scheduler with mocked dependencies."""
    sched = Scheduler()
    sched.collector = mock_collector
    sched.digest_generator = mock_digest_generator
    return sched


class TestScheduledTask:
    """Test ScheduledTask class."""
    
    def test_task_creation(self):
        """Test creating a scheduled task."""
        async def dummy_task(x, y=1):
            return x + y
        
        task = ScheduledTask(
            name="test_task",
            cron_expression="0 * * * *",
            task_func=dummy_task,
            args=(5,),
            kwargs={"y": 2},
        )
        
        assert task.name == "test_task"
        assert task.cron_expression == "0 * * * *"
        assert task.task_func == dummy_task
        assert task.args == (5,)
        assert task.kwargs == {"y": 2}
        assert task.last_run is None
        assert task.next_run is None
        assert task.run_count == 0
        assert task.error_count == 0
        assert task.last_error is None


class TestScheduler:
    """Test Scheduler class."""
    
    def test_initialization(self, scheduler):
        """Test scheduler initialization."""
        assert scheduler.scheduler is not None
        assert len(scheduler.tasks) == 0
        assert not scheduler.scheduler.running
    
    def test_add_task(self, scheduler):
        """Test adding a task to scheduler."""
        async def dummy_task():
            return "done"
        
        task = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",  # Every hour
            task_func=dummy_task,
        )
        
        scheduler.add_task(task)
        
        assert "test" in scheduler.tasks
        assert scheduler.tasks["test"] == task
        # next_run will be None until scheduler is started
    
    def test_add_task_invalid_cron(self, scheduler):
        """Test adding task with invalid cron expression."""
        async def dummy_task():
            return "done"
        
        task = ScheduledTask(
            name="test",
            cron_expression="invalid cron",
            task_func=dummy_task,
        )
        
        with pytest.raises(ValueError, match="Invalid cron expression"):
            scheduler.add_task(task)
    
    def test_add_duplicate_task(self, scheduler):
        """Test replacing an existing task."""
        async def dummy_task():
            return "done"
        
        task1 = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",
            task_func=dummy_task,
        )
        task2 = ScheduledTask(
            name="test",
            cron_expression="30 * * * *",
            task_func=dummy_task,
        )
        
        scheduler.add_task(task1)
        scheduler.add_task(task2)
        
        assert len(scheduler.tasks) == 1
        assert scheduler.tasks["test"].cron_expression == "30 * * * *"
    
    def test_remove_task(self, scheduler):
        """Test removing a task."""
        async def dummy_task():
            return "done"
        
        task = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",
            task_func=dummy_task,
        )
        
        scheduler.add_task(task)
        assert "test" in scheduler.tasks
        
        scheduler.remove_task("test")
        assert "test" not in scheduler.tasks
    
    @pytest.mark.asyncio
    async def test_run_task_success(self, scheduler):
        """Test successfully running a task."""
        result = []
        
        async def test_func(value):
            result.append(value)
            return value
        
        task = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",
            task_func=test_func,
            args=(42,),
        )
        
        await scheduler._run_task(task)
        
        assert result == [42]
        assert task.run_count == 1
        assert task.error_count == 0
        assert task.last_run is not None
        assert task.last_error is None
    
    @pytest.mark.asyncio
    async def test_run_task_error(self, scheduler):
        """Test task execution with error."""
        async def failing_task():
            raise RuntimeError("Task failed")
        
        task = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",
            task_func=failing_task,
        )
        
        await scheduler._run_task(task)
        
        assert task.run_count == 0
        assert task.error_count == 1
        assert task.last_error == "Task failed"
    
    @pytest.mark.asyncio
    async def test_collect_news(self, scheduler, mock_collector):
        """Test news collection task."""
        result = await scheduler.collect_news()
        
        assert result["total"] == 10
        assert result["new"] == 5
        assert result["duplicates"] == 5
        mock_collector.collect_and_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_daily_digest(self, scheduler, mock_collector, mock_digest_generator):
        """Test daily digest generation."""
        # Setup mock items
        mock_items = [MagicMock() for _ in range(3)]
        mock_collector.get_recent_items.return_value = mock_items
        
        result = await scheduler.generate_digest(period="daily")
        
        assert result["status"] == "success"
        assert result["period"] == "daily"
        assert result["items_count"] == 5
        assert "AI" in result["categories"]
        
        mock_collector.get_recent_items.assert_called_once_with(days=1)
        mock_digest_generator.generate_digest.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_weekly_digest(self, scheduler, mock_collector):
        """Test weekly digest generation."""
        mock_items = [MagicMock() for _ in range(5)]
        mock_collector.get_recent_items.return_value = mock_items
        
        result = await scheduler.generate_digest(period="weekly")
        
        assert result["period"] == "weekly"
        mock_collector.get_recent_items.assert_called_once_with(days=7)
    
    @pytest.mark.asyncio
    async def test_generate_digest_no_items(self, scheduler, mock_collector):
        """Test digest generation with no items."""
        mock_collector.get_recent_items.return_value = []
        
        result = await scheduler.generate_digest()
        
        assert result["status"] == "no_items"
        assert result["period"] == "daily"
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, scheduler, mock_collector):
        """Test cleanup task."""
        result = await scheduler.cleanup_old_data()
        
        assert result["database_entries_removed"] == 50
        assert result["cache_files_removed"] == 10
        mock_collector.cleanup_old_duplicates.assert_called_once_with(days=30)
    
    def test_setup_default_tasks(self, scheduler):
        """Test setting up default tasks from config."""
        with patch("ai_news_agent.scheduler.scheduler.settings") as mock_settings:
            mock_settings.scheduler_rss_cron = "0 */6 * * *"
            mock_settings.scheduler_daily_digest_cron = "0 17 * * *"
            mock_settings.scheduler_weekly_digest_cron = "0 8 * * 0"
            mock_settings.scheduler_cleanup_cron = "0 2 * * 0"
            
            scheduler.setup_default_tasks()
            
            assert len(scheduler.tasks) == 4
            assert "collect_rss" in scheduler.tasks
            assert "daily_digest" in scheduler.tasks
            assert "weekly_digest" in scheduler.tasks
            assert "cleanup_old_data" in scheduler.tasks
    
    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        """Test starting and stopping scheduler."""
        # Add a task first
        async def dummy_task():
            pass
        
        task = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",
            task_func=dummy_task,
        )
        scheduler.add_task(task)
        
        # Start
        scheduler.start()
        assert scheduler.scheduler.running
        
        # Give scheduler time to start
        await asyncio.sleep(0.1)
        
        # Try to start again
        scheduler.start()  # Should log warning but not fail
        
        # Stop
        scheduler.stop()
        # Give scheduler time to shut down
        await asyncio.sleep(0.1)
        assert not scheduler.scheduler.running
        
        # Try to stop again
        scheduler.stop()  # Should log warning but not fail
    
    def test_get_status(self, scheduler):
        """Test getting scheduler status."""
        # Add tasks
        async def task1():
            pass
        
        async def task2():
            pass
        
        t1 = ScheduledTask("task1", "0 * * * *", task1)
        t2 = ScheduledTask("task2", "30 * * * *", task2)
        
        scheduler.add_task(t1)
        scheduler.add_task(t2)
        
        # Set some task stats
        t1.run_count = 5
        t1.last_run = datetime.now(UTC)
        t2.error_count = 2
        t2.last_error = "Test error"
        
        status = scheduler.get_status()
        
        assert not status["running"]
        assert len(status["tasks"]) == 2
        assert status["tasks"]["task1"]["run_count"] == 5
        assert status["tasks"]["task1"]["last_run"] is not None
        assert status["tasks"]["task2"]["error_count"] == 2
        assert status["tasks"]["task2"]["last_error"] == "Test error"
    
    @pytest.mark.asyncio
    async def test_run_task_now(self, scheduler):
        """Test running a specific task immediately."""
        executed = []
        
        async def test_task(value):
            executed.append(value)
        
        task = ScheduledTask(
            name="test",
            cron_expression="0 * * * *",
            task_func=test_task,
            args=(123,),
        )
        
        scheduler.add_task(task)
        await scheduler.run_task_now("test")
        
        assert executed == [123]
        assert task.run_count == 1
    
    @pytest.mark.asyncio
    async def test_run_task_now_not_found(self, scheduler):
        """Test running non-existent task."""
        with pytest.raises(ValueError, match="Task 'nonexistent' not found"):
            await scheduler.run_task_now("nonexistent")
    
    def test_cron_expressions(self):
        """Test various cron expressions are valid."""
        expressions = [
            ("0 * * * *", "Every hour"),
            ("0 */6 * * *", "Every 6 hours"),
            ("0 9 * * *", "Daily at 9 AM"),
            ("0 9 * * 1-5", "Weekdays at 9 AM"),
            ("0 9 * * 6,0", "Weekends at 9 AM"),
            ("*/15 * * * *", "Every 15 minutes"),
            ("0 0 1 * *", "First day of month"),
        ]
        
        for expr, desc in expressions:
            try:
                trigger = CronTrigger.from_crontab(expr)
                assert trigger is not None, f"{desc} should be valid"
            except Exception as e:
                pytest.fail(f"{desc} ({expr}) failed: {e}")