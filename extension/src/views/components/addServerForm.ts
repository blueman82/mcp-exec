/**
 * Add Server Form Component
 * Form for adding/editing MCP server configurations with validation.
 * Supports dynamic env var rows with add/remove functionality.
 */

import { ServerConfig } from './serverList';

export type CommandType = 'node' | 'npx' | 'uvx' | 'python' | 'custom';

export interface AddServerFormData {
    name: string;
    commandType: CommandType;
    command: string;
    args: string[];
    env: Record<string, string>;
}

export interface AddServerFormCallbacks {
    onSave: (data: AddServerFormData, originalName?: string) => void;
    onCancel: () => void;
    onValidationError: (message: string) => void;
}

export interface ValidationResult {
    valid: boolean;
    errors: string[];
}

/**
 * Command type options for dropdown
 */
export const COMMAND_TYPE_OPTIONS: Array<{ value: CommandType; label: string; hint: string }> = [
    { value: 'node', label: 'node', hint: 'Run Node.js script directly' },
    { value: 'npx', label: 'npx', hint: 'Run npm package' },
    { value: 'uvx', label: 'uvx', hint: 'Run uv/Python package' },
    { value: 'python', label: 'python', hint: 'Run Python script' },
    { value: 'custom', label: 'custom', hint: 'Custom command' },
];

/**
 * Escapes HTML special characters to prevent XSS
 */
function escapeHtml(str: string): string {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Validates server form data
 */
export function validateFormData(data: AddServerFormData): ValidationResult {
    const errors: string[] = [];

    // Name validation
    if (!data.name || data.name.trim() === '') {
        errors.push('Server name is required');
    } else if (!/^[a-zA-Z0-9_-]+$/.test(data.name.trim())) {
        errors.push('Server name must contain only letters, numbers, underscores, and hyphens');
    }

    // Command validation
    if (!data.command || data.command.trim() === '') {
        errors.push('Command/package is required');
    }

    // Env var key validation
    for (const key of Object.keys(data.env)) {
        if (key && !/^[A-Z_][A-Z0-9_]*$/i.test(key)) {
            errors.push(`Invalid env var name: ${key}`);
        }
    }

    return {
        valid: errors.length === 0,
        errors,
    };
}

/**
 * Parses args string into array (handles newlines and spaces)
 */
export function parseArgs(argsString: string): string[] {
    if (!argsString.trim()) return [];
    // Split by newlines first, then by spaces
    return argsString
        .split(/[\n\r]+/)
        .flatMap((line) => line.trim().split(/\s+/))
        .filter((arg) => arg.length > 0);
}

/**
 * Generates HTML for command type dropdown options
 */
function renderCommandTypeOptions(selected: CommandType): string {
    return COMMAND_TYPE_OPTIONS.map(
        (opt) =>
            `<option value="${opt.value}" ${selected === opt.value ? 'selected' : ''}>${opt.label}</option>`
    ).join('');
}

/**
 * Generates HTML for a single env var row
 */
export function renderEnvVarRow(key = '', value = '', index: number): string {
    return `
        <div class="env-var-row" data-index="${index}">
            <input
                type="text"
                class="form-input env-key"
                placeholder="KEY"
                value="${escapeHtml(key)}"
                data-field="env-key"
            >
            <input
                type="text"
                class="form-input env-value"
                placeholder="value"
                value="${escapeHtml(value)}"
                data-field="env-value"
            >
            <button class="btn btn-icon btn-remove" data-action="remove-env" data-index="${index}" title="Remove">&times;</button>
        </div>
    `;
}

/**
 * Generates the complete form HTML
 */
export function renderAddServerForm(server?: ServerConfig, isEdit = false): string {
    const name = server?.name || '';
    const commandType = server?.commandType || 'npx';
    const command = server?.command || '';
    const args = server?.args?.join(' ') || '';
    const env = server?.env || {};
    const envEntries = Object.entries(env);

    return `
        <div id="add-server-form" class="add-server-form">
            <div class="form-group">
                <label class="form-label" for="form-server-name">Server Name *</label>
                <input
                    type="text"
                    id="form-server-name"
                    class="form-input"
                    placeholder="e.g., my-mcp-server"
                    value="${escapeHtml(name)}"
                    ${isEdit ? 'readonly' : ''}
                    required
                >
                <div class="form-hint">Unique identifier for this server (letters, numbers, hyphens, underscores)</div>
            </div>

            <div class="form-group">
                <label class="form-label" for="form-command-type">Command Type</label>
                <select id="form-command-type" class="form-select">
                    ${renderCommandTypeOptions(commandType)}
                </select>
                <div class="form-hint">How to run the MCP server</div>
            </div>

            <div class="form-group">
                <label class="form-label" for="form-command">Command / Package *</label>
                <input
                    type="text"
                    id="form-command"
                    class="form-input"
                    placeholder="e.g., @modelcontextprotocol/server-filesystem"
                    value="${escapeHtml(command)}"
                    required
                >
                <div class="form-hint">Package name (npx/uvx) or script path (node/python/custom)</div>
            </div>

            <div class="form-group">
                <label class="form-label" for="form-args">Arguments</label>
                <textarea
                    id="form-args"
                    class="form-input form-textarea"
                    placeholder="--path /some/path&#10;--option value"
                    rows="3"
                >${escapeHtml(args)}</textarea>
                <div class="form-hint">One argument per line, or space-separated</div>
            </div>

            <div class="form-group">
                <label class="form-label">Environment Variables</label>
                <div class="env-vars-container" id="form-env-vars-container">
                    <div id="form-env-var-rows">
                        ${envEntries.length > 0 ? envEntries.map(([k, v], i) => renderEnvVarRow(k, v, i)).join('') : ''}
                    </div>
                    <button class="btn btn-secondary" id="form-btn-add-env" type="button" data-action="add-env">+ Add Variable</button>
                </div>
                <div class="form-hint">Optional environment variables for the server process</div>
            </div>
        </div>
    `;
}

/**
 * Collects form data from DOM
 */
export function collectFormData(container: HTMLElement): AddServerFormData {
    const name = (container.querySelector('#form-server-name') as HTMLInputElement)?.value || '';
    const commandType =
        ((container.querySelector('#form-command-type') as HTMLSelectElement)?.value as CommandType) ||
        'npx';
    const command = (container.querySelector('#form-command') as HTMLInputElement)?.value || '';
    const argsText = (container.querySelector('#form-args') as HTMLTextAreaElement)?.value || '';
    const args = parseArgs(argsText);

    const env: Record<string, string> = {};
    container.querySelectorAll('.env-var-row').forEach((row) => {
        const key = (row.querySelector('.env-key') as HTMLInputElement)?.value?.trim() || '';
        const value = (row.querySelector('.env-value') as HTMLInputElement)?.value || '';
        if (key) {
            env[key] = value;
        }
    });

    return { name: name.trim(), commandType, command: command.trim(), args, env };
}

/**
 * Creates and manages form state with event handlers
 */
export function createAddServerFormComponent(
    container: HTMLElement,
    _callbacks: AddServerFormCallbacks
): {
    render: (server?: ServerConfig, isEdit?: boolean) => void;
    getData: () => AddServerFormData;
    validate: () => ValidationResult;
    reset: () => void;
} {
    let envRowIndex = 0;

    function render(server?: ServerConfig, isEdit = false): void {
        container.innerHTML = renderAddServerForm(server, isEdit);
        envRowIndex = Object.keys(server?.env || {}).length;
        attachEventListeners();
    }

    function attachEventListeners(): void {
        // Add env var button
        const addEnvBtn = container.querySelector('#form-btn-add-env');
        addEnvBtn?.addEventListener('click', () => {
            const envRowsContainer = container.querySelector('#form-env-var-rows');
            if (envRowsContainer) {
                envRowsContainer.insertAdjacentHTML('beforeend', renderEnvVarRow('', '', envRowIndex++));
            }
        });

        // Event delegation for remove buttons
        container.addEventListener('click', (event) => {
            const target = event.target as HTMLElement;
            if (target.dataset.action === 'remove-env') {
                target.closest('.env-var-row')?.remove();
            }
        });

        // Real-time validation on name field
        const nameInput = container.querySelector('#form-server-name') as HTMLInputElement;
        nameInput?.addEventListener('blur', () => {
            const name = nameInput.value.trim();
            if (name && !/^[a-zA-Z0-9_-]+$/.test(name)) {
                nameInput.classList.add('invalid');
            } else {
                nameInput.classList.remove('invalid');
            }
        });
    }

    function getData(): AddServerFormData {
        return collectFormData(container);
    }

    function validate(): ValidationResult {
        const data = getData();
        return validateFormData(data);
    }

    function reset(): void {
        envRowIndex = 0;
        render();
    }

    return { render, getData, validate, reset };
}

/**
 * Handle form submission with validation
 */
export function handleFormSubmit(
    container: HTMLElement,
    callbacks: AddServerFormCallbacks,
    originalName?: string
): void {
    const data = collectFormData(container);
    const validation = validateFormData(data);

    if (!validation.valid) {
        callbacks.onValidationError(validation.errors.join('\n'));
        return;
    }

    callbacks.onSave(data, originalName);
}
