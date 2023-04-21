import asyncio, json
from websockets.server import serve

async def parse(websocket):
	async for message in websocket:
		#print("=== RAW MESSAGE RECEIVED ===")
		#print(message)
		#print("============================")
		data = json.loads(message)
		print("=== JSON MESSAGE PARSED  ===")
		print(data)
		print("============================")
		if "text" in data:
			if "bot" in data["text"]:
				print("[INFO] Sending False")
				await websocket.send("False")
			else:
				print("[INFO] Sending True")
				await websocket.send("True")
		else:
			await websocket.send("True")

async def main():
	async with serve(parse, "localhost", 5052):
		await asyncio.Future()  # run forever

asyncio.run(main())
