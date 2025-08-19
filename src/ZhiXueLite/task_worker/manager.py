import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from app.database.models import BackgroundTask, TaskStatus
from task_worker.database import init_db, get_session
from task_worker.repository import get_next_pending_task, update_task_status


class TaskManager:
    """后台任务管理器 - 使用子进程执行任务"""

    def __init__(self):
        self.polling_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.poll_interval = 2
        self.task_timeout = 300  # 默认 5 分钟任务超时
        self.running_processes: dict[str, subprocess.Popen] = {}  # 跟踪运行中的进程

    def get_runner_script_path(self) -> Path:
        """获取 runner.py 脚本的路径"""
        current_dir = Path(__file__).parent
        return current_dir / "runner.py"

    def process_task(self, task: BackgroundTask):
        """使用子进程处理单个任务"""
        try:
            logger.info(f"Starting task in subprocess: {task.uuid} - {task.task_type}")

            runner_script = self.get_runner_script_path()
            if not runner_script.exists():
                raise FileNotFoundError(f"Runner script not found: {runner_script}")

            # 构建命令行参数
            cmd = [
                sys.executable, str(runner_script),
                "--task-uuid", task.uuid,
                "--task-id", str(task.id),
                "--task-type", task.task_type,
                "--user-id", str(task.user_id),
                "--parameters", task.parameters or "{}"
            ]

            # 启动子进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(__file__).parent.parent.parent.parent  # 设置工作目录为项目根目录
            )

            # 记录进程
            self.running_processes[task.uuid] = process

            try:
                task_timeout = task.timeout if task.timeout and task.timeout > 0 else self.task_timeout
                logger.debug(f"Task {task.uuid} will run with timeout: {task_timeout}s")

                # 等待进程完成
                stdout, stderr = process.communicate(timeout=task_timeout)

                if process.returncode == 0:
                    logger.info(f"Task subprocess completed successfully: {task.uuid}")
                    if stdout:
                        logger.debug(f"Task stdout: {stdout}")
                else:
                    logger.warning(f"Task subprocess failed with code {process.returncode}: {task.uuid}")
                    if stderr:
                        logger.warning(f"Task stderr: {stderr}")

                    # 如果子进程失败，确保数据库中的任务状态被更新
                    with get_session() as session:
                        update_task_status(
                            session,
                            task.uuid,
                            TaskStatus.FAILED,
                            error_message="Task failed due to unknown error, "
                                          "please contact the administrator for more information"
                        )
                        session.commit()

            except subprocess.TimeoutExpired:
                logger.warning(f"Task subprocess timeout: {task.uuid}")
                process.kill()
                stdout, stderr = process.communicate()

                # 更新任务状态为超时失败
                with get_session() as session:
                    update_task_status(
                        session,
                        task.uuid,
                        TaskStatus.FAILED,
                        error_message=f"Task timeout after {task_timeout} seconds"
                    )
                    session.commit()

            finally:
                # 清理进程记录
                self.running_processes.pop(task.uuid, None)

        except Exception as e:
            logger.error(f"Failed to start task subprocess: {task.uuid} - {str(e)}")
            # 更新任务状态为失败
            with get_session() as session:
                update_task_status(
                    session,
                    task.uuid,
                    TaskStatus.FAILED,
                    error_message="Failed to start task, please contact the administrator for more information"
                )
                session.commit()

    def stop_task(self, task_uuid: str) -> bool:
        """停止指定的任务"""
        process = self.running_processes.get(task_uuid)
        if process and process.poll() is None:  # 进程还在运行
            try:
                process.terminate()
                # 给进程一些时间优雅退出
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 如果还没退出，强制杀死
                    process.kill()
                    process.wait()

                # 更新任务状态
                with get_session() as session:
                    update_task_status(
                        session,
                        task_uuid,
                        TaskStatus.FAILED,
                        error_message="Task was manually stopped, please contact the administrator for more information"
                    )
                    session.commit()

                logger.info(f"Task stopped: {task_uuid}")
                return True
            except Exception as e:
                logger.error(f"Failed to stop task {task_uuid}: {e}")
                return False
        return False

    def get_running_tasks(self) -> list[str]:
        """获取当前运行中的任务列表"""
        # 清理已完成的进程
        completed = []
        for task_uuid, process in self.running_processes.items():
            if process.poll() is not None:
                completed.append(task_uuid)

        for task_uuid in completed:
            self.running_processes.pop(task_uuid, None)

        return list(self.running_processes.keys())

    def polling_worker(self):
        """轮询工作线程"""
        logger.info("Polling worker started")
        init_db()

        while self.is_running:
            try:
                task = get_next_pending_task()

                if task:
                    self.process_task(task)
                else:
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Polling worker error: {str(e)}")
                time.sleep(self.poll_interval)

        logger.info("Polling worker stopped")

    def start(self):
        """启动任务管理器"""
        if self.is_running:
            logger.warning("Task Manager is already running")
            return

        self.is_running = True
        self.polling_thread = threading.Thread(
            target=self.polling_worker,
            daemon=True
        )
        self.polling_thread.start()
        logger.info("Task Manager started")

    def stop(self):
        """停止任务管理器"""
        self.is_running = False

        # 停止所有运行中的任务
        running_tasks = list(self.running_processes.keys())
        for task_uuid in running_tasks:
            self.stop_task(task_uuid)

        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=5)
        logger.info("Task Manager stopped")


task_manager = TaskManager()
