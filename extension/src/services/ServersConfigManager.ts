import * as fs from 'fs';
import * as path from 'path';
import { getServersConfigPath } from '../utils/environment';
import { ServersConfigSchema, ServerConfigSchema, ServersConfig, ServerConfig } from '../types';

export class ConfigNotFoundError extends Error {
    constructor(configPath: string) {
        super(`Config file not found: ${configPath}`);
        this.name = 'ConfigNotFoundError';
    }
}

export class ConfigParseError extends Error {
    constructor(message: string) {
        super(`Failed to parse config: ${message}`);
        this.name = 'ConfigParseError';
    }
}

export class ConfigValidationError extends Error {
    constructor(message: string) {
        super(`Config validation failed: ${message}`);
        this.name = 'ConfigValidationError';
    }
}

/**
 * Servers Config Manager - CRUD operations for servers.json
 */
export class ServersConfigManager {
    private configPath: string;

    constructor(configPath?: string) {
        this.configPath = configPath ?? getServersConfigPath();
    }

    /**
     * Get the config file path
     */
    getConfigPath(): string {
        return this.configPath;
    }

    /**
     * Check if config file exists
     */
    exists(): boolean {
        return fs.existsSync(this.configPath);
    }

    /**
     * Load and validate servers config
     */
    load(): ServersConfig {
        if (!this.exists()) {
            throw new ConfigNotFoundError(this.configPath);
        }

        let rawData: string;
        try {
            rawData = fs.readFileSync(this.configPath, 'utf-8');
        } catch (err) {
            throw new ConfigNotFoundError(this.configPath);
        }

        let parsed: unknown;
        try {
            parsed = JSON.parse(rawData);
        } catch (err) {
            throw new ConfigParseError((err as Error).message);
        }

        const result = ServersConfigSchema.safeParse(parsed);
        if (!result.success) {
            throw new ConfigValidationError(result.error.message);
        }

        return result.data;
    }

    /**
     * Save config with atomic write (temp file + rename)
     */
    save(config: ServersConfig): void {
        const result = ServersConfigSchema.safeParse(config);
        if (!result.success) {
            throw new ConfigValidationError(result.error.message);
        }

        const dir = path.dirname(this.configPath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }

        const tempPath = `${this.configPath}.tmp`;
        const content = JSON.stringify(config, null, 2);

        fs.writeFileSync(tempPath, content, 'utf-8');
        fs.renameSync(tempPath, this.configPath);
    }

    /**
     * Initialize empty config if not exists
     */
    init(): ServersConfig {
        if (this.exists()) {
            return this.load();
        }

        const config: ServersConfig = { mcpServers: {} };
        this.save(config);
        return config;
    }

    /**
     * List all server names
     */
    listServers(): string[] {
        if (!this.exists()) {
            return [];
        }
        const config = this.load();
        return Object.keys(config.mcpServers);
    }

    /**
     * Get a server config by name
     */
    getServer(name: string): ServerConfig | undefined {
        if (!this.exists()) {
            return undefined;
        }
        const config = this.load();
        return config.mcpServers[name];
    }

    /**
     * Add or update a server
     */
    setServer(name: string, serverConfig: ServerConfig): void {
        const result = ServerConfigSchema.safeParse(serverConfig);
        if (!result.success) {
            throw new ConfigValidationError(result.error.message);
        }

        const config = this.exists() ? this.load() : { mcpServers: {} };
        config.mcpServers[name] = result.data;
        this.save(config);
    }

    /**
     * Remove a server
     * @returns true if removed, false if not found
     */
    removeServer(name: string): boolean {
        if (!this.exists()) {
            return false;
        }
        const config = this.load();
        if (!(name in config.mcpServers)) {
            return false;
        }
        delete config.mcpServers[name];
        this.save(config);
        return true;
    }

    /**
     * Enable/disable a server
     */
    setServerEnabled(name: string, enabled: boolean): boolean {
        const server = this.getServer(name);
        if (!server) {
            return false;
        }
        server.disabled = !enabled;
        this.setServer(name, server);
        return true;
    }
}
