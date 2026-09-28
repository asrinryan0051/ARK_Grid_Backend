# Smart Street Light Monitoring System — Documentation

## 1. System Overview

The Smart Street Light Monitoring System is a distributed IoT setup consisting of three tiers:

| Component | Role | Current Deployment |
|---|---|---|
| **ESP32 Nodes** | Sensor/actuator nodes attached to individual street lights. Read LDR (light-dependent resistor) values and control an LED. | Multiple physical ESP32 boards |
| **Gateway Node** | Aggregates data from multiple ESP32 nodes on the local network and forwards it to the cloud backend. | An ESP32 connected to the same network as the laptop running the backend |
| **Cloud Backend Server** | Central server that receives node data, maintains live system state, and pushes updates to connected dashboards in real time. | FastAPI application (`backend.py`) running on a laptop, exposed publicly via a Cloudflare quick tunnel |
| **Frontend Dashboard** | Web dashboard that visualizes node status in real time. | Runs on a separate laptop, connects to the backend over WebSocket |

```
[ESP32 Node] ──┐
[ESP32 Node] ──┼──► [Gateway Node (ESP32)] ──► [Cloud Backend (FastAPI)] ──► [Frontend Dashboard]
[ESP32 Node] ──┘                                     ▲
                                            (public URL via Cloudflare Tunnel)
```

*(Gateway and ESP32 node documentation to be added in a future revision.)*

---

## 2. Backend Architecture

The backend is implemented using **FastAPI** and exposes two interfaces:

1. A **REST endpoint** (`POST /trigger`) for the gateway to push node data to the cloud.
2. A **WebSocket endpoint** (`/ws`) for the frontend dashboard to receive live updates.

The backend acts as the single source of truth for the current state of all known nodes, held in an in-memory dictionary (`node_dict`), and as a broadcast hub — any data received via `/trigger` is immediately pushed out to every connected dashboard via `/ws`.

### 2.1 Key In-Memory State

| Variable | Type | Purpose |
|---|---|---|
| `node_dict` | `dict[str, dict]` | Maps `node_id` → latest known data for that node (LED status, LDR value, MAC address, last-updated timestamp). Acts as the current system state snapshot. |
| `active_sockets` | `list[WebSocket]` | Tracks all currently connected dashboard WebSocket clients, so new data can be broadcast to all of them. |

> **Note:** State is stored only in memory. It resets whenever the server restarts, and does not currently persist to a database.

### 2.2 CORS Configuration

CORS middleware is configured with `allow_origins=["*"]`, allowing requests from any origin. This is intended for development/testing (e.g. the frontend running on a different machine/origin than the backend). It should be restricted to the specific frontend origin before any production deployment.

---

## 3. API Reference

### 3.1 `POST /trigger`

Used by the **gateway node** to report data for a single ESP32 node.

**Request body** (`NodeData` model):

| Field | Type | Description |
|---|---|---|
| `node_id` | `string` | Unique identifier for the ESP32 node |
| `mac_address` | `string` | MAC address of the node, used as a hardware identifier |
| `led_status` | `boolean` | Current state of the street light LED (on/off) |
| `ldr_value` | `integer` | Raw light sensor (LDR) reading from the node |

**Behavior:**
1. Logs the incoming data to the console.
2. Adds a `connected_at` timestamp (server-side, `YYYY-MM-DD HH:MM:SS`) to the record.
3. Stores/overwrites the entry in `node_dict` under the node's `node_id`.
4. Broadcasts the **entire updated `node_dict`** (not just the single node) to every connected WebSocket client.

**Response:**
```json
{
  "status": "success",
  "message": "Data Received",
  "data": { ...echoed input data... }
}
```

### 3.2 `WS /ws`

Used by the **frontend dashboard** to receive live node updates.

**Connection behavior:**
1. On connect, the socket is accepted and added to `active_sockets`.
2. The current full `node_dict` snapshot is sent immediately, so a newly connected dashboard has the latest state without waiting for the next update.
3. The connection is then held open; the server calls `receive_text()` in a loop purely to detect disconnects (it does not currently process incoming messages from the dashboard).
4. On disconnect (`WebSocketDisconnect`), the socket is removed from `active_sockets`.

**Message format pushed to clients:**
The full `node_dict`, e.g.:
```json
{
  "node_1": {
    "node_id": "node_1",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "led_status": true,
    "ldr_value": 512,
    "connected_at": "2026-09-24 10:15:32"
  }
}
```

---

## 4. Data Flow

1. An ESP32 node reads its LDR sensor and sets its LED state locally.
2. The **gateway node** collects readings from nearby ESP32 nodes and sends each as a `POST /trigger` request to the cloud backend (currently reached via a Cloudflare quick tunnel public URL, since the backend runs on a laptop rather than a fixed server).
3. The backend updates its in-memory `node_dict` and immediately broadcasts the full state to all connected dashboards over `/ws`.
4. The **frontend dashboard**, already connected via WebSocket, receives the update and re-renders the live view — no polling required.
5. Any dashboard that connects later receives the current full snapshot immediately upon connecting, before any new `/trigger` event occurs.

---

## 5. Known Limitations / Notes for Future Work

- **No persistence:** all node state is lost on server restart; no database is currently used.
- **No authentication:** `/trigger` and `/ws` are open endpoints; anyone with the public tunnel URL can post data or read live state.
- **Broad CORS policy** (`*`) is set for development convenience and should be tightened later.
- **Broadcast is not targeted:** `/trigger` always sends the *entire* `node_dict` to all clients rather than just the changed node, which is simple but not bandwidth-efficient as node count grows.
- **Public exposure via Cloudflare quick tunnel** is temporary by design (URL changes on every restart); a named tunnel or proper hosting would be needed for a stable deployment.