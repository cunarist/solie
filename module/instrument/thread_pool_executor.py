from apscheduler.executors.base import BaseExecutor, run_job

from module import thread_toss

# referred to apscheduler.executors.pool.BasePoolExecutor


class ThreadPoolExecutor(BaseExecutor):
    def _do_submit_job(self, job, run_times):
        # "job"is an instance of apscheduler.job.Job, not a function

        def threaded_job():
            run_job(job, job._jobstore_alias, run_times, self._logger.name)

        thread_toss.apply_async(threaded_job)

        self._run_job_success(job.id, [])
