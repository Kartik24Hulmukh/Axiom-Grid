import asyncio
import json
import logging
import sys
import traceback
from typing import Callable, Coroutine, Any, Set

log = logging.getLogger("kairo-sidecar.ipc")

# Maximum bytes buffered per connection before the connection is dropped.
# Prevents OOM from malformed or oversized messages.
MAX_MESSAGE_BYTES = 1_048_576  # 1 MB

# Maximum number of requests processed concurrently per connection.
# Prevents a burst of requests from starving legitimate work.
MAX_CONCURRENT_REQUESTS = 16

MAX_OUTSTANDING_REQUESTS = 32
MAX_RETAINED_REQUEST_BYTES = 1_048_576


class AdmissionBudget:
    """Single-event-loop admission for active + queued framed requests.

    Does not bound connection counts, fragment buffers, responses or all memory.
    """

    def __init__(self):
        self.outstanding = 0
        self.retained_bytes = 0

    def reserve(self, size: int) -> bool:
        if size <= 0:
            raise ValueError("Admission size must include the frame delimiter")
        if (self.outstanding >= MAX_OUTSTANDING_REQUESTS
                or self.retained_bytes + size > MAX_RETAINED_REQUEST_BYTES):
            return False
        self.outstanding += 1
        self.retained_bytes += size
        return True

    def release(self, size: int):
        assert self.outstanding > 0 and self.retained_bytes >= size
        self.outstanding -= 1
        self.retained_bytes -= size


class NamedPipeProtocol(asyncio.Protocol):
    def __init__(
        self, handler: Callable[[dict], Coroutine[Any, Any, dict]],
        admission: AdmissionBudget | None = None,
    ):
        # The standalone default is component-local, NOT server-global.
        # start_named_pipe_server supplies one budget shared by its factory.
        self.admission = admission if admission is not None else AdmissionBudget()
        self._closed = False
        self._handler_started: Set[asyncio.Task] = set()
        self.handler = handler
        self.transport = None
        self.buffer = b""
        self._active_tasks: Set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def connection_made(self, transport):
        self.transport = transport
        log.info("Client connected to named pipe")

    def data_received(self, data):
        if self._closed:
            return
        if len(self.buffer) + len(data) > MAX_MESSAGE_BYTES:
            log.error(
                "IPC buffer overflow (>%d bytes) — dropping connection to protect memory",
                MAX_MESSAGE_BYTES,
            )
            self._refuse()
            return
        self.buffer += data
        while b"\n" in self.buffer:
            delimiter = self.buffer.index(b"\n")
            size = delimiter + 1  # Account for the complete frame, including LF.
            if not self.admission.reserve(size):
                self._refuse()
                return
            line = self.buffer[:delimiter]
            self.buffer = self.buffer[size:]
            coroutine = self._process_line(line)
            try:
                task = asyncio.create_task(coroutine)
            except BaseException:
                coroutine.close()
                self.admission.release(size)
                self._refuse()
                raise
            self._active_tasks.add(task)
            # Completion owns release, including cancellation before first run.
            task.add_done_callback(lambda done, size=size: self._completed(done, size))

    def _completed(self, task: asyncio.Task, size: int):
        self._active_tasks.discard(task)
        self._handler_started.discard(task)
        self.admission.release(size)

    def _refuse(self):
        transport = self.transport
        self.connection_lost(None)
        if transport:
            transport.close()

    async def drain(self):
        """Wait for all in-flight requests to complete (call before shutdown)."""
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

    async def _process_line(self, line: bytes):
        if not line.strip():
            return
        async with self._semaphore:
            try:
                req = json.loads(line.decode("utf-8").strip())
                self._handler_started.add(asyncio.current_task())
                resp = await self.handler(req)
                resp_bytes = (json.dumps(resp) + "\n").encode("utf-8")
                if self.transport:
                    self.transport.write(resp_bytes)
            except Exception as e:
                log.error(f"Error handling line: {e}\n{traceback.format_exc()}")
                try:
                    err_resp = {"ok": False, "error": str(e), "traceback": traceback.format_exc()}
                    if self.transport:
                        self.transport.write((json.dumps(err_resp) + "\n").encode("utf-8"))
                except Exception:
                    pass

    def connection_lost(self, exc):
        log.info(f"Client disconnected from named pipe: {exc}")
        self._closed = True
        self.transport = None
        self.buffer = b""
        # Never cancel work once the handler has started: a mutation's outcome
        # may be unknown. Only queued / not-yet-started requests are cancelled.
        for task in self._active_tasks:
            if task not in self._handler_started:
                task.cancel()


async def start_named_pipe_server(
    pipe_name: str, handler: Callable[[dict], Coroutine[Any, Any, dict]]
):
    """Starts the Windows Named Pipe server using asyncio ProactorEventLoop."""
    loop = asyncio.get_running_loop()
    if not sys.platform.startswith("win"):
        # Fallback to local TCP on non-Windows platforms for development/tests compatibility
        raise OSError("Named Pipe IPC is only supported on Windows")

    log.info(f"Binding to Named Pipe: {pipe_name}")

    # ProactorEventLoop has start_serving_pipe
    try:
        admission = AdmissionBudget()
        server = await loop.start_serving_pipe(
            lambda: NamedPipeProtocol(handler, admission), pipe_name
        )
        return server
    except AttributeError:
        log.error(
            "Active event loop does not support Named Pipes (must use ProactorEventLoop on Windows)"
        )
        raise RuntimeError("ProactorEventLoop required for Windows Named Pipes")
