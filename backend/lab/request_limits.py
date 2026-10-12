"""Bound request bodies before JSON decoding or multipart spooling."""
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class RequestLimits:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method') not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        path=scope.get('path','')
        limit=128*1024*1024+1_000_000 if path=='/api/audio' else 33_000_000 if path=='/api/exports' else 2_100_000
        length=Headers(scope=scope).get('content-length')
        try:declared=int(length) if length is not None else None
        except ValueError:declared=-1
        if declared is not None and (declared<0 or declared>limit):
            response=JSONResponse({'detail':'Requête trop volumineuse ou taille invalide.'},status_code=413 if declared>=0 else 400,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
            return await response(scope,receive,send)
        count=0
        rejected=False
        async def bounded_receive():
            nonlocal count
            message=await receive()
            if message['type']=='http.request':
                count+=len(message.get('body',b''))
                if count>limit:raise HTTPException(413,'Requête trop volumineuse.')
            return message
        async def bounded_send(message):
            nonlocal rejected
            if count>limit:
                if not rejected:
                    rejected=True
                    response=JSONResponse({'detail':'Requête trop volumineuse.'},status_code=413,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
                    await response(scope,receive,send)
                return
            await send(message)
        await self.app(scope,bounded_receive,bounded_send)
