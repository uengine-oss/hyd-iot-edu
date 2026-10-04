"""Durable source processing, separate from Kafka acknowledgement and task completion."""
import asyncio
import logging

log=logging.getLogger('process.source')


class SourcePending(Exception):
    def __init__(self,reason,result=None):
        super().__init__(reason);self.result=result


class SourceDelivery:
    def __init__(self,inbox,runtime,apply_event,*,owner,lease_s=60):
        self.inbox,self.runtime,self.apply_event=inbox,runtime,apply_event
        self.owner,self.lease_s=owner,lease_s

    async def run_once(self):
        receipt=await asyncio.to_thread(self.inbox.claim,self.owner,lease_s=self.lease_s)
        if receipt is None:return None
        lost=False
        async def renew():
            nonlocal lost
            while True:
                await asyncio.sleep(self.lease_s/3)
                try:
                    if await asyncio.to_thread(self.inbox.renew,receipt,lease_s=self.lease_s) is None:
                        lost=True;return
                except Exception:
                    lost=True;log.exception('source claim renewal failed: %s',receipt['id']);return
        heartbeat=asyncio.create_task(renew())
        try:
            if receipt['kind']=='RAISE':
                result=await asyncio.to_thread(self.runtime.receive_alert,receipt['payload'],receipt['policy'])
            elif receipt['kind'] in ('CLEAR','ACK'):
                result=await asyncio.to_thread(self.apply_event,receipt)
            else:raise ValueError('unexpected claimable source kind: '+receipt['kind'])
            if lost:return {'id':receipt['id'],'status':'CLAIM_LOST'}
            settled=await asyncio.to_thread(self.inbox.finish,receipt,result)
        except SourcePending as exc:
            settled=await asyncio.to_thread(self.inbox.defer,receipt,str(exc),delay_s=5,result=exc.result)
        except Exception as exc:
            log.exception('source handling failed: %s',receipt['id'])
            settled=await asyncio.to_thread(self.inbox.fail,receipt,f'{type(exc).__name__}: {exc}')
        finally:
            heartbeat.cancel()
            try:await heartbeat
            except asyncio.CancelledError:pass
        return settled or {'id':receipt['id'],'status':'CLAIM_LOST'}

    async def wait_for(self,receipt,*,timeout=30):
        """HTTP may await the same canonical receipt; it never starts a second path."""
        if receipt['status']=='CONFLICT':raise ValueError(receipt['error'])
        receipt_id=receipt['parent_id'] or receipt['id']
        deadline=asyncio.get_running_loop().time()+timeout
        while True:
            row=await asyncio.to_thread(self.inbox.get,receipt_id)
            if row['status']=='HANDLED':return row
            if row['status'] in ('FAILED','INVALID','CONFLICT'):raise ValueError(row['error'])
            if asyncio.get_running_loop().time()>=deadline:
                raise TimeoutError(f'원천 접수 {receipt_id} 처리 대기 중: {row["status"]}')
            await asyncio.sleep(.2)
