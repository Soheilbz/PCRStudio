import type { QueryClient } from '@tanstack/react-query';
let epoch = 0;
export function privateStateEpoch() {
  return epoch;
}
export async function clearPrivateState(client: QueryClient) {
  epoch += 1;
  await client.cancelQueries();
  client.clear();
}
// Retain a failed active query's error while dropping its last successful data.
// Removing an active query alone leaves its observer holding the old response.
export async function clearDeniedContent(client: QueryClient) {
  epoch += 1;
  await client.cancelQueries({ queryKey: ['private'] });
  for (const query of client
    .getQueryCache()
    .findAll({ queryKey: ['private'] })) {
    query.setState({ data: undefined, dataUpdatedAt: 0 });
    if (query.getObserversCount() === 0) client.getQueryCache().remove(query);
  }
  // A denied write may be the first indication that a mounted read lost access.
  // Revalidate those reads so the page can show the server's current error.
  await client.invalidateQueries({
    queryKey: ['private'],
    predicate: (query) => query.state.status !== 'error',
  });
}
export function privateKey(
  identity: string,
  workspace: string,
  resource: string,
  ...parts: unknown[]
) {
  return ['private', identity, workspace, resource, ...parts] as const;
}
