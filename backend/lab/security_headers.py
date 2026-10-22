"""Browser protections applied even when request admission rejects a body."""
from starlette.datastructures import MutableHeaders


class SecurityHeaders:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        async def protected_send(message):
            if message['type']=='http.response.start':
                headers=MutableHeaders(scope=message)
                policy="base-uri 'self'; object-src 'none'; frame-ancestors 'self'; form-action 'self'"
                if scope['path'].startswith(('/api/exports/','/api/export/svg')):policy+='; sandbox'
                headers['Content-Security-Policy']=policy
                headers['X-Frame-Options']='SAMEORIGIN'
                headers['X-Content-Type-Options']='nosniff'
                headers['Referrer-Policy']='same-origin'
                headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
                if scope.get('scheme')=='https':headers['Strict-Transport-Security']='max-age=15552000'
                if scope['path'].startswith(('/api/','/login','/register','/auth/')):
                    headers['Cache-Control']='no-store'
            await send(message)
        await self.app(scope,receive,protected_send)
