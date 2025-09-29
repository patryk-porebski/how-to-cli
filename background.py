"""Background job management for parallel command execution"""

import threading
import queue
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from openrouter_client import Command
from logger import get_logger


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundJob:
    """Represents a background job"""
    id: str
    name: str
    command: Command
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0


class JobManager:
    """Manages background job execution"""
    
    def __init__(self, max_workers: int = 3):
        self.logger = get_logger(self.__class__.__name__)
        self.max_workers = max_workers
        self.jobs: Dict[str, BackgroundJob] = {}
        self.job_queue = queue.Queue()
        self.workers: List[threading.Thread] = []
        self.running = False
        self._lock = threading.Lock()
        
        self.start_workers()
    
    def start_workers(self):
        """Start worker threads"""
        if self.running:
            return
        
        self.running = True
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"JobWorker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        self.logger.info(f"Started {self.max_workers} job workers")
    
    def stop_workers(self):
        """Stop worker threads"""
        self.running = False
        
        # Add stop signals to queue
        for _ in range(self.max_workers):
            self.job_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        self.logger.info("Stopped all job workers")
    
    def submit_job(self, name: str, command: Command) -> str:
        """Submit a job for background execution"""
        job_id = str(uuid.uuid4())
        
        job = BackgroundJob(
            id=job_id,
            name=name,
            command=command,
            status=JobStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        with self._lock:
            self.jobs[job_id] = job
        
        self.job_queue.put(job_id)
        
        self.logger.info(f"Submitted job '{name}' with ID {job_id}")
        return job_id
    
    def submit_parallel_jobs(self, commands: List[Command], 
                           name_prefix: str = "Command") -> List[str]:
        """Submit multiple jobs for parallel execution"""
        job_ids = []
        
        for i, command in enumerate(commands):
            if self._can_run_parallel(command):
                job_name = f"{name_prefix} {i+1}: {command.command[:30]}..."
                job_id = self.submit_job(job_name, command)
                job_ids.append(job_id)
            else:
                self.logger.warning(f"Command not suitable for parallel execution: {command.command}")
        
        return job_ids
    
    def _can_run_parallel(self, command: Command) -> bool:
        """Check if command can be run in parallel safely"""
        # Don't run dangerous commands in parallel
        dangerous_patterns = ['rm', 'mv', 'cp', 'chmod', 'chown', 'sudo', 'dd']
        cmd_lower = command.command.lower()
        
        for pattern in dangerous_patterns:
            if pattern in cmd_lower:
                return False
        
        # Don't run interactive commands in parallel
        interactive_patterns = ['vim', 'nano', 'emacs', 'less', 'more', 'top', 'htop']
        for pattern in interactive_patterns:
            if pattern in cmd_lower:
                return False
        
        return True
    
    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get job by ID"""
        with self._lock:
            return self.jobs.get(job_id)
    
    def list_jobs(self, status_filter: Optional[JobStatus] = None) -> List[BackgroundJob]:
        """List all jobs, optionally filtered by status"""
        with self._lock:
            jobs = list(self.jobs.values())
        
        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]
        
        # Sort by creation time, newest first
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            if job.status in [JobStatus.PENDING]:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now().isoformat()
                self.logger.info(f"Cancelled job {job_id}")
                return True
            
            return False
    
    def wait_for_jobs(self, job_ids: List[str], timeout: Optional[float] = None) -> Dict[str, BackgroundJob]:
        """Wait for jobs to complete"""
        start_time = time.time()
        completed_jobs = {}
        
        while len(completed_jobs) < len(job_ids):
            if timeout and (time.time() - start_time) > timeout:
                break
            
            for job_id in job_ids:
                if job_id in completed_jobs:
                    continue
                
                job = self.get_job(job_id)
                if job and job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    completed_jobs[job_id] = job
            
            if len(completed_jobs) < len(job_ids):
                time.sleep(0.1)
        
        return completed_jobs
    
    def get_job_stats(self) -> Dict[str, Any]:
        """Get job execution statistics"""
        with self._lock:
            jobs = list(self.jobs.values())
        
        total = len(jobs)
        by_status = {}
        
        for status in JobStatus:
            count = sum(1 for job in jobs if job.status == status)
            by_status[status.value] = count
        
        # Calculate average execution time for completed jobs
        completed_jobs = [job for job in jobs if job.status == JobStatus.COMPLETED 
                         and job.started_at and job.completed_at]
        
        avg_execution_time = 0.0
        if completed_jobs:
            total_time = 0.0
            for job in completed_jobs:
                start = datetime.fromisoformat(job.started_at)
                end = datetime.fromisoformat(job.completed_at)
                total_time += (end - start).total_seconds()
            avg_execution_time = total_time / len(completed_jobs)
        
        return {
            'total_jobs': total,
            'by_status': by_status,
            'average_execution_time': avg_execution_time,
            'queue_size': self.job_queue.qsize(),
            'active_workers': len([w for w in self.workers if w.is_alive()])
        }
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed jobs"""
        cutoff_time = datetime.now()
        cutoff_time = cutoff_time.replace(hour=cutoff_time.hour - max_age_hours)
        cutoff_str = cutoff_time.isoformat()
        
        removed_count = 0
        with self._lock:
            job_ids_to_remove = []
            
            for job_id, job in self.jobs.items():
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] 
                    and job.completed_at and job.completed_at < cutoff_str):
                    job_ids_to_remove.append(job_id)
            
            for job_id in job_ids_to_remove:
                del self.jobs[job_id]
                removed_count += 1
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old jobs")
        
        return removed_count
    
    def _worker_loop(self):
        """Main worker loop"""
        worker_name = threading.current_thread().name
        self.logger.debug(f"Worker {worker_name} started")
        
        while self.running:
            try:
                # Get job from queue (blocking with timeout)
                job_id = self.job_queue.get(timeout=1)
                
                # Check for stop signal
                if job_id is None:
                    break
                
                # Execute job
                self._execute_job(job_id)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker {worker_name} error: {e}")
        
        self.logger.debug(f"Worker {worker_name} stopped")
    
    def _execute_job(self, job_id: str):
        """Execute a job"""
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.PENDING:
            return
        
        try:
            # Update job status
            with self._lock:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now().isoformat()
            
            self.logger.debug(f"Executing job {job_id}: {job.command.command}")
            
            # Import here to avoid circular imports
            from executor import CommandExecutor
            
            # Execute command
            executor = CommandExecutor(require_confirmation=False)
            success, output = executor._execute_single_command(job.command)
            
            # Update job with results
            with self._lock:
                job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
                job.completed_at = datetime.now().isoformat()
                job.progress = 100.0
                job.result = {
                    'success': success,
                    'output': output,
                    'command': job.command.command
                }
                
                if not success:
                    job.error = output
            
            self.logger.debug(f"Job {job_id} completed with success={success}")
            
        except Exception as e:
            self.logger.error(f"Job {job_id} failed with error: {e}")
            
            with self._lock:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now().isoformat()
                job.error = str(e)
