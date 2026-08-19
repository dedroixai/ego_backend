"""Business logic for WITHDRAWAL.

Source: app/models/withdrawal.py, docs/database-design.md Section 1.9.

Business rule implemented: a worker may only request withdrawals for
themselves, and only list their own withdrawal history
(`Worker.withdrawEarnings()` in the class diagram). `amount > 0` is already
enforced by the Pydantic schema and a DB CHECK constraint - not re-checked
here.

No payment-processing/commission logic here at all (explicitly out of
scope - "do not implement... Payments"). This service only records a
withdrawal *request*; nothing here moves money or decides payout amounts.

`status` has no defined default anywhere (same undefined-enum situation as
JobService) - required, caller-supplied, not guessed.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from app.models.withdrawal import Withdrawal
from app.repositories.exceptions import RepositoryError
from app.repositories.withdrawal_repository import WithdrawalRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.base import BaseService
from app.services.exceptions import ResourceNotFoundError, UnauthorizedOperationError


class WithdrawalService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._withdrawals = WithdrawalRepository(session)
        self._workers = WorkerRepository(session)

    async def list_for_worker(
        self, worker_id: uuid.UUID, requester_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Withdrawal]:
        if requester_id != worker_id:
            raise UnauthorizedOperationError("You can only view your own withdrawal history.")
        return await self._withdrawals.list_by_worker(worker_id, limit=limit, offset=offset)

    async def request_withdrawal(
        self, worker_id: uuid.UUID, requester_id: uuid.UUID, *, amount: Decimal, status: str
    ) -> Withdrawal:
        if requester_id != worker_id:
            raise UnauthorizedOperationError("You can only request withdrawals for yourself.")

        if await self._workers.get_by_id(worker_id) is None:
            raise ResourceNotFoundError("Worker", worker_id)

        try:
            withdrawal = await self._withdrawals.create(worker_id=worker_id, amount=amount, status=status)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return withdrawal
