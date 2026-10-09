import { type RouteConfig, index, route } from '@react-router/dev/routes';
export default [
  index('routes/app.tsx', { id: 'routes/app-index' }),
  route('*', 'routes/app.tsx'),
] satisfies RouteConfig;
