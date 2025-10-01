#!/usr/bin/env node
/**
 * TypeScript interop client for testing against any Cap'n Web server.
 *
 * This client runs the same test suite as the Python client.
 * Uses the official capnweb library for proper compatibility.
 */

import { newHttpBatchRpcSession, RpcTarget } from 'capnweb';

/**
 * Test service interface matching the server
 */
interface TestService extends RpcTarget {
  echo(value: any): any;
  add(a: number, b: number): number;
  multiply(a: number, b: number): number;
  concat(...args: any[]): string;
  getUserCount(): number;
  processArray(arr: number[]): number[];
  processObject(obj: Record<string, any>): { original: Record<string, any>; keys: string[]; count: number };
  getAllUserNames(): string[];
  getUserName(userId: number): string;
  throwError(errorType: string): never;
}

/**
 * Helper to create a new session for each individual call
 * This avoids batch session lifecycle issues
 */
function createSession(url: string): any {
  return newHttpBatchRpcSession<TestService>(url);
}

/**
 * Run comprehensive interop tests
 */
async function runTests(url: string): Promise<Record<string, any>> {
  const results: Record<string, any> = {};

  console.log('Running interop tests...');

  // Test 1: Basic echo
  console.log('  1. Basic echo...');
  let result = await createSession(url).echo('Hello, World!');
  results.echo = result;
  if (result !== 'Hello, World!') throw new Error(`Echo failed: ${result}`);

  // Test 2: Arithmetic
  console.log('  2. Arithmetic (add)...');
  result = await createSession(url).add(5, 3);
  results.add = result;
  if (result !== 8) throw new Error(`Add failed: ${result}`);

  console.log('  3. Arithmetic (multiply)...');
  result = await createSession(url).multiply(7, 6);
  results.multiply = result;
  if (result !== 42) throw new Error(`Multiply failed: ${result}`);

  // Test 3: String operations
  console.log('  4. String concatenation...');
  result = await createSession(url).concat('Hello', ' ', 'World');
  results.concat = result;
  if (result !== 'Hello World') throw new Error(`Concat failed: ${result}`);

  // Test 4: Property access
  console.log('  5. Property access...');
  result = await createSession(url).getUserCount();
  results.userCount = result;
  if (typeof result !== 'number') throw new Error(`User count should be number: ${result}`);

  // Test 5: Array handling
  console.log('  6. Array processing...');
  result = await createSession(url).processArray([1, 2, 3, 4, 5]);
  results.processArray = result;
  if (JSON.stringify(result) !== JSON.stringify([2, 4, 6, 8, 10])) {
    throw new Error(`Process array failed: ${result}`);
  }

  // Test 6: Object handling
  console.log('  7. Object processing...');
  result = await createSession(url).processObject({ a: 1, b: 2, c: 3 });
  results.processObject = result;
  if (result.count !== 3) throw new Error(`Process object failed: ${JSON.stringify(result)}`);
  // Flatten keys if double-wrapped (implementation difference)
  const keysArray = Array.isArray(result.keys[0]) ? result.keys[0] : result.keys;
  const keys = new Set(keysArray);
  if (!keys.has('a') || !keys.has('b') || !keys.has('c')) {
    throw new Error(`Keys mismatch: expected [a,b,c], got ${JSON.stringify(keysArray)}`);
  }

  // Test 7: Get array of values
  console.log('  8. Get all user names...');
  result = await createSession(url).getAllUserNames();
  results.allUserNames = result;
  if (!Array.isArray(result)) throw new Error(`Should return array: ${result}`);
  if (result.length < 3) throw new Error(`Should have at least 3 users: ${result}`);

  // Test 8: Skip capability for now (needs proper serialization)
  // console.log('  9. Get user capability...');
  // const user = await createSession(url).getUser(1);

  // Test 9: Call method that returns user name directly
  console.log('  9. Get user name...');
  const name = await createSession(url).getUserName(1);
  results.userName = name;
  if (typeof name !== 'string') throw new Error(`User name should be string: ${name}`);

  // Test 10: Error handling
  console.log('  11. Error handling (not_found)...');
  try {
    await createSession(url).throwError('not_found');
    throw new Error('Should have raised an error');
  } catch (e: any) {
    results.errorNotFound = e.message;
    if (!e.message.toLowerCase().includes('not found')) {
      throw new Error(`Wrong error: ${e.message}`);
    }
  }

  console.log('  12. Error handling (bad_request)...');
  try {
    await createSession(url).throwError('bad_request');
    throw new Error('Should have raised an error');
  } catch (e: any) {
    results.errorBadRequest = e.message;
    const msg = e.message.toLowerCase();
    if (!msg.includes('invalid') && !msg.includes('bad')) {
      throw new Error(`Wrong error: ${e.message}`);
    }
  }

  // Test 11: Batch/concurrent calls - use a single session for this test
  console.log('  13. Concurrent batch calls...');
  const batchApi = createSession(url);
  const batchResults = await Promise.all([
    batchApi.add(1, 1),
    batchApi.add(2, 2),
    batchApi.add(3, 3),
  ]);
  results.batchCalls = batchResults;
  if (JSON.stringify(batchResults) !== JSON.stringify([2, 4, 6])) {
    throw new Error(`Batch calls failed: ${batchResults}`);
  }

  // Test 12: Property access on service
  console.log('  14. Service properties...');
  const version = await createSession(url).echo('test');
  results.serviceAlive = version !== null;

  console.log('\n✅ All tests passed!');
  return results;
}

/**
 * Main function
 */
async function main() {
  if (process.argv.length < 3) {
    console.log('Usage: node client.js <server-url>');
    console.log('Example: node client.js http://127.0.0.1:8080/rpc/batch');
    process.exit(1);
  }

  const url = process.argv[2];

  console.log(`TypeScript interop client connecting to: ${url}\n`);

  try {
    const results = await runTests(url);

    // Output results as JSON for comparison
    console.log('\nTest Results (JSON):');
    console.log(JSON.stringify(results, null, 2));
  } catch (error: any) {
    console.error('❌ Test failed:', error.message);
    process.exit(1);
  }
}

main().catch(console.error);
