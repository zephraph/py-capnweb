#!/usr/bin/env node
/**
 * TypeScript interop server for testing with Python client.
 *
 * This server implements the same API as the Python server for interop testing.
 */

import http from 'node:http';
import { RpcTarget, nodeHttpBatchRpcResponse } from 'capnweb';

/**
 * User capability
 */
class User extends RpcTarget {
  constructor(
    public userId: number,
    public name: string,
    public email: string
  ) {
    super();
  }

  getName(): string {
    return this.name;
  }

  getEmail(): string {
    return this.email;
  }

  updateName(newName: string): { old: string; new: string } {
    const oldName = this.name;
    this.name = newName;
    return { old: oldName, new: this.name };
  }

  // Properties accessed via getters
  get id(): number {
    return this.userId;
  }
}

/**
 * Main test service
 */
class TestService extends RpcTarget {
  private users: Map<number, User>;

  constructor() {
    super();
    this.users = new Map([
      [1, new User(1, 'Alice', 'alice@example.com')],
      [2, new User(2, 'Bob', 'bob@example.com')],
      [3, new User(3, 'Charlie', 'charlie@example.com')],
    ]);
  }

  echo(value: any): any {
    return value ?? null;
  }

  add(a: number, b: number): number {
    return a + b;
  }

  multiply(a: number, b: number): number {
    return a * b;
  }

  concat(...args: any[]): string {
    return args.map(String).join('');
  }

  getUser(userId: number): User {
    const user = this.users.get(userId);
    if (!user) {
      throw new Error(`User ${userId} not found`);
    }
    return user;
  }

  getUserName(userId: number): string {
    const user = this.users.get(userId);
    if (!user) {
      throw new Error(`User ${userId} not found`);
    }
    return user.name;
  }

  createUser(userId: number, name: string, email: string): User {
    const user = new User(userId, name, email);
    this.users.set(userId, user);
    return user;
  }

  getUserCount(): number {
    return this.users.size;
  }

  getAllUserNames(): string[] {
    return Array.from(this.users.values()).map((u) => u.name);
  }

  throwError(errorType: string = 'internal'): never {
    switch (errorType) {
      case 'not_found':
        throw new Error('Resource not found');
      case 'bad_request':
        throw new Error('Invalid request');
      case 'permission_denied':
        throw new Error('Access denied');
      default:
        throw new Error('Internal server error');
    }
  }

  processArray(arr: number[]): number[] {
    return arr.map((x) => x * 2);
  }

  processObject(obj: Record<string, any>): {
    original: Record<string, any>;
    keys: string[];
    count: number;
  } {
    return {
      original: obj,
      keys: Object.keys(obj),
      count: Object.keys(obj).length,
    };
  }

  async asyncDelay(delay: number = 0.1): Promise<string> {
    await new Promise((resolve) => setTimeout(resolve, delay * 1000));
    return `Delayed ${delay}s`;
  }

  batchTest(value: number = 0): { timestamp: number; value: number } {
    return {
      timestamp: Date.now() / 1000,
      value: value,
    };
  }

  // Properties accessed via getters
  get version(): string {
    return '1.0.0';
  }

  get language(): string {
    return 'typescript';
  }

  get userCount(): number {
    return this.users.size;
  }
}

/**
 * Start the TypeScript interop server
 */
async function main() {
  const port = parseInt(process.argv[2] || '8081', 10);

  const server = http.createServer(async (req, res) => {
    // Handle /rpc/batch endpoint for HTTP batch RPC
    if (req.method === 'POST' && req.url === '/rpc/batch') {
      try {
        await nodeHttpBatchRpcResponse(req, res, new TestService(), {
          headers: { 'Access-Control-Allow-Origin': '*' },
        });
      } catch (err: any) {
        console.error('RPC Error:', err?.stack || err);
        res.writeHead(500, { 'content-type': 'text/plain' });
        res.end(String(err?.stack || err));
      }
      return;
    }

    res.writeHead(404, { 'content-type': 'text/plain' });
    res.end('Not Found');
  });

  server.listen(port, '127.0.0.1', () => {
    console.log(
      `TypeScript interop server listening on http://127.0.0.1:${port}/rpc/batch`
    );
    console.log('Ready for interop testing...');
  });
}

// Run server
main().catch(console.error);
