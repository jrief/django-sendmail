import pytest
import time
from datetime import timedelta
from multiprocessing import Process

from sendmail.dblock import db_lock, TimeoutException, LockedException
from sendmail.models import DBMutex


@pytest.mark.django_db
def test_lock_expires_by_itself():
    with pytest.raises(TimeoutException):
        with db_lock('test_dblock', timedelta(seconds=1)) as lock:
            assert DBMutex.objects.filter(locked_by=lock.locked_by, lock_id=lock.lock_id).exists()
            time.sleep(1.1)  # task runs too long
    assert not DBMutex.objects.filter(locked_by=lock.locked_by, lock_id=lock.lock_id).exists()


@pytest.mark.django_db(transaction=True)
def test_aquire_and_release_locks():
    lock1 = db_lock('test_dblock', timedelta(seconds=1))
    assert not DBMutex.objects.filter(locked_by=lock1.locked_by, lock_id=lock1.lock_id).exists()
    lock1.acquire()
    assert DBMutex.objects.filter(locked_by=lock1.locked_by, lock_id=lock1.lock_id).exists()
    lock2 = db_lock('test_dblock', timedelta(seconds=1))
    with pytest.raises(LockedException):
        lock2.acquire()
    lock1.release()
    assert not DBMutex.objects.filter(locked_by=lock1.locked_by, lock_id=lock1.lock_id).exists()
    lock2.acquire()
    lock3 = db_lock('test_dblock3', timedelta(seconds=60))
    lock3.acquire()
    assert DBMutex.objects.filter(locked_by=lock3.locked_by, lock_id=lock3.lock_id).exists()
    assert DBMutex.objects.filter(locked_by=lock2.locked_by, lock_id=lock2.lock_id).exists()
    lock2.release()
    assert DBMutex.objects.filter(locked_by=db_lock.locked_by).exists()
    lock3.release()
    assert not DBMutex.objects.filter(locked_by=db_lock.locked_by).exists()


@pytest.mark.django_db
def test_lock_using_decorator():
    @db_lock('test_dblock', timedelta(seconds=1))
    def func(sleep_time):
        time.sleep(sleep_time)
        return 'some result'

    assert func(0.2) == 'some result'
    with pytest.raises(TimeoutException):
        func(2.0)


def concurrent_lock():
    # lock the mutex and wait for 0.5 seconds
    with db_lock('test_dblock', timedelta(seconds=1)):
        time.sleep(0.5)


@pytest.mark.django_db(transaction=True)
def test_refuse_to_lock_concurrent_task():
    proc = Process(target=concurrent_lock)
    proc.start()
    time.sleep(0.1)
    lock = db_lock('test_dblock', timedelta(seconds=1))
    with pytest.raises(LockedException):
        lock.acquire()
        print("second lock aquired")
    proc.join()


@pytest.mark.django_db(transaction=True)
def test_wait_for_concurrent_task():
    proc = Process(target=concurrent_lock)
    proc.start()
    time_stamp = time.monotonic()
    time.sleep(0.1)
    with db_lock('test_dblock', timedelta(seconds=1), wait=True) as lock:
        # check that the lock was acquired at least 0.5 seconds later
        assert time.monotonic() - time_stamp > 0.5
    proc.join()
    assert not DBMutex.objects.filter(locked_by=lock.locked_by).exists()


@pytest.mark.django_db
def test_lock_remaining_time():
    with pytest.raises(TimeoutException):
        with db_lock('test_dblock', timedelta(seconds=1)) as lock:
            assert lock.remaining_time < timedelta(seconds=1)
            assert lock.remaining_time > timedelta(seconds=0.8)
            time.sleep(0.1)
            assert lock.remaining_time < timedelta(seconds=0.9)
            assert lock.remaining_time > timedelta(seconds=0.7)
            time.sleep(0.5)
            assert lock.remaining_time < timedelta(seconds=0.5)
            assert lock.remaining_time > timedelta(seconds=0.3)
            time.sleep(1)
            raise RuntimeError  # this should never be reached
    assert not DBMutex.objects.filter(locked_by=lock.locked_by, lock_id=lock.lock_id).exists()
