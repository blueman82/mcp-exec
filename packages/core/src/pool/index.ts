export {
  ServerPool,
  ConnectionError,
  PoolExhaustedError,
  type ConnectionFactory,
  type PoolConfig,
} from './server-pool.js';

export {
  createConnection,
  closeConnection,
  SpawnError,
  TimeoutError,
  UnexpectedExitError,
  type CreateConnectionOptions,
} from './connection.js';

export { buildSpawnConfig, type SpawnConfig } from './stdio-transport.js';
