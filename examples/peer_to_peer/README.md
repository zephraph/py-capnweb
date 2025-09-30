# Peer-to-Peer Example

This example demonstrates that Cap'n Web is truly peer-to-peer with no client/server distinction. Both Alice and Bob:
- Export their own capabilities (act as "servers")
- Call each other's capabilities (act as "clients")

## Running the Example

### Terminal 1 - Start Alice
```bash
cd python/examples/peer_to_peer
python alice.py
```

### Terminal 2 - Start Bob
```bash
cd python/examples/peer_to_peer
python bob.py
```

## What Happens

1. **Alice starts** on port 8080 and exports her capabilities
2. **Alice calls Bob** at port 8081:
   - `greet()` - Gets Bob's greeting
   - `chat("message")` - Sends Bob a message
   - `get_stats()` - Gets Bob's message count

3. **Bob starts** on port 8081 and exports his capabilities
4. **Bob calls Alice** at port 8080:
   - `greet()` - Gets Alice's greeting
   - `chat("message")` - Sends Alice a message
   - `get_stats()` - Gets Alice's message count

5. **Both keep running** and can receive calls from each other

## Expected Output

### Alice's Terminal:
```
🚀 Starting Alice on port 8080...
✅ Alice is running!
   - Alice exports her capabilities at http://127.0.0.1:8080/rpc/batch
   - Alice can receive calls from Bob

🔗 Connecting to Bob at http://127.0.0.1:8081...
📞 Alice calls Bob.greet()...
   ← Hey there! I'm Bob.
📞 Alice calls Bob.chat('Hi Bob!')...
   ← Bob says: Got your message #1!
📞 Alice calls Bob.get_stats()...
   ← {'name': 'Bob', 'messages_received': 1}

📨 Alice received: Hi Alice, this is Bob!
⏳ Alice is waiting for calls from Bob...
```

### Bob's Terminal:
```
🚀 Starting Bob on port 8081...
✅ Bob is running!
   - Bob exports his capabilities at http://127.0.0.1:8081/rpc/batch
   - Bob can receive calls from Alice

🔗 Connecting to Alice at http://127.0.0.1:8080...
📞 Bob calls Alice.greet()...
   ← Hello! I'm Alice.
📞 Bob calls Alice.chat('Hi Alice!')...
   ← Alice says: Thanks for the message #1!
📞 Bob calls Alice.get_stats()...
   ← {'name': 'Alice', 'messages_received': 1}

📨 Bob received: Hi Bob, this is Alice!
⏳ Bob is waiting for calls from Alice...
```

## Key Takeaways

✅ **No client/server distinction** - Both Alice and Bob are peers
✅ **Bidirectional communication** - Both can call each other
✅ **Capability-based** - Each exports their own capabilities
✅ **Simultaneous** - Both processes run concurrently
