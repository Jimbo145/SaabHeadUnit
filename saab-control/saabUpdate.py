import asyncio


async def say_after():
    await asyncio.sleep(0.1)
    asyncio.create_task(say_after2())
    print("here")

async def say_after2():
    await asyncio.sleep(0.1)
    print("there")

async def main():

    asyncio.create_task(say_after())
    while True:

        await asyncio.sleep(0.1)


asyncio.run(main())