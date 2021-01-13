from apscheduler.executors.base import BaseExecutor, run_job

from recipe import thread

# apscheduler.executors.pool.BasePoolExecutor를 참고해서 만듦


class ThreadPoolExecutor(BaseExecutor):
    def _do_submit_job(self, job, run_times):

        # job은 함수가 아니라 apscheduler.job.Job 클래스의 인스턴스임
        # run_times는 실행해야 할 시간을 나타내는 datetime들의 list임(보통 1개 원소)

        def threaded_job():
            run_job(job, job._jobstore_alias, run_times, self._logger.name)

        thread.apply_async(threaded_job)

        self._run_job_success(job.id, [])
