# Microservices Example

This example demonstrates a microservices architecture using Cap'n Web, showcasing service mesh communication, capability-based authentication, and cross-service authorization.

## Features

- **Service Mesh Architecture**: Three independent services coordinated by an API gateway
- **Capability-Based Security**: User capabilities passed between services for authentication
- **Cross-Service Authorization**: Services verify permissions via capability RPC calls
- **Service Orchestration**: API gateway routes requests and coordinates multi-service operations
- **Permission Model**: Role-based access control (admin vs user)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Client                              │
│                  (examples/client.py)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Port 8080)                  │
│                (examples/api_gateway.py)                    │
│                                                             │
│  Methods:                                                   │
│  - login(username, password) → {token, userId, role}        │
│  - getUserProfile(token) → {userId, username, email, role}  │
│  - listUsers(token) → [{id, username, role}, ...]           │
│  - createOrder(token, items) → {orderId, total, status}     │
│  - listOrders(token) → [{orderId, total, status}, ...]      │
│  - cancelOrder(token, orderId) → {status, orderId}          │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
               │ HTTP                     │ HTTP
               ▼                          ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│   User Service (8081)    │  │   Order Service (8082)       │
│  (user_service.py)       │  │  (order_service.py)          │
│                          │  │                              │
│  User capability:        │  │  Order capability:           │
│  - getId() → str         │  │  - getId() → str             │
│  - getUsername() → str   │  │  - getUserId() → str         │
│  - getEmail() → str      │  │  - getTotal() → float        │
│  - getRole() → str       │  │  - getStatus() → str         │
│  - hasPermission(p)      │  │  - cancel(user) → result     │
│                          │  │                              │
│  Service methods:        │  │  Service methods:            │
│  - authenticate()        │  │  - createOrder(user, items)  │
│  - getUser(id)           │  │  - listOrders(user)          │
│  - getUserByToken(token) │  │  - cancelOrder(id, user)     │
│  - listUsers()           │  │  - getOrder(id)              │
└──────────────────────────┘  └──────────────────────────────┘
```

## Key Concepts Demonstrated

### 1. Capability Passing Between Services

The API gateway receives a token, converts it to a User capability via the User Service, then **passes that capability** to the Order Service:

```python
# API Gateway
async def _create_order(self, token: str, items: list):
    # Get User capability from User Service
    user_capability: RpcStub = await user_client.call(0, "getUserByToken", [token])

    # Pass capability to Order Service for permission checking
    result = await order_client.call(0, "createOrder", [user_capability, items])

    return result
```

### 2. Cross-Service Permission Verification

The Order Service calls methods on the User capability to verify permissions:

```python
# Order Service
async def _create_order(self, user_capability: RpcStub, items: list):
    # Get user ID from the capability
    user_id = await user_capability.getId()

    # Check permissions via RPC call to the capability
    has_permission = await user_capability.hasPermission("order.create")
    if not has_permission:
        raise RpcError.permission_denied("You don't have permission to create orders")

    # Create order...
```

### 3. Service Mesh Communication

Each service is independent and can be scaled separately:

- **User Service (8081)**: Manages users and authentication
- **Order Service (8082)**: Manages orders, calls User Service for permissions
- **API Gateway (8080)**: Orchestrates requests, doesn't contain business logic

### 4. Role-Based Access Control

Users have different permission sets based on their role:

```python
# User capability
def _has_permission(self, permission: str) -> bool:
    admin_permissions = {"user.create", "user.delete", "order.cancel", "system.admin"}
    user_permissions = {"order.create", "order.view", "profile.edit"}

    if self.role == "admin":
        return True  # Admin has all permissions
    elif self.role == "user":
        return permission in user_permissions
    return False
```

## Running the Example

### Terminal 1 - User Service

```bash
python examples/microservices/user_service.py
```

Output:
```
🔐 User Service running on http://127.0.0.1:8081
   Endpoint: http://127.0.0.1:8081/rpc/batch

Available users:
  - alice (admin)
  - bob (user)
  - charlie (user)

Press Ctrl+C to stop
```

### Terminal 2 - Order Service

```bash
python examples/microservices/order_service.py
```

Output:
```
📦 Order Service running on http://127.0.0.1:8082
   Endpoint: http://127.0.0.1:8082/rpc/batch
   User Service: http://127.0.0.1:8081/rpc/batch

Press Ctrl+C to stop
```

### Terminal 3 - API Gateway

```bash
python examples/microservices/api_gateway.py
```

Output:
```
🌐 API Gateway running on http://127.0.0.1:8080
   Endpoint: http://127.0.0.1:8080/rpc/batch

Backend services:
   User Service:  http://127.0.0.1:8081
   Order Service: http://127.0.0.1:8082

Run client with: python examples/microservices/client.py
Press Ctrl+C to stop
```

### Terminal 4 - Demo Client

```bash
python examples/microservices/client.py
```

Output:
```
=== Microservices Demo ===

1. Login as Bob (regular user)
   ✓ Logged in as bob (role: user)
   Token: token_bob_0

2. Get Bob's profile
   User ID: user2
   Username: bob
   Email: bob@example.com
   Role: user

3. List all users
   Found 3 users:
     - alice (id: user1, role: admin)
     - bob (id: user2, role: user)
     - charlie (id: user3, role: user)

4. Create an order as Bob
   ✓ Order created: order1
   Total: $1059.97
   Status: pending
   Items: 2

5. List Bob's orders
   Found 1 order(s):
     - order1: $1059.97 (pending)

6. Try to cancel order as Bob (should fail)
   ✓ Expected failure: You don't have permission to cancel orders

7. Login as Alice (admin)
   ✓ Logged in as alice (role: admin)
   Token: token_alice_1

8. Create an order as Alice
   ✓ Order created: order2
   Total: $4999.99

9. Alice cancels Bob's order (should succeed)
   ✓ Order cancelled: order1
   Status: cancelled

10. Verify Bob's order was cancelled
   Order order1 status: cancelled
   ✓ Order successfully cancelled

=== Demo Complete ===

This demo showed:
  • API Gateway routing requests to backend services
  • User authentication via User Service
  • Cross-service capability passing (User → Order Service)
  • Permission-based access control (admin can cancel, user cannot)
  • Service mesh architecture with Cap'n Web
```

## Code Walkthrough

### User Service

**User Capability** (`User` class):
- Represents a logged-in user
- Can be passed between services
- Provides permission checking via `hasPermission()`

```python
class User(RpcTarget):
    async def call(self, method: str, args: list):
        match method:
            case "getId": return self.user_id
            case "hasPermission": return self._has_permission(args[0])
```

**UserService** (`UserService` class):
- Manages user accounts
- Authenticates users and returns session tokens
- Maps tokens to User capabilities

```python
async def _authenticate(self, username: str, password: str):
    # Find user and create session token
    session_token = f"token_{username}_{len(self.sessions)}"
    self.sessions[session_token] = user
    return {"token": session_token, "userId": user.user_id, ...}

def _get_user_by_token(self, token: str) -> User:
    # Return User capability for the token
    return self.sessions[token]
```

### Order Service

**Order Capability** (`Order` class):
- Represents a single order
- Validates permissions before cancellation

**OrderService** (`OrderService` class):
- Creates orders with permission checking
- Verifies permissions by calling User capability methods

```python
async def _create_order(self, user_capability: RpcStub, items: list):
    # Extract user ID from capability
    user_id = await user_capability.getId()

    # Check permission via capability
    has_permission = await user_capability.hasPermission("order.create")
    if not has_permission:
        raise RpcError.permission_denied(...)

    # Create order...
```

### API Gateway

**ApiGateway** (`ApiGateway` class):
- Routes all client requests
- Connects to backend services
- Orchestrates multi-service operations

**Key Flow - Creating an Order:**

1. Client calls `createOrder(token, items)`
2. Gateway gets User capability from User Service
3. Gateway passes User capability to Order Service
4. Order Service calls `user_capability.hasPermission("order.create")`
5. User Service executes permission check
6. Order Service creates order if permitted
7. Gateway returns result to client

```python
async def _create_order(self, token: str, items: list):
    user_client = await self._get_user_client()
    order_client = await self._get_order_client()

    # Get user capability from token
    user_capability = await user_client.call(0, "getUserByToken", [token])

    # Pass capability to order service (cross-service capability passing!)
    result = await order_client.call(0, "createOrder", [user_capability, items])

    return result
```

## Permission Model

### User Permissions
- `order.create` - Create new orders
- `order.view` - View own orders
- `profile.edit` - Edit own profile

### Admin Permissions
- All user permissions, plus:
- `user.create` - Create new users
- `user.delete` - Delete users
- `order.cancel` - Cancel any order
- `system.admin` - System administration

## Security Highlights

1. **Capabilities are Unforgeable**: Only the User Service can create User capabilities
2. **No Token Inspection**: Order Service never sees tokens, only capabilities
3. **Permission Delegation**: User Service is authoritative for all permission checks
4. **Service Isolation**: Each service can be secured independently
5. **No Ambient Authority**: Services can only do what capabilities allow

## Scaling Considerations

For production deployments:

1. **Service Discovery**: Use Consul/etcd instead of hardcoded URLs
2. **Load Balancing**: Run multiple instances of each service
3. **Database**: Replace in-memory storage with PostgreSQL/MongoDB
4. **Authentication**: Use JWT tokens with expiration and refresh
5. **API Gateway**: Use Kong/Envoy for production gateway
6. **Observability**: Add distributed tracing (OpenTelemetry)
7. **Rate Limiting**: Prevent abuse at gateway level
8. **Circuit Breakers**: Handle service failures gracefully

## Error Handling

The example demonstrates several error scenarios:

**Permission Denied:**
```python
# Bob tries to cancel an order
try:
    await client.call(0, "cancelOrder", [bob_token, order_id])
except RpcError as e:
    print(e.message)  # "You don't have permission to cancel orders"
```

**Invalid Token:**
```python
try:
    await client.call(0, "getUserProfile", ["invalid_token"])
except RpcError as e:
    print(e.message)  # "Invalid or expired token"
```

**Service Unavailable:**
```python
try:
    async with Client(config) as client:
        # ...
except Exception as e:
    print(f"Connection error: {e}")
```

## Extending the Example

### Add More Services

```python
# Product Service (8083)
class ProductService(RpcTarget):
    async def call(self, method: str, args: list):
        match method:
            case "getProduct":
                return self._get_product(args[0])
            case "checkInventory":
                return self._check_inventory(args[0], args[1])
```

### Add Private Messaging

```python
# In Order Service
async def _notify_user(self, user_capability: RpcStub, message: str):
    # If User capability exposes sendNotification method
    await user_capability.sendNotification(message)
```

### Add Payment Service

```python
# Payment Service
async def _process_payment(self, user_capability: RpcStub, amount: float):
    user_id = await user_capability.getId()
    # Process payment...
    return {"transactionId": txn_id, "status": "success"}
```

## Related Examples

- [Calculator](../calculator/) - Basic client/server RPC
- [Chat](../chat/) - WebSocket transport and bidirectional RPC
- [Peer-to-Peer](../peer_to_peer/) - Bidirectional capability passing

## Next Steps

- Run all three services and the client
- Modify permission model in `user_service.py`
- Add new methods to services
- Create additional user roles (e.g., "moderator")
- Implement order history tracking
- Add webhook notifications
