# Real-Time Chat Example

This example demonstrates a real-time chat application using Cap'n Web with WebSocket transport and bidirectional RPC.

## Features

- **WebSocket Transport**: Persistent connections for real-time updates
- **Bidirectional RPC**: Server can call client methods (for message delivery)
- **Multiple Clients**: Chat room with multiple concurrent users
- **Broadcasting**: Messages sent to all connected clients
- **User Management**: Join/leave notifications
- **Command System**: Built-in commands (/users, /quit, /help)

## Architecture

```
┌─────────────────┐           ┌─────────────────┐
│  Chat Server    │           │  Chat Clients   │
│                 │           │   (multiple)    │
│  ┌───────────┐  │           │                 │
│  │ ChatRoom  │◄─┼───────────┼──▶ Client 1    │
│  │           │  │           │                 │
│  │ - clients │  │  WebSocket│  ┌───────────┐  │
│  │ - history │  │◄──────────┼──┤ChatClient │  │
│  └───────────┘  │           │  │           │  │
│                 │           │  │-onMessage │  │
│  Capabilities:  │           │  └───────────┘  │
│  - join()       │           │                 │
│  - sendMessage()│           │  Client 2       │
│  - leave()      │           │  ┌───────────┐  │
│  - listUsers()  │           │  │ChatClient │  │
└─────────────────┘           │  └───────────┘  │
                              └─────────────────┘
```

## Key Concepts Demonstrated

### 1. WebSocket Transport

Unlike HTTP batch transport, WebSocket maintains a persistent connection:

```python
# Client uses WebSocket URL
config = ClientConfig(url="ws://127.0.0.1:8080/rpc/ws")
```

### 2. Bidirectional RPC

The **server** can call methods on **client** capabilities:

```python
# Server side - store client capability
self.clients[username] = client_capability

# Server calls client method
await client.onMessage(message)
```

```python
# Client side - export capability to server
class ChatClient(RpcTarget):
    async def call(self, method: str, args: list):
        match method:
            case "onMessage":
                # Server calls this!
                return await self._on_message(args[0])
```

### 3. Capability Management

The server stores client capabilities and broadcasts messages:

```python
# Broadcasting to all clients
for username, client in self.clients.items():
    await client.onMessage(message)
```

### 4. Resource Cleanup

When clients disconnect, their capabilities are disposed:

```python
client = self.clients.pop(username)
client.dispose()  # Clean up the capability
```

## Running the Example

### Terminal 1 - Start the Server

```bash
python examples/chat/server.py
```

You should see:
```
🚀 Chat server running on http://127.0.0.1:8080
   WebSocket endpoint: ws://127.0.0.1:8080/rpc/ws
   HTTP endpoint: http://127.0.0.1:8080/rpc/batch

Run clients with: python examples/chat/client.py
Press Ctrl+C to stop
```

### Terminal 2 - Connect First Client

```bash
python examples/chat/client.py
```

```
=== Cap'n Web Chat Client ===

Enter your username: Alice

Connecting to chat server as 'Alice'...

Welcome to the chat, Alice!
Connected users (1): Alice

Type messages and press Enter to send.
Type '/quit' to exit, '/users' to list users, '/help' for commands
```

### Terminal 3 - Connect Second Client

```bash
python examples/chat/client.py
```

```
Enter your username: Bob

Connecting to chat server as 'Bob'...

Welcome to the chat, Bob!
Connected users (2): Alice, Bob
```

Both clients will see:
```
*** Bob joined the chat ***
```

### Chat Example

**Alice types:**
```
Hello everyone!
```

**Alice sees (gray):**
```
[You] Hello everyone!
```

**Bob sees:**
```
[Alice] Hello everyone!
```

**Bob types:**
```
Hi Alice!
```

**Bob sees (gray):**
```
[You] Hi Alice!
```

**Alice sees:**
```
[Bob] Hi Alice!
```

### Commands

**List users:**
```
/users

Connected users: Alice, Bob
```

**Help:**
```
/help

Commands:
  /users  - List connected users
  /quit   - Leave the chat
  /help   - Show this help
```

**Quit:**
```
/quit

Leaving chat...
```

Other users see:
```
*** Alice left the chat ***
```

## Code Walkthrough

### Server Side (server.py)

**ChatRoom Class:**
- Manages connected clients (stores capabilities)
- Broadcasts messages to all clients
- Handles join/leave events
- Maintains message history

**Key Methods:**
- `join(username, client_capability)` - Register new user
- `sendMessage(username, text)` - Broadcast a message
- `leave(username)` - Remove user and notify others

**Broadcasting:**
```python
async def _broadcast_message(self, message: dict) -> None:
    tasks = []
    for username, client in self.clients.items():
        task = client.onMessage(message)
        tasks.append((username, task))

    for username, task in tasks:
        try:
            await task
        except Exception as e:
            # Remove unreachable clients
            self.clients.pop(username).dispose()
```

### Client Side (client.py)

**ChatClient Class:**
- Exports `onMessage` method to receive messages from server
- Handles different message types (chat, system)
- Formats output with colors

**Main Loop:**
```python
# Join chat
client_stub = client.create_stub(ChatClient(username))
await client.call(0, "join", [username, client_stub])

# Read input and send messages
while True:
    message = await read_input()
    if message == "/quit":
        await client.call(0, "leave", [username])
        break
    else:
        await client.call(0, "sendMessage", [username, message])
```

## Error Handling

The example demonstrates several error handling patterns:

**Username conflicts:**
```python
if username in self.clients:
    raise RpcError.bad_request(f"Username {username} is already taken")
```

**Unreachable clients:**
```python
try:
    await client.onMessage(message)
except Exception:
    # Remove client if they're unreachable
    self.clients.pop(username).dispose()
```

**Connection errors:**
```python
try:
    async with Client(config) as client:
        # ... chat logic
except Exception as e:
    print(f"Connection error: {e}")
```

## Scaling Considerations

For production use, consider:

1. **Message Queue**: Use Redis/RabbitMQ for inter-server communication
2. **Database**: Store message history in a database
3. **Authentication**: Add user authentication
4. **Rate Limiting**: Prevent message flooding
5. **Horizontal Scaling**: Use shared state for multi-server deployments

## Next Steps

- Try running 3+ clients simultaneously
- Modify the client to show typing indicators
- Add private messaging between users
- Add chat rooms/channels
- Implement file sharing
- Add emoji support

## Related Examples

- [Calculator](../calculator/) - Basic client/server example
- [Peer-to-Peer](../peer_to_peer/) - Bidirectional RPC fundamentals
- [Batch Pipelining](../batch-pipelining/) - Performance optimization
