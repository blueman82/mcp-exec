/**
 * Connection Queue Manager
 * Manages EventSource connection limits (browser max: 6 concurrent SSE per origin)
 */

interface ConnectionRequest {
  id: string;
  url: string;
  resolve: (eventSource: EventSource) => void;
  reject: (error: Error) => void;
}

class ConnectionQueueManager {
  private maxConcurrentConnections = 6; // Browser SSE limit per origin
  private activeConnections = new Map<string, EventSource>();
  private queue: ConnectionRequest[] = [];

  /**
   * Request a connection (will queue if at capacity)
   * @param id Unique identifier for this connection (e.g., "prod1-ketchup-app-1")
   * @param url EventSource URL
   * @returns Promise that resolves with EventSource when slot available
   */
  async requestConnection(id: string, url: string): Promise<EventSource> {
    return new Promise((resolve, reject) => {
      // If already connected, return existing connection
      if (this.activeConnections.has(id)) {
        resolve(this.activeConnections.get(id)!);
        return;
      }

      // Add to queue
      this.queue.push({ id, url, resolve, reject });
      this.processQueue();
    });
  }

  /**
   * Release a connection slot and process queue
   * @param id Connection identifier to release
   */
  releaseConnection(id: string): void {
    if (this.activeConnections.has(id)) {
      const eventSource = this.activeConnections.get(id)!;
      eventSource.close();
      this.activeConnections.delete(id);

      // Process next queued connection
      this.processQueue();
    }
  }

  /**
   * Get current queue status for UI feedback
   * @returns {active: number, queued: number, capacity: number}
   */
  getStatus(): { active: number; queued: number; capacity: number } {
    return {
      active: this.activeConnections.size,
      queued: this.queue.length,
      capacity: this.maxConcurrentConnections,
    };
  }

  /**
   * Process queued connection requests
   * Opens EventSource connections up to max capacity
   */
  private processQueue(): void {
    while (
      this.queue.length > 0 &&
      this.activeConnections.size < this.maxConcurrentConnections
    ) {
      const request = this.queue.shift()!;

      try {
        // Create EventSource connection
        const eventSource = new EventSource(request.url);

        // Track active connection
        this.activeConnections.set(request.id, eventSource);

        // Resolve promise to caller
        request.resolve(eventSource);
      } catch (error) {
        request.reject(
          error instanceof Error ? error : new Error('Failed to create EventSource')
        );
      }
    }
  }

  /**
   * Close all connections and clear queue
   * Used for cleanup/reset scenarios
   */
  closeAll(): void {
    // Close all active connections
    this.activeConnections.forEach((eventSource) => {
      eventSource.close();
    });
    this.activeConnections.clear();

    // Reject all queued requests
    this.queue.forEach((request) => {
      request.reject(new Error('Connection queue cleared'));
    });
    this.queue = [];
  }
}

// Singleton instance
export const connectionQueueManager = new ConnectionQueueManager();
