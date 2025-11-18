export interface MemoryResourceOptions {
  limit?: number;
  onLimitExceeded?: () => void;
}

interface MemoryResource extends MemoryResourceOptions {
  getUsage: () => number;
  lastUsage: number;
}

interface MemoryResourceStatus {
  usage: number;
  limit?: number;
  timestamp: number;
}

export class MemoryManager {
  private static instance: MemoryManager | null = null;

  private resources = new Map<string, MemoryResource>();
  private resourceStatus = new Map<string, MemoryResourceStatus>();

  static getInstance(): MemoryManager {
    if (!MemoryManager.instance) {
      MemoryManager.instance = new MemoryManager();
    }
    return MemoryManager.instance;
  }

  registerResource(id: string, getUsage: () => number, options: MemoryResourceOptions = {}): void {
    this.resources.set(id, {
      getUsage,
      limit: options.limit,
      onLimitExceeded: options.onLimitExceeded,
      lastUsage: 0,
    });
    this.updateResourceUsage(id);
  }

  unregisterResource(id: string): void {
    this.resources.delete(id);
    this.resourceStatus.delete(id);
  }

  updateResourceUsage(id: string, usage?: number): void {
    const resource = this.resources.get(id);
    if (!resource) {
      return;
    }

    const currentUsage = usage ?? resource.getUsage();
    resource.lastUsage = currentUsage;
    this.resourceStatus.set(id, {
      usage: currentUsage,
      limit: resource.limit,
      timestamp: Date.now(),
    });

    if (resource.limit !== undefined && currentUsage > resource.limit) {
      resource.onLimitExceeded?.();
    }
  }

  getResourceUsage(id: string): number {
    const status = this.resourceStatus.get(id);
    if (status) {
      return status.usage;
    }
    const resource = this.resources.get(id);
    if (!resource) {
      return 0;
    }
    const usage = resource.getUsage();
    this.updateResourceUsage(id, usage);
    return usage;
  }

  getStatus(): Record<string, MemoryResourceStatus> {
    const result: Record<string, MemoryResourceStatus> = {};
    for (const [id, status] of this.resourceStatus.entries()) {
      result[id] = { ...status };
    }
    return result;
  }

  enforceLimits(): void {
    for (const [id, resource] of this.resources.entries()) {
      const usage = resource.getUsage();
      if (usage !== resource.lastUsage) {
        this.updateResourceUsage(id, usage);
      }
      if (resource.limit !== undefined && usage > resource.limit) {
        resource.onLimitExceeded?.();
      }
    }
  }

  destroy(): void {
    this.resources.clear();
    this.resourceStatus.clear();
    MemoryManager.instance = null;
  }
}

export const getMemoryManager = () => MemoryManager.getInstance();
