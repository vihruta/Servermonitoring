import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        try:
            result = await client.get("https://example.com", timeout=5)
            if result.status_code in (200, 204):
                print('OK')
                print(type(result.status_code))
            else:
                print(f'Not OK | {result.status_code}' )
        except httpx.ConnectError as exc:
            print(f'Connect error | {exc}')
        except httpx.TimeoutException as exc:
            print(f'Timeout | {exc}')
        

asyncio.run(main())