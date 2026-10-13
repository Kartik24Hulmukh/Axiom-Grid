"""A confirmed dead peer cannot receive a capacity-retry response."""
import asyncio

import pytest

from overlay.admission import AdmissionFull, ClientDisconnected, until_disconnect


class ReceivedDisconnect:
    async def receive(self):
        return {"type": "http.disconnect"}


@pytest.mark.asyncio
async def test_completed_disconnect_wins_only_over_simultaneous_capacity_rejection():
    async def saturated():
        raise AdmissionFull()
    with pytest.raises(ClientDisconnected):
        await until_disconnect(saturated(), ReceivedDisconnect(), 1)


@pytest.mark.asyncio
async def test_live_peer_still_gets_real_capacity_failure():
    blocked = asyncio.Event()

    class Connected:
        async def receive(self):
            await blocked.wait()
            return {"type": "http.disconnect"}

    async def saturated():
        raise AdmissionFull()
    with pytest.raises(AdmissionFull):
        await until_disconnect(saturated(), Connected(), 1)


@pytest.mark.asyncio
async def test_completed_storage_failure_is_not_masked_by_disconnect():
    async def failed():
        raise OSError("storage unavailable")
    with pytest.raises(OSError, match="storage unavailable"):
        await until_disconnect(failed(), ReceivedDisconnect(), 1)


@pytest.mark.asyncio
async def test_completed_success_remains_actual_work_even_after_peer_disconnect():
    async def completed():
        return "actual completed operation"
    assert await until_disconnect(completed(), ReceivedDisconnect(), 1) == "actual completed operation"
