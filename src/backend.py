from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [                     # VS Code Live Server
    "*"                         # Allows ALL origins (for testing/development)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # Origins allowed to make requests
    allow_credentials=True,     # Allows cookies/authorization headers
    allow_methods=["*"],        # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],        # Allows all headers
)

class NodeData(BaseModel):
    node_id: str
    mac_address: str
    led_status: bool
    ldr_value: int

node_dict = {}           #Stores all the active (connected) nodes
active_sockets = []      #Maintains the connected clients


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_sockets.append(websocket)

    await websocket.send_json(node_dict)

    try:
        while True:
            await websocket.receive_text()  # Keeps connection alive
    except WebSocketDisconnect:
        active_sockets.remove(websocket)
    

@app.post("/trigger")
async def trigger_action(data: NodeData):
    print(f"NODE ID: {data.node_id}")
    print(f"MAC ADDRESS: {data.mac_address}")
    print(f"LED STATUS: {data.led_status}")
    print(f"LDR_value: {data.ldr_value}")

    node_data = data.model_dump()
    node_data["connected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    node_dict[data.node_id] = node_data


    print(node_data)

    for ws in active_sockets:
        await ws.send_json(node_dict)

    return {"status": "success", "message": "Data Received", "data":data}


   