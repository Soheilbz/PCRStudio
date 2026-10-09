import { describe, expect, it } from 'vitest';
import { QueryClient, QueryObserver } from '@tanstack/react-query';
import {
  clearDeniedContent,
  clearPrivateState,
  privateKey,
} from '../app/lib/privacy';
describe('confidential query state', () => {
  it('cancels an in-flight private read and removes cached workspace content', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const key = privateKey('identity-a', 'workspace-a', 'projects');
    client.setQueryData(
      privateKey('identity-a', 'workspace-a', 'project', 'id'),
      { name: 'Synthetic private draft' },
    );
    let aborted = false;
    const read = client
      .fetchQuery({
        queryKey: key,
        queryFn: ({ signal }) =>
          new Promise<string>((resolve, reject) => {
            void resolve;
            signal.addEventListener('abort', () => {
              aborted = true;
              reject(new Error('cancelled'));
            });
          }),
      })
      .catch(() => undefined);
    await clearPrivateState(client);
    await read;
    expect(aborted).toBe(true);
    expect(client.getQueryCache().getAll()).toHaveLength(0);
    expect(
      client.getQueryData(privateKey('identity-b', 'workspace-b', 'projects')),
    ).toBeUndefined();
  });
  it('cannot reuse one workspace cache as another workspace’s loading data', () => {
    const client = new QueryClient();
    client.setQueryData(privateKey('user', 'one', 'projects'), ['synthetic']);
    expect(
      client.getQueryData(privateKey('user', 'two', 'projects')),
    ).toBeUndefined();
    expect(
      client.getQueryData(privateKey('different-user', 'one', 'projects')),
    ).toBeUndefined();
  });
  it('drops unauthorized content from active observers and inactive caches while preserving the access error', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const key = privateKey('identity', 'workspace', 'project', 'synthetic');
    client.setQueryData(key, {
      name: 'Previously authorized synthetic project',
    });
    client.setQueryData(privateKey('identity', 'workspace', 'projects'), [
      'Previously authorized list',
    ]);
    client.setQueryData(['me'], { id: 'identity' });
    const denied = new Error('Access unavailable');
    const observer = new QueryObserver(client, {
      queryKey: key,
      queryFn: async () => {
        throw denied;
      },
      enabled: false,
    });
    const unsubscribe = observer.subscribe(() => {});
    await observer.refetch();
    await clearDeniedContent(client);
    expect(observer.getCurrentResult().data).toBeUndefined();
    expect(observer.getCurrentResult().error).toBe(denied);
    expect(
      client.getQueryData(privateKey('identity', 'workspace', 'projects')),
    ).toBeUndefined();
    expect(client.getQueryData(['me'])).toEqual({ id: 'identity' });
    unsubscribe();
  });
  it('revalidates a mounted read after a denied mutation without retaining its previous content', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const key = privateKey('identity', 'workspace', 'project', 'synthetic');
    client.setQueryData(key, {
      name: 'Previously authorized synthetic project',
    });
    const denied = new Error('Access unavailable');
    const observer = new QueryObserver(client, {
      queryKey: key,
      queryFn: async () => {
        throw denied;
      },
      staleTime: Infinity,
    });
    const unsubscribe = observer.subscribe(() => {});
    await clearDeniedContent(client);
    expect(observer.getCurrentResult().data).toBeUndefined();
    expect(observer.getCurrentResult().error).toBe(denied);
    unsubscribe();
  });
});
