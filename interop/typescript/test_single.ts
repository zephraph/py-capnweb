import { newHttpBatchRpcSession, RpcTarget } from 'capnweb';

interface TestService extends RpcTarget {
  echo(value: any): any;
}

async function main() {
  const url = 'http://127.0.0.1:18093/rpc/batch';
  
  console.log('Test 1: Direct await');
  try {
    const api = newHttpBatchRpcSession<TestService>(url);
    const result = await api.echo('Hello');
    console.log('Success:', result);
  } catch (e: any) {
    console.log('Error:', e.message);
  }
  
  console.log('\nTest 2: Chained call');
  try {
    const result = await newHttpBatchRpcSession<TestService>(url).echo('Hello');
    console.log('Success:', result);
  } catch (e: any) {
    console.log('Error:', e.message);
  }
}

main();
